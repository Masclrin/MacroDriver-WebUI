from __future__ import annotations

import json
from typing import Any


def coerce_value(value: Any, target_type: str) -> Any:
    if target_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        return text in ("1", "true", "yes", "on", "y")
    if target_type == "int":
        if value is None:
            return 0
        if isinstance(value, str) and not value.strip():
            return 0
        return int(float(value))
    if target_type == "float":
        if value is None:
            return 0.0
        if isinstance(value, str) and not value.strip():
            return 0.0
        return float(value)
    if target_type == "list":
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        text = str(value).strip()
        if not text:
            return []
        if text.startswith("["):
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        return [item.strip() for item in text.split(",") if item.strip()]
    if target_type == "set":
        if isinstance(value, (set, list, tuple)):
            return set(value)
        text = str(value).strip()
        if not text:
            return set()
        if text.startswith("["):
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return set(parsed)
        return {item.strip() for item in text.split(",") if item.strip()}
    if target_type == "json":
        if isinstance(value, (dict, list)):
            return value
        text = str(value).strip()
        if not text:
            return {}
        parsed = json.loads(text)
        if not isinstance(parsed, (dict, list)):
            raise ValueError("json 参数必须是对象或数组")
        return parsed
    return str(value)


def friendly_value(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "name") and isinstance(getattr(value, "name"), str):
        return getattr(value, "name")
    return value


def resolve_attr_target(module: Any, attr_path: str):
    parts = [p for p in str(attr_path).split(".") if p]
    if not parts:
        raise ValueError("属性路径不能为空")
    target = module
    for part in parts[:-1]:
        target = getattr(target, part)
    return target, parts[-1]
