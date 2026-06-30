# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any

from core.response import ok, fail


class ConverterApiMixin:

    def converter_detect(self, source_text: str) -> dict:
        try:
            import macro_converter as mc
            fmt = mc.detect_format_by_content(source_text)
            return ok(format=fmt or "unknown")
        except Exception as exc:
            return fail(str(exc))

    def converter_convert(
        self,
        source_text: str,
        src_fmt: str = "auto",
        dst_fmt: str = "webui",
        fps: int = 60,
        ahk_v2: bool = False,
        synapse_version: int = 4,
        logitech_ghub: bool = True,
    ) -> dict:
        try:
            import macro_converter as mc

            if src_fmt == "auto":
                detected = mc.detect_format_by_content(source_text)
                if detected is None:
                    return fail("无法自动识别格式，请手动选择源格式")
                src_fmt = detected
            detected_fmt = src_fmt

            # 第一步：解析源文本 → WebUI rows
            if src_fmt == "webui":
                rows = mc._parse_jsonc_str(source_text)
                if not isinstance(rows, list):
                    return fail("WebUI JSON 格式错误：顶层应为数组")
            else:
                converter = mc.create_converter(src_fmt)
                rows = converter.convert(source_text)

            # 第二步：导出到目标格式
            if dst_fmt == "webui":
                normalized = mc._normalize_rows_for_save(rows)
                lines = ["["]
                lines.extend(mc._serialize_rows_with_notes(normalized, indent_level=1))
                lines.append("]")
                output = "\n".join(lines) + "\n"
                return ok(output=output, detected_fmt=detected_fmt, warnings=[])

            if dst_fmt == "webui_frame":
                exporter = mc.WebUIFrameExporter(rows, fps=fps)
                output = exporter.export()
                return ok(output=output, detected_fmt=detected_fmt, warnings=exporter.warnings)

            exporter = mc.create_exporter(
                dst_fmt, rows,
                is_v2=bool(ahk_v2),
                fps=fps,
                synapse_version=int(synapse_version),
                logitech_ghub=bool(logitech_ghub),
            )
            if dst_fmt == "xmouse_dsl":
                output = exporter.export_dsl()
            else:
                output = exporter.export()
            return ok(output=output, detected_fmt=detected_fmt, warnings=exporter.warnings)

        except Exception as exc:
            return fail(str(exc))

    def converter_reframe(
        self,
        source_text: str,
        src_fps: int,
        dst_fps: int,
    ) -> dict:
        try:
            import macro_converter as mc

            rows = mc._parse_jsonc_str(source_text)
            if not isinstance(rows, list):
                return fail("输入应为 WebUI JSON 格式（顶层数组）")

            converted = _reframe_rows(rows, int(src_fps), int(dst_fps), mc)
            normalized = mc._normalize_rows_for_save(converted)
            lines = ["["]
            lines.extend(mc._serialize_rows_with_notes(normalized, indent_level=1))
            lines.append("]")
            return ok(output="\n".join(lines) + "\n")

        except Exception as exc:
            return fail(str(exc))


def _reframe_rows(rows: list, src_fps: int, dst_fps: int, mc: Any) -> list:
    src_ms = 1000.0 / max(1, src_fps)
    dst_ms = 1000.0 / max(1, dst_fps)
    result = []
    for row in rows:
        if not isinstance(row, list) or not row:
            result.append(row)
            continue
        cmd = str(row[0]).strip().lower()
        if cmd == "loop" and len(row) >= 3 and isinstance(row[2], list):
            result.append([row[0], row[1], _reframe_rows(row[2], src_fps, dst_fps, mc)])
            continue
        idx = mc._DELAY_INDEX.get(cmd)
        if idx is not None and len(row) > idx:
            val = row[idx]
            if mc._is_frame_delay_str(val):
                n_src = int(str(val).strip()[:-1])
                n_dst = round(n_src * src_ms / dst_ms)
                new_row = list(row)
                new_row[idx] = f"{n_dst}f" if n_dst >= 1 else int(round(n_src * src_ms))
                result.append(new_row)
                continue
        result.append(row)
    return result
