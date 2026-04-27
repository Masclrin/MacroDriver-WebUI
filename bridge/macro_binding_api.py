# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import threading
from typing import Any, Dict, List, Optional

from pynput import keyboard, mouse

try:
    from macro_io.parser import safe_rel, macro_abs_from_rel
    _has_macro_io = True
except ImportError:
    _has_macro_io = False


class MacroBindingApiMixin:
    def _require_executor(self):
        if self.executor is None:
            raise RuntimeError("宏执行框架不可用")

    def _binding_runtime(self, trigger_key: str) -> Dict[str, Any]:
        self._require_executor()
        live = self.executor._collect_live_macro_infos(trigger_key)
        running = [
            info for info in live
            if not (info.get("stop_event") is not None and info["stop_event"].is_set())
        ]
        return {
            "live_count": len(running),
            "stopping_count": max(0, len(live) - len(running)),
            "paused_count": sum(1 for info in running if info.get("pause_event") is not None and info["pause_event"].is_set()),
        }

    def _normalize_binding_paths(self, value: Any) -> List[str]:
        if hasattr(self.executor, "normalize_binding_macro_paths"):
            try:
                return list(self.executor.normalize_binding_macro_paths(value))
            except Exception:
                pass

        if value is None:
            return []
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple, set)):
            items = list(value)
        else:
            items = [str(value)]

        out: List[str] = []
        seen = set()
        for item in items:
            path = str(item).strip()
            if not path or path in seen:
                continue
            seen.add(path)
            out.append(path)
        return out

    def _refresh_binding_cache(self, trigger_key: str, reason: str = "绑定更新") -> None:
        if hasattr(self.executor, "refresh_compiled_cache_for_trigger"):
            self.executor.refresh_compiled_cache_for_trigger(trigger_key, reason=reason)

    def _invalidate_binding_cache(self, trigger_key: str) -> None:
        if hasattr(self.executor, "invalidate_compiled_cache_for_trigger"):
            self.executor.invalidate_compiled_cache_for_trigger(trigger_key)
            return
        with self.executor.macro_cache_lock:
            self.executor.compiled_macro_cache.pop(trigger_key, None)

    def list_bindings(self):
        self._require_executor()
        rows = []
        for trigger, raw_value in sorted(self.executor.MACRO_BINDINGS.items(), key=lambda x: str(x[0])):
            macro_paths = self._normalize_binding_paths(raw_value)
            if not macro_paths:
                continue
            cfg = self.executor.resolve_macro_config(trigger)
            runtime = self._binding_runtime(trigger)
            rows.append(
                {
                    "trigger": trigger,
                    "macro_path": macro_paths[0],
                    "macro_paths": macro_paths,
                    "macro_count": len(macro_paths),
                    "repeat": cfg["repeat_count"] if cfg else 1,
                    "running_press_mode": cfg["running_press_mode"] if cfg else "normal",
                    **runtime,
                }
            )
        return self._ok(items=rows)

    def bind_macro(self, trigger: str, macro_rel_path: str, repeat: int = 1, running_press_mode: str = "normal"):
        self._require_executor()
        if not _has_macro_io:
            return self._fail("宏文件模块不可用")
        try:
            trigger = str(trigger).strip().lower()
            if not trigger:
                return self._fail("触发键不能为空")

            macro_path = safe_rel(macro_rel_path)
            if not macro_abs_from_rel(macro_path).exists():
                return self._fail("宏文件不存在")

            valid_modes = self.executor.VALID_RUNNING_PRESS_MODES
            mode = str(running_press_mode).strip().lower()
            if mode not in valid_modes:
                mode = "normal"

            old_binding = copy.deepcopy(self.executor.MACRO_BINDINGS.get(trigger))
            old_runtime = copy.deepcopy(self.executor.MACRO_RUNTIME_SETTINGS.get(trigger))

            existing_paths = self._normalize_binding_paths(self.executor.MACRO_BINDINGS.get(trigger))
            already_bound = macro_path in existing_paths
            allow_multi = bool(getattr(self, "ALLOW_MULTI_MACRO_BIND_PER_KEY", False))
            replaced_existing = False

            if allow_multi:
                if existing_paths:
                    new_paths = list(existing_paths)
                    if not already_bound:
                        new_paths.append(macro_path)
                else:
                    new_paths = [macro_path]
            else:
                new_paths = [macro_path]
                replaced_existing = bool(existing_paths and (len(existing_paths) > 1 or existing_paths[0] != macro_path))

            self.executor.MACRO_BINDINGS[trigger] = new_paths
            self.executor.MACRO_RUNTIME_SETTINGS[trigger] = {
                "repeat": max(1, int(repeat)),
                "running_press_mode": mode,
            }

            try:
                self._refresh_binding_cache(trigger, reason="绑定后立即预编译")
            except Exception:
                if old_binding is None:
                    self.executor.MACRO_BINDINGS.pop(trigger, None)
                else:
                    self.executor.MACRO_BINDINGS[trigger] = old_binding

                if old_runtime is None:
                    self.executor.MACRO_RUNTIME_SETTINGS.pop(trigger, None)
                else:
                    self.executor.MACRO_RUNTIME_SETTINGS[trigger] = old_runtime
                raise

            self._persist_param_config()

            return self._ok(
                trigger=trigger,
                macro_path=macro_path,
                macro_paths=new_paths,
                append=bool(allow_multi and existing_paths and not already_bound),
                already_bound=bool(already_bound),
                replaced_existing=replaced_existing,
                multi_bind_enabled=allow_multi,
                running_press_mode=mode,
            )
        except Exception as exc:
            return self._fail("绑定宏失败", str(exc))

    def unbind_macro(self, trigger: str):
        self._require_executor()
        key = str(trigger).strip().lower()
        self.executor.MACRO_BINDINGS.pop(key, None)
        self.executor.MACRO_RUNTIME_SETTINGS.pop(key, None)
        self._invalidate_binding_cache(key)
        self._persist_param_config()
        return self._ok(trigger=key)

    def capture_next_binding(self, timeout_s: float = 8.0):
        self._require_executor()
        timeout_s = max(1.0, min(float(timeout_s), 20.0))
        done = threading.Event()
        result = {"key": None}

        def on_press(key):
            key_name = self.executor.get_pressed_key_name(key)
            if key_name:
                result["key"] = key_name
                done.set()
                return False
            return True

        def on_click(x, y, button, pressed):
            if not pressed:
                return
            if button == mouse.Button.x1:
                result["key"] = "mouse_x1"
                done.set()
                return False
            if button == mouse.Button.x2:
                result["key"] = "mouse_x2"
                done.set()
                return False

        key_listener = keyboard.Listener(on_press=on_press)
        mouse_listener = mouse.Listener(on_click=on_click)
        key_listener.start()
        mouse_listener.start()

        try:
            ok = done.wait(timeout_s)
            if not ok:
                return self._ok(canceled=True)
            return self._ok(key=result["key"])
        finally:
            key_listener.stop()
            mouse_listener.stop()
