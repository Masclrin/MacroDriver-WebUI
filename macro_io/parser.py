# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.paths import BASE_DIR, MACRO_ROOT

# 宽松 JSON（容忍宏文件里多余的结尾逗号 / 缺失的逗号 / 注释）
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
try:
    from lenient_json import loads_lenient as _loads_lenient
except Exception:  # noqa: BLE001
    _loads_lenient = None


def ensure_json_suffix(name: str) -> str:
    text = str(name).strip()
    if not text:
        raise ValueError("文件名不能为空")
    if not text.lower().endswith(".json"):
        text += ".json"
    return text


def safe_rel(path_like: str) -> str:
    text = str(path_like).strip().replace("\\", "/")
    text = text.lstrip("/")
    if not text:
        raise ValueError("路径不能为空")
    norm = os.path.normpath(text)
    if norm.startswith(".."):
        raise ValueError("不允许越界路径")
    return norm.replace("\\", "/")


def macro_abs_from_rel(rel_path: str) -> Path:
    rel = safe_rel(rel_path)
    abs_path = (BASE_DIR / rel).resolve()
    if not str(abs_path).startswith(str(BASE_DIR.resolve())):
        raise ValueError("路径越界")
    return abs_path


def _is_note_row(row: Any) -> bool:
    return isinstance(row, list) and len(row) >= 1 and str(row[0]).strip().lower() == "note"


def _is_raw_row(row: Any) -> bool:
    """未被识别的原始行：以 {"__raw": "<原始文本>"} 形式保留，保存时原样写回。"""
    return isinstance(row, dict) and isinstance(row.get("__raw"), str)


def _clean_comment_text(token: str) -> str:
    text = str(token)
    if text.startswith("//"):
        return text[2:].strip()
    if text.startswith("/*") and text.endswith("*/"):
        inner = text[2:-2]
        lines = [ln.strip() for ln in inner.splitlines()]
        return " ".join([ln for ln in lines if ln]).strip()
    return text.strip()


