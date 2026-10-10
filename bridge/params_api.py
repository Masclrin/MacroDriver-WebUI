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

            for section, section_values in payload.items():
                if section not in self.PARAM_SCHEMA:
                    continue
                if not isinstance(section_values, dict):
                    continue

                schema = self.PARAM_SCHEMA[section]

                for key, value in section_values.items():
                    if key not in schema:
                        continue
                    self._set_schema_value(section, key, value)

            if save_to_disk:
                self._save_param_config_to_disk(self._collect_param_snapshot(include_debug=True))

            return self._ok(message="参数更新完成", saved=bool(save_to_disk))
        except Exception as exc:
            return self._fail("更新全局参数失败", str(exc))

    def choose_param_import_file(self):
        try:
            if self._window is None:
                return self._fail("窗口未就绪")
            result = self._window.create_file_dialog(self.webview.OPEN_DIALOG, allow_multiple=False)
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
