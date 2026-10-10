# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any, Dict


from core.param_helpers import coerce_value, friendly_value, resolve_attr_target


class ParamsApiMixin:
    def _module_by_section(self, section: str):
        source = self.SECTION_META.get(section, {}).get("source")
        if source == "executor":
            return self.executor
        if source == "recorder":
            return self.recorder
        if source == "simplify_tool":
            return self.simplify_tool
        if source == "interception":
            return self.interception
        if source == "bridge":
            return self
        return None

    def _get_schema_value(self, section: str, key: str):
        module = self._module_by_section(section)
        if module is None:
            raise ValueError(f"未找到 section 对应模块: {section}")
        target, leaf = resolve_attr_target(module, key)
        return getattr(target, leaf)

    def _set_schema_value(self, section: str, key: str, value: Any):
        module = self._module_by_section(section)
        if module is None:
            raise ValueError(f"未找到 section 对应模块: {section}")

        target, leaf = resolve_attr_target(module, key)
        current_value = getattr(target, leaf)
        target_type = self.PARAM_SCHEMA[section][key]["type"]
        casted = coerce_value(value, target_type)

        if isinstance(current_value, set) and not isinstance(casted, set):
            casted = set(casted)

        setattr(target, leaf, casted)
        return casted

    def _collect_param_snapshot(self, include_debug: bool = True):
        payload: Dict[str, Dict[str, Any]] = {}
        for section, fields in self.PARAM_SCHEMA.items():
            section_values: Dict[str, Any] = {}
            for key, meta in fields.items():
                if not include_debug and meta.get("tier") == "debug":
                    continue
                try:
                    value = friendly_value(self._get_schema_value(section, key))
                except Exception:
                    continue
                if isinstance(value, (dict, list)):
                    section_values[key] = copy.deepcopy(value)
                else:
                    section_values[key] = value
            payload[section] = section_values
        return payload

    def _save_param_config_to_disk(self, values: Dict[str, Dict[str, Any]]):
        data = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "values": values,
        }
        self.param_config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _extract_param_values_from_obj(self, obj: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        if "values" in obj and isinstance(obj["values"], dict):
            return obj["values"]
        if all(isinstance(v, dict) for v in obj.values()):
            return obj
        raise ValueError("参数文件格式错误，应为 {values:{...}} 或按 section 分组对象")

    def _load_param_config_from_disk(self) -> bool:
        if not self.param_config_path.exists():
            return False
        try:
            raw = self.param_config_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            values = self._extract_param_values_from_obj(data)
            self.update_global_params(values, save_to_disk=False)
            self.console.push(f"参数已从配置文件加载: {self.param_config_path.name}", "stdout")
            return True
        except Exception as exc:
            self.console.push(f"参数配置加载失败，已忽略: {exc}", "stderr")
            return False

    def get_global_params(self):
        sections = {}
        defaults = self._default_param_values
        for section, fields in self.PARAM_SCHEMA.items():
            section_meta = self.SECTION_META.get(section, {})
            rows = []
            for key, meta in fields.items():
                try:
                    value = friendly_value(self._get_schema_value(section, key))
                except Exception:
                    continue

                default_section = defaults.get(section, {}) if isinstance(defaults, dict) else {}
                default_value = friendly_value(default_section.get(key)) if key in default_section else friendly_value(value)

                rows.append(
                    {
                        "key": key,
                        "field_id": f"{section}.{key}",
                        "type": meta["type"],
                        "label": meta["label"],
                        "hint": meta.get("hint", ""),
                        "desc": self.PARAM_DOCS.get(f"{section}.{key}", {}).get("desc", ""),
                        "recommend": self.PARAM_DOCS.get(f"{section}.{key}", {}).get("recommend", ""),
                        "example": self.PARAM_DOCS.get(f"{section}.{key}", {}).get("example", ""),
                        "tier": meta.get("tier", "basic"),
                        "options": meta.get("options", []),
                        "display_names": meta.get("display_names", {}),
                        "depends_on": meta.get("depends_on", []),
                        "value": value,
                        "default": default_value,
                    }
                )

            sections[section] = {
                "title": section_meta.get("title", section),
                "rows": rows,
            }

        return self._ok(sections=sections, config_path=str(self.param_config_path), has_config=self.param_config_path.exists())

    def update_global_params(self, payload: Dict[str, Dict[str, Any]], save_to_disk: bool = True):
        try:
            if not isinstance(payload, dict):
                return self._fail("参数必须是对象")

            # 精度档位优先处理：它是一组参数的联动预设，
            # 必须后于它的单参数覆盖之前写入，否则会被随后的旧值盖掉。
            profile_result = None
            exec_payload = payload.get("executor") or {}
            if isinstance(exec_payload, dict) and "PRECISION_PROFILE" in exec_payload:
                profile_result = self._apply_precision_profile(exec_payload["PRECISION_PROFILE"])

            for section, section_values in payload.items():
                if section not in self.PARAM_SCHEMA:
                    continue
                if not isinstance(section_values, dict):
                    continue

                schema = self.PARAM_SCHEMA[section]

                for key, value in section_values.items():
                    if key not in schema:
                        continue
                    # 档位已写入的值不再被同一次提交里的旧快照覆盖
                    if (profile_result and section == "executor"
                            and key in profile_result.get("applied", {})):
                        continue
                    self._set_schema_value(section, key, value)

            # 进程优先级档位 / 共享帧缓存 TTL
            if isinstance(exec_payload, dict):
                self._apply_engine_level_knobs(exec_payload)

            if save_to_disk:
                self._save_param_config_to_disk(self._collect_param_snapshot(include_debug=True))

            if "automation_editor" in payload:
                try:
                    self._restart_editor_hotkey_listener()
                except Exception:
                    pass

            extra = {}
            if profile_result:
                extra["precision_profile"] = profile_result
            return self._ok(message="参数更新完成", saved=bool(save_to_disk), **extra)
        except Exception as exc:
            return self._fail("更新全局参数失败", str(exc))

    # ------------------------------------------------------------------
    # 精度档位
    # ------------------------------------------------------------------
    def _precision_engine_module(self):
        try:
            from engine import precision as _pr
            return _pr
        except Exception:
            return None

    def _apply_precision_profile(self, profile_name: str) -> dict:
        """应用精度/占用档位预设。"""
        try:
            from core.precision_profile import apply_precision_profile
        except Exception as exc:
            return {"applied": {}, "engine": {}, "profile": profile_name, "error": str(exc)}
        result = apply_precision_profile(
            profile_name,
            executor_module=self.executor,
            engine_module=self._precision_engine_module(),
        )
        if result.get("applied"):
            self.console.push(
                f"[参数] 已应用精度档位「{profile_name}」，联动 {len(result['applied'])} 项参数"
            )
        return result

    def _apply_engine_level_knobs(self, exec_payload: dict):
        """应用进程优先级档位与共享帧缓存 TTL。"""
        pr = self._precision_engine_module()
        tier = exec_payload.get("PROCESS_PRIORITY_TIER")
        if tier and pr is not None:
            try:
                pr.set_process_priority_tier(str(tier))
            except Exception:
                pass
        ttl = exec_payload.get("DETECTION_FRAME_CACHE_TTL_MS")
        if ttl is not None:
            try:
                from core.precision_profile import set_default_frame_cache_ttl
                set_default_frame_cache_ttl(float(ttl or 0))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 热键冲突检测
    # ------------------------------------------------------------------
    HOTKEY_KEYS = {
        "executor": [
            ("GLOBAL_PAUSE_TOGGLE_KEY", "宏执行·全局暂停/恢复"),
            ("STOP_MACRO_KEY", "宏执行·停止全部宏"),
            ("MACRO_RELOAD_KEY", "宏执行·宏重载"),
        ],
        "recorder": [
            ("RECORD_ARM_HOTKEY", "录制·布防/开始"),
            ("RECORD_STOP_HOTKEY", "录制·停止"),
            ("RECORD_SAVE_HOTKEY", "录制·保存"),
            ("RECORD_CLEAR_HOTKEY", "录制·清空"),
        ],
        "automation_editor": [
            ("HOTKEY_RUN", "自动化编辑器·运行"),
            ("HOTKEY_PAUSE", "自动化编辑器·暂停"),
            ("HOTKEY_STOP", "自动化编辑器·停止"),
            ("HOTKEY_FULLSCREEN", "自动化编辑器·全屏"),
        ],
    }

    def get_hotkey_conflicts(self):
        """收集全部全局热键并报告互相冲突的按键。

        F8 同时被「宏执行暂停」「录制停止」「编辑器停止」占用，
        F7/F10 也各有两处冲突，但项目此前完全没有冲突检测，
        用户按键后行为取决于注册顺序，且首个注册者之后的全被静默丢弃。
        """
        try:
            collected = {}
            for section, keys in self.HOTKEY_KEYS.items():
                module = self._module_by_section(section)
                if module is None:
                    continue
                for key, label in keys:
                    try:
                        target, leaf = resolve_attr_target(module, key)
                        raw = getattr(target, leaf, None)
                    except Exception:
                        continue
                    if raw is None:
                        continue
                    name = str(raw).strip().lower()
                    if not name or name in ("", "none"):
                        continue
                    collected.setdefault(name, []).append(
                        {"section": section, "key": key, "label": label, "value": str(raw)}
                    )
            conflicts = [
                {"key": k, "users": v}
                for k, v in collected.items() if len(v) > 1
            ]
            conflict_keys = {c["key"] for c in conflicts}
            # 扁平的绑定清单（按分组排序），供「快捷键速查」表格按真实配置渲染
            flat = []
            for name, users in collected.items():
                for u in users:
                    flat.append({**u, "conflict": name in conflict_keys})
            flat.sort(key=lambda x: (x["section"], x["key"]))
            return self._ok(conflicts=conflicts, hotkeys=collected, flat=flat)
        except Exception as exc:
            return self._fail("检测热键冲突失败", str(exc))

    def get_engine_summary(self):
        """汇总「当前实际生效」的引擎状态，供界面明示。

        这些开关此前只能改、看不到结果：用户改了精度档位/Standby 开关后，
        既不知道联动到了什么，也不知道 native 引擎到底加载没加载
        （standby .pyd 缺失时会静默回退 Python 路径）。这里把生效值摊开给用户看。
        """
        try:
            ex = self.executor
            profile = getattr(ex, "PRECISION_PROFILE", None) if ex is not None else None
            try:
                from core.precision_profile import get_profile_names, DEFAULT_PRECISION_PROFILE
                labels = {p["name"]: p["label"] for p in get_profile_names()}
            except Exception:
                labels, DEFAULT_PRECISION_PROFILE = {}, "balanced"
            if not profile:
                profile = DEFAULT_PRECISION_PROFILE

            standby_enabled = bool(getattr(ex, "ENABLE_STANDBY_ENGINE", False)) if ex is not None else False
            standby_available = None
            if ex is not None and hasattr(ex, "_standby_available"):
                try:
                    standby_available = bool(ex._standby_available())
                except Exception:
                    standby_available = None

            pr = self._precision_engine_module()
            priority_tier = getattr(ex, "PROCESS_PRIORITY_TIER", None) if ex is not None else None
            priority_now = None
            if pr is not None:
                try:
                    cur = pr.get_process_priority()
                    reverse = {v: k for k, v in getattr(pr, "PROCESS_PRIORITY_TIERS", {}).items()}
                    priority_now = reverse.get(cur, str(cur))
                except Exception:
                    priority_now = None

            try:
                from core.precision_profile import get_default_frame_cache_ttl
                frame_ttl = get_default_frame_cache_ttl()
            except Exception:
                frame_ttl = 0.0

            return self._ok(
                precision_profile=profile,
                precision_profile_label=labels.get(profile, profile),
                standby_enabled=standby_enabled,
                standby_available=standby_available,
                standby_effective=bool(standby_enabled and (standby_available is not False)),
                process_priority_tier=priority_tier,
                process_priority_now=priority_now,
                frame_cache_ttl_ms=frame_ttl,
            )
        except Exception as exc:
            return self._fail("读取引擎状态失败", str(exc))

    def get_precision_profiles(self):
        """供前端渲染档位下拉框。"""
        try:
            from core.precision_profile import get_profile_names, DEFAULT_PRECISION_PROFILE
            current = getattr(self.executor, "PRECISION_PROFILE", DEFAULT_PRECISION_PROFILE) \
                if self.executor is not None else DEFAULT_PRECISION_PROFILE
            return self._ok(profiles=get_profile_names(), current=str(current))
        except Exception as exc:
            return self._fail("读取精度档位失败", str(exc))

    def choose_param_import_file(self):
        try:
            if self._window is None:
                return self._fail("窗口未就绪")
            result = self._window.create_file_dialog(self.webview.FileDialog.OPEN, allow_multiple=False)
            if not result:
                return self._ok(canceled=True)
            return self._ok(path=str(result[0]))
        except Exception as exc:
            return self._fail("打开参数文件失败", str(exc))

    def choose_param_export_file(self):
        try:
            if self._window is None:
                return self._fail("窗口未就绪")
            result = self._window.create_file_dialog(
                self.webview.SAVE_DIALOG,
                allow_multiple=False,
                save_filename="参数配置.json",
            )
            if not result:
                return self._ok(canceled=True)
            path = result if isinstance(result, str) else result[0]
            return self._ok(path=str(path))
        except Exception as exc:
            return self._fail("打开导出路径失败", str(exc))

    def export_global_params(self, output_path: str):
        try:
            path = Path(str(output_path).strip())
            if not path.suffix:
                path = path.with_suffix(".json")
            data = {
                "version": 1,
                "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "values": self._collect_param_snapshot(include_debug=True),
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._ok(path=str(path))
        except Exception as exc:
            return self._fail("导出参数失败", str(exc))

    def import_global_params(self, input_path: str):
        try:
            path = Path(str(input_path).strip())
            if not path.exists():
                return self._fail("参数文件不存在")
            data = json.loads(path.read_text(encoding="utf-8"))
            values = self._extract_param_values_from_obj(data)
            ret = self.update_global_params(values, save_to_disk=True)
            if not ret.get("ok"):
                return ret
            return self._ok(path=str(path), message="参数导入成功，已覆盖 config")
        except Exception as exc:
            return self._fail("导入参数失败", str(exc))

    def reset_global_params_to_default(self):
        try:
            values = copy.deepcopy(self._default_param_values)
            ret = self.update_global_params(values, save_to_disk=True)
            if not ret.get("ok"):
                return ret
            return self._ok(message="已恢复默认参数并覆盖 config")
        except Exception as exc:
            return self._fail("恢复默认参数失败", str(exc))

    def get_macro_runtime_profile(self):
        return self._ok(
            speed_factor=float(self.executor.EXEC_SPEED_FACTOR),
            random_enabled=bool(self.executor.ENABLE_RUNTIME_RANDOM_OFFSET),
            random_min_ms=float(self.executor.RUNTIME_RANDOM_OFFSET_MIN_MS),
            random_max_ms=float(self.executor.RUNTIME_RANDOM_OFFSET_MAX_MS),
            low_cpu_enabled=bool(getattr(self.executor, "ENABLE_LOW_CPU_EXECUTION", False)),
            low_cpu_time_period=bool(getattr(self.executor, "LOW_CPU_ENABLE_TIME_PERIOD", True)),
        )

    def update_macro_runtime_profile(self, payload: Dict[str, Any]):
        try:
            if not isinstance(payload, dict):
                return self._fail("参数必须为对象")

            if "speed_factor" in payload:
                self.executor.EXEC_SPEED_FACTOR = max(0.05, float(payload.get("speed_factor", 1.0)))
            if "random_enabled" in payload:
                self.executor.ENABLE_RUNTIME_RANDOM_OFFSET = bool(payload.get("random_enabled"))
            if "random_min_ms" in payload:
                self.executor.RUNTIME_RANDOM_OFFSET_MIN_MS = float(payload.get("random_min_ms", 0.0))
            if "random_max_ms" in payload:
                self.executor.RUNTIME_RANDOM_OFFSET_MAX_MS = float(payload.get("random_max_ms", 0.0))
            if "low_cpu_enabled" in payload:
                self.executor.ENABLE_LOW_CPU_EXECUTION = bool(payload.get("low_cpu_enabled"))
            if "low_cpu_time_period" in payload:
                self.executor.LOW_CPU_ENABLE_TIME_PERIOD = bool(payload.get("low_cpu_time_period"))

            self._save_param_config_to_disk(self._collect_param_snapshot(include_debug=True))
            return self.get_macro_runtime_profile()
        except Exception as exc:
            return self._fail("更新执行配置失败", str(exc))