def _tokenize_macro_top_level(raw: str) -> List[Dict[str, str]]:
    tokens: List[Dict[str, str]] = []
    n = len(raw)
    start = raw.find("[")
    if start < 0:
        return tokens

    i = start + 1
    while i < n:
        while i < n and raw[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        if raw[i] == "]":
            break

        if raw.startswith("//", i):
            j = raw.find("\n", i)
            if j < 0:
                j = n
            tokens.append({"kind": "comment", "text": raw[i:j]})
            i = j
            continue

        if raw.startswith("/*", i):
            j = raw.find("*/", i + 2)
            if j < 0:
                j = n - 2
            tokens.append({"kind": "comment", "text": raw[i:j + 2]})
            i = j + 2
            continue

        value_start = i
        in_string = False
        escaped = False
        quote = '"'
        depth = 0

        while i < n:
            ch = raw[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    in_string = False
                i += 1
                continue

            if ch in ('"', "'"):
                in_string = True
                quote = ch
                i += 1
                continue

            if depth == 0 and (raw.startswith("//", i) or raw.startswith("/*", i)):
                break

            if ch in "[{":
                depth += 1
                i += 1
                continue

            if ch in "]}":
                if depth > 0:
                    depth -= 1
                    i += 1
                    # 顶层值（数组/对象）配对闭合即结束本 token。
                    # 这样即使两条动作之间漏写逗号，也不会被合并成同一个 token。
                    if depth == 0:
                        break
                    continue
                break

            if ch == "," and depth == 0:
                break

            i += 1

        value_text = raw[value_start:i].strip()
        if value_text:
            tokens.append({"kind": "value", "text": value_text})

        while i < n and raw[i] in " \t\r\n":
            i += 1

        while i < n and (raw.startswith("//", i) or raw.startswith("/*", i)):
            if raw.startswith("//", i):
                j = raw.find("\n", i)
                if j < 0:
                    j = n
                tokens.append({"kind": "comment", "text": raw[i:j]})
                i = j
            else:
                j = raw.find("*/", i + 2)
                if j < 0:
                    j = n - 2
                tokens.append({"kind": "comment", "text": raw[i:j + 2]})
                i = j + 2

            while i < n and raw[i] in " \t\r\n":
                i += 1

        if i < n and raw[i] == ",":
            i += 1

    return tokens


def load_macro_rows_with_notes(path: Path) -> List[List[Any]]:
    raw = path.read_text(encoding="utf-8")
    rows: List[List[Any]] = []
    for token in _tokenize_macro_top_level(raw):
        if token["kind"] == "comment":
            text = _clean_comment_text(token["text"])
            if text:
                rows.append(["note", text])
            continue

        if token["kind"] != "value":
            continue

        try:
            parsed = _loads_lenient(token["text"]) if _loads_lenient is not None else json.loads(token["text"])
        except Exception:
            # 解析失败不再静默丢弃：保留原始文本，前端可原文编辑，避免保存时丢数据
            rows.append({"__raw": token["text"]})
            continue

        if isinstance(parsed, list):
            rows.append(parsed)
        else:
            # 顶层不是数组（宏只接受数组指令）→ 同样保留原文而非丢弃
            rows.append({"__raw": token["text"]})

    return rows


def _normalize_rows_for_save(rows: List[List[Any]]) -> List[List[Any]]:
    normalized: List[List[Any]] = []
    for row in rows:
        if _is_raw_row(row):
            text = str(row.get("__raw", "")).strip()
            if text:
                normalized.append({"__raw": text})
            continue
        if not isinstance(row, list) or not row:
            continue

        cmd = str(row[0]).strip().lower()
        if cmd == "note":
            text = str(row[1]).strip() if len(row) >= 2 else ""
            if text:
                normalized.append(["note", text])
            continue

        if cmd == "loop" and len(row) >= 3 and isinstance(row[2], list):
            count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
            block = _normalize_rows_for_save(row[2])
            normalized.append(["loop", count, block])
            continue

        normalized.append(row)

    return normalized


def _serialize_rows_with_notes(rows: List[List[Any]], indent_level: int = 1) -> List[str]:
    pad = "    " * indent_level
    lines: List[str] = []
    action_rows = [row for row in rows if not _is_note_row(row)]
    action_index = 0

    for row in rows:
        if _is_note_row(row):
            text = str(row[1]).strip() if len(row) >= 2 else ""
            if text:
                lines.append(f"{pad}// {text}")
            continue

        action_index += 1
        comma = "," if action_index < len(action_rows) else ""

        if _is_raw_row(row):
            # 原文行：原样写回（去掉可能残留的行尾逗号，统一由序列化补逗号）
            raw_text = str(row.get("__raw", "")).strip().rstrip(",").rstrip()
            if raw_text:
                lines.append(f"{pad}{raw_text}{comma}")
            continue

        cmd = str(row[0]).strip().lower() if row else ""
        if cmd == "loop" and len(row) >= 3 and isinstance(row[2], list):
            count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
            block = row[2]
            if not block:
                lines.append(f"{pad}[\"loop\",{count},[]]{comma}")
            else:
                lines.append(f"{pad}[\"loop\",{count},[")
                lines.extend(_serialize_rows_with_notes(block, indent_level + 1))
                lines.append(f"{pad}]]{comma}")
            continue

        lines.append(f"{pad}{json.dumps(row, ensure_ascii=False, separators=(',', ':'))}{comma}")

    return lines


def save_macro_rows_with_notes(path: Path, rows: List[List[Any]]) -> None:
    normalized = _normalize_rows_for_save(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["["]
    lines.extend(_serialize_rows_with_notes(normalized, indent_level=1))
    lines.append("]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_macro_tree(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    root = {"name": "宏", "path": "宏", "folders": {}, "files": []}

    for item in items:
        rel = str(item.get("path", "")).strip().replace("\\", "/")
        if not rel:
            continue

        parts = [part for part in rel.split("/") if part]
        if not parts:
            continue

        node = root
        current_parts: List[str] = []
        for part in parts[:-1]:
            current_parts.append(part)
            folders = node["folders"]
            if part not in folders:
                folders[part] = {
                    "name": part,
                    "path": "/".join(current_parts),
                    "folders": {},
                    "files": [],
                }
            node = folders[part]

        node["files"].append(
            {
                "name": item.get("name") or parts[-1],
                "path": rel,
                "size": item.get("size"),
                "mtime": item.get("mtime"),
            }
        )

    def _to_list(node: Dict[str, Any]) -> Dict[str, Any]:
        folder_values = list(node["folders"].values())
        folder_values.sort(key=lambda x: x["name"])
        files = list(node["files"])
        files.sort(key=lambda x: x["path"])
        return {
            "name": node["name"],
            "path": node["path"],
            "folders": [_to_list(child) for child in folder_values],
            "files": files,
        }

    return _to_list(root)


class MacroFileApiMixin:
    def _list_macro_files(self, query: str = "") -> List[Dict[str, Any]]:
        query_l = query.strip().lower()
        files = []
        if not MACRO_ROOT.exists():
            return files

        for p in MACRO_ROOT.rglob("*.json"):
            # 跳过隐藏/临时文件（如测试点运行产生的 .xxx.__testrun.json）
            if p.name.startswith(".") or p.name.startswith("__"):
                continue
            rel = p.relative_to(BASE_DIR).as_posix()
            if query_l and query_l not in rel.lower() and query_l not in p.name.lower():
                continue
            files.append(
                {
                    "path": rel,
                    "name": p.name,
                    "folder": p.parent.relative_to(BASE_DIR).as_posix(),
                    "size": p.stat().st_size,
                    "mtime": int(p.stat().st_mtime),
                }
            )

        files.sort(key=lambda x: x["path"])
        return files

    def list_macros(self, query: str = ""):
        files = self._list_macro_files(query)
        return self._ok(items=files)

    def list_macro_tree(self, query: str = ""):
        files = self._list_macro_files(query)
        tree = build_macro_tree(files)
        return self._ok(items=files, tree=tree)

    def read_macro(self, rel_path: str):
        try:
            path = macro_abs_from_rel(rel_path)
            if not path.exists():
                return self._fail("宏文件不存在")

            rows = load_macro_rows_with_notes(path)
            return self._ok(path=safe_rel(rel_path), rows=rows)
        except Exception as exc:
            return self._fail("读取宏失败", str(exc))

    def save_macro(self, rel_path: str, rows: List[List[Any]]):
        try:
            if not isinstance(rows, list):
                return self._fail("rows 必须是数组")
            path = macro_abs_from_rel(rel_path)
            save_macro_rows_with_notes(path, rows)
            return self._ok(path=safe_rel(rel_path), count=len(rows))
        except Exception as exc:
            return self._fail("保存宏失败", str(exc))

    def run_macro_slice(self, rel_path: str, from_index: int = 0, to_index: int = None,
                        macro_label: str = ""):
        """从指定顶层行开始执行宏（宏编辑器"测试点运行"）。

        from_index/to_index 是**顶层动作行**的下标（to_index 不含，None=到末尾）。
        实现：切出顶层行 → 写到源文件同目录的临时宏（保证 import 相对路径可解析）
        → 交给旧引擎直接执行 → 立刻删除临时文件（加载/编译已在调用内完成）。
        """
        try:
            path = macro_abs_from_rel(rel_path)
            if not path.exists():
                return self._fail("宏文件不存在")

            rows = load_macro_rows_with_notes(path)
            total = len(rows)

            try:
                start = int(from_index)
            except (TypeError, ValueError):
                start = 0
            start = max(0, min(start, total))

            if to_index is None:
                end = total
            else:
                try:
                    end = int(to_index)
                except (TypeError, ValueError):
                    end = total
                end = max(0, min(end, total))

            if end <= start:
                return self._fail("测试区间为空（结束点需在起点之后）")

            runner = getattr(self.executor, "run_macro_file_once", None)
            if not callable(runner):
                return self._fail("当前引擎版本不支持直接运行宏切片")

            tmp_path = path.parent / f".{path.stem}.__testrun.json"
            try:
                save_macro_rows_with_notes(tmp_path, rows[start:end])
                label = macro_label or f"{path.name} [测试 {start + 1}~{end}]"
                ok, msg = runner(str(tmp_path), options=None, macro_name=label)
            finally:
                # 加载/编译已在 run_macro_file_once 内同步完成，可安全删除
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:  # noqa: BLE001
                    pass

            if not ok:
                return self._fail(msg)

            return self._ok(
                message=msg,
                from_index=start,
                to_index=end,
                total=total,
                executed_rows=end - start,
            )
        except Exception as exc:
            return self._fail("测试点运行失败", str(exc))

    def create_macro(self, folder_rel: str = "宏", file_name: str = "新建宏.json"):
        try:
            file_name = ensure_json_suffix(file_name)
            folder = macro_abs_from_rel(folder_rel)
            folder.mkdir(parents=True, exist_ok=True)

            target = folder / file_name
            if target.exists():
                stamp = time.strftime("%Y%m%d_%H%M%S")
                target = folder / file_name.replace(".json", f"_{stamp}.json")

            if self.simplify_tool is not None:
                self.simplify_tool.save_macro(str(target), [])
            else:
                save_macro_rows_with_notes(target, [])
            rel = target.relative_to(BASE_DIR).as_posix()
            return self._ok(path=rel)
        except Exception as exc:
            return self._fail("新建宏失败", str(exc))

    def rename_macro(self, old_rel: str, new_file_name: str):
        try:
            old_path = macro_abs_from_rel(old_rel)
            if not old_path.exists():
                return self._fail("原文件不存在")

            new_name = ensure_json_suffix(new_file_name)
            new_path = old_path.with_name(new_name)
            if new_path.exists():
                return self._fail("目标文件已存在")

            old_path.rename(new_path)

            old_key = safe_rel(old_rel)
            new_key = new_path.relative_to(BASE_DIR).as_posix()
            touched_triggers = set()
            for trigger, value in list(self.executor.MACRO_BINDINGS.items()):
                paths = self._normalize_binding_paths(value)
                replaced = False
                for idx, p in enumerate(paths):
                    if safe_rel(p) == old_key:
                        paths[idx] = new_key
                        replaced = True
                if replaced:
                    self.executor.MACRO_BINDINGS[trigger] = paths
                    touched_triggers.add(trigger)

            for trigger in touched_triggers:
                self._refresh_binding_cache(trigger, reason="宏重命名后刷新")

            self._persist_param_config()

            return self._ok(path=new_key)
        except Exception as exc:
            return self._fail("重命名失败", str(exc))

    def move_macro(self, old_rel: str, target_folder_rel: str):
        try:
            old_path = macro_abs_from_rel(old_rel)
            if not old_path.exists():
                return self._fail("原文件不存在")

            target_folder = macro_abs_from_rel(target_folder_rel)
            target_folder.mkdir(parents=True, exist_ok=True)

            new_path = target_folder / old_path.name
            if new_path.exists():
                return self._fail("目标位置已存在同名文件")

            old_path.rename(new_path)

            old_key = safe_rel(old_rel)
            new_key = new_path.relative_to(BASE_DIR).as_posix()
            touched_triggers = set()
            for trigger, value in list(self.executor.MACRO_BINDINGS.items()):
                paths = self._normalize_binding_paths(value)
                replaced = False
                for idx, p in enumerate(paths):
                    if safe_rel(p) == old_key:
                        paths[idx] = new_key
                        replaced = True
                if replaced:
                    self.executor.MACRO_BINDINGS[trigger] = paths
                    touched_triggers.add(trigger)

            for trigger in touched_triggers:
                self._refresh_binding_cache(trigger, reason="宏移动后刷新")

            self._persist_param_config()

            return self._ok(path=new_key)
        except Exception as exc:
            return self._fail("移动宏失败", str(exc))

    def delete_macro(self, rel_path: str):
        try:
            path = macro_abs_from_rel(rel_path)
            if not path.exists():
                return self._fail("文件不存在")

            safe_rel_path = path.relative_to(BASE_DIR).as_posix()
            touched_triggers = set()
            for trigger, value in list(self.executor.MACRO_BINDINGS.items()):
                paths = [p for p in self._normalize_binding_paths(value) if safe_rel(p) != safe_rel_path]
                if len(paths) == len(self._normalize_binding_paths(value)):
                    continue

                if paths:
                    self.executor.MACRO_BINDINGS[trigger] = paths
                    touched_triggers.add(trigger)
                else:
                    self.executor.MACRO_BINDINGS.pop(trigger, None)
                    self.executor.MACRO_RUNTIME_SETTINGS.pop(trigger, None)
                    self._invalidate_binding_cache(trigger)

            path.unlink()

            for trigger in touched_triggers:
                self._refresh_binding_cache(trigger, reason="宏删除后刷新")

            self._persist_param_config()
            return self._ok(path=safe_rel_path)
        except Exception as exc:
            return self._fail("删除失败", str(exc))

    def import_macros_from_folder(self, folder_path: str):
        try:
            src = Path(folder_path)
            if not src.exists() or not src.is_dir():
                return self._fail("目录不存在")

            copied = []
            for p in src.rglob("*.json"):
                rel_under_src = p.relative_to(src)
                target = MACRO_ROOT / rel_under_src
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    target = target.with_name(target.stem + f"_{stamp}" + target.suffix)
                shutil.copy2(p, target)
                copied.append(target.relative_to(BASE_DIR).as_posix())

            return self._ok(imported=copied, count=len(copied))
        except Exception as exc:
            return self._fail("导入宏失败", str(exc))

    def choose_import_folder(self):
        try:
            if self._window is None:
                return self._fail("窗口未就绪")
            result = self._window.create_file_dialog(self.webview.FOLDER_DIALOG, allow_multiple=False)
            if not result:
                return self._ok(canceled=True)
            return self._ok(path=result[0])
        except Exception as exc:
            return self._fail("打开目录选择器失败", str(exc))

    def choose_multi_format_files(self):
        try:
            if self._window is None:
                return self._fail("窗口未就绪")
            file_types = (
                "宏文件 (*.xml;*.lua;*.ahk;*.xmbcs;*.txt;*.json)",
                "Razer宏 (*.xml)",
                "Logitech宏 (*.lua)",
                "AutoHotkey (*.ahk)",
                "XMouse (*.xmbcs)",
                "文本宏 (*.txt)",
                "JSON宏 (*.json)",
            )
            result = self._window.create_file_dialog(
                self.webview.FileDialog.OPEN,
                allow_multiple=True,
                file_types=file_types,
            )
            if not result:
                return self._ok(canceled=True)
            return self._ok(files=list(result))
        except Exception as exc:
            return self._fail("打开文件选择器失败", str(exc))

    def import_multi_format_macros(self, file_paths: list):
        try:
            from macro_converter import (
                detect_format,
                create_converter,
                save_macro_rows_with_notes,
            )

            if not isinstance(file_paths, list) or not file_paths:
                return self._fail("未选择文件")

            output_dir = MACRO_ROOT / "导入宏"
            output_dir.mkdir(parents=True, exist_ok=True)

            results = []
            for raw_path in file_paths:
                src = Path(raw_path)
                file_result = {
                    "file": src.name,
                    "status": "pending",
                    "message": "",
                    "output": "",
                }

                if not src.exists():
                    file_result["status"] = "failed"
                    file_result["message"] = "文件不存在"
                    results.append(file_result)
                    continue

                try:
                    source_text = src.read_text(encoding="utf-8")
                except Exception as read_err:
                    file_result["status"] = "failed"
                    file_result["message"] = f"读取失败: {read_err}"
                    results.append(file_result)
                    continue

                fmt = detect_format(str(src), source_text)
                if fmt is None:
                    file_result["status"] = "skipped"
                    file_result["message"] = f"无法识别格式 (扩展名: {src.suffix or '无'})"
                    results.append(file_result)
                    continue

                try:
                    converter = create_converter(fmt)
                    rows = converter.convert(source_text)
                except Exception as conv_err:
                    file_result["status"] = "failed"
                    file_result["message"] = f"转换失败({fmt}): {conv_err}"
                    results.append(file_result)
                    continue

                target = output_dir / f"{src.stem}.json"
                if target.exists():
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    target = output_dir / f"{src.stem}_{stamp}.json"

                try:
                    save_macro_rows_with_notes(target, rows)
                except Exception as save_err:
                    file_result["status"] = "failed"
                    file_result["message"] = f"保存失败: {save_err}"
                    results.append(file_result)
                    continue

                file_result["status"] = "success"
                file_result["message"] = converter.summary()
                file_result["output"] = target.relative_to(BASE_DIR).as_posix()
                results.append(file_result)

            success_count = sum(1 for r in results if r["status"] == "success")
            skipped_count = sum(1 for r in results if r["status"] == "skipped")
            failed_count = sum(1 for r in results if r["status"] == "failed")

            return self._ok(
                results=results,
                success_count=success_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
            )
        except Exception as exc:
            return self._fail("多格式导入失败", str(exc))

    _EXPORT_EXT_TO_FMT: dict[str, str] = {
        ".json": "original",
        ".xml": "razer",
        ".lua": "logitech",
        ".ahk": "ahk",
        ".xmbcs": "xmouse",
    }

    def choose_export_path(self, rel_path: str):
        try:
            if self._window is None:
                return self._fail("窗口未就绪")

            src_path = macro_abs_from_rel(rel_path)
            if not src_path.exists():
                return self._fail("宏文件不存在")

            stem = src_path.stem

            file_types = (
                "原始版 JSON (*.json)",
                "Razer XML (*.xml)",
                "Logitech Lua (*.lua)",
                "AutoHotkey (*.ahk)",
                "XMouse (*.xmbcs)",
            )

            result = self._window.create_file_dialog(
                self.webview.FileDialog.SAVE,
                allow_multiple=False,
                file_types=file_types,
                save_filename=stem + ".json",
            )
            if not result:
                return self._ok(canceled=True)
            # SAVE 对话框返回 str，不是 tuple。原先写 result[0] 会取到路径首字符
            # （例如 "C"），导出时把文件写到工作目录下名为 "C" 的文件，UI 却提示"已导出"。
            # 注意：FOLDER/OPEN 对话框返回的是 tuple，那里的 result[0] 是对的，不要改。
            path = result if isinstance(result, str) else (result[0] if result else "")
            return self._ok(path=path)
        except Exception as exc:
            return self._fail("打开保存对话框失败", str(exc))

    def export_macro(self, rel_path: str, save_path: str, ahk_v2: bool = False, razer_v3: bool = False,
                     logitech_ghub: bool = True, fps: int | None = None):
        try:
            src_path = macro_abs_from_rel(rel_path)
            if not src_path.exists():
                return self._fail("宏文件不存在")

            target = Path(save_path)
            ext = target.suffix.lower()
            fmt = self._EXPORT_EXT_TO_FMT.get(ext, "original")

            if fmt == "original":
                from macro_converter import (
                    _load_json_with_comments,
                    resolve_imports,
                    save_macro_rows_with_notes,
                )

                try:
                    parsed = _load_json_with_comments(src_path)
                except json.JSONDecodeError as exc:
                    return self._fail("无法解析JSON源文件", str(exc))

                if not isinstance(parsed, list):
                    return self._fail("JSON源文件顶层必须是数组")

                import_warnings: list[str] = []
                base_dir = os.path.dirname(str(src_path))
                parsed = resolve_imports(parsed, base_dir, warnings=import_warnings)

                target.parent.mkdir(parents=True, exist_ok=True)
                save_macro_rows_with_notes(target, parsed)

                return self._ok(
                    file=target.name,
                    path=str(target),
                    format="original",
                    warnings=import_warnings,
                )

            from macro_converter import (
                _load_json_with_comments,
                create_exporter,
                resolve_imports,
                _has_frame_delay,
                _count_frame_delays,
            )

            try:
                parsed = _load_json_with_comments(src_path)
            except json.JSONDecodeError as exc:
                return self._fail("无法解析JSON源文件", str(exc))

            if not isinstance(parsed, list):
                return self._fail("JSON源文件顶层必须是数组")

            import_warnings: list[str] = []
            base_dir = os.path.dirname(str(src_path))
            parsed = resolve_imports(parsed, base_dir, warnings=import_warnings)

            # 含 f 帧延迟且未提供 fps → 请求前端弹窗输入帧率
            if fps is None and _has_frame_delay(parsed):
                return self._ok(
                    need_fps=True,
                    f_count=_count_frame_delays(parsed),
                )

            is_v2 = (fmt == "ahk" and ahk_v2)
            synapse_version = 3 if (fmt == "razer" and razer_v3) else 4
            is_ghub = (fmt == "logitech" and logitech_ghub)
            exporter = create_exporter(fmt, parsed, is_v2=is_v2, synapse_version=synapse_version,
                                       logitech_ghub=is_ghub, fps=fps)
            output_text = exporter.export()

            all_warnings = import_warnings + exporter.warnings

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(output_text, encoding="utf-8")

            format_label = fmt
            if is_v2:
                format_label = "ahk_v2"
            elif fmt == "razer" and razer_v3:
                format_label = "razer_v3"
            elif fmt == "logitech":
                format_label = "logitech_ghub" if logitech_ghub else "logitech_lgs"

            return self._ok(
                file=target.name,
                path=str(target),
                format=format_label,
                warnings=all_warnings,
            )
        except Exception as exc:
            return self._fail("导出宏失败", str(exc))
