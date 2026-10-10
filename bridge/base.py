import importlib
import importlib.util
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from core.paths import BASE_DIR
from core.console_service import RingConsole, TeeStream
from core.response import ok, fail

from bridge.metadata import PARAM_DOCS, PARAM_SCHEMA, SECTION_META


def _load_module(alias: str, file_name: str):
    file_path = BASE_DIR / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"模块文件不存在: {file_name}")

    spec = importlib.util.spec_from_file_location(alias, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块: {file_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


class MacroBridgeBase:
    BASE_DIR = BASE_DIR
    SECTION_META = SECTION_META
    PARAM_DOCS = PARAM_DOCS
    PARAM_SCHEMA = PARAM_SCHEMA

    def __init__(self):
        self.ALLOW_MULTI_MACRO_BIND_PER_KEY = False

        # 自动化编辑器热键设置
        self.HOTKEY_ENABLED = True
        self.HOTKEY_RUN = "F5"
        self.HOTKEY_PAUSE = "F6"
        self.HOTKEY_STOP = "F7"
        self.HOTKEY_FULLSCREEN = "F11"

        self.console = RingConsole(max_lines=6000)
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = TeeStream(self._stdout, self.console, "stdout")
        sys.stderr = TeeStream(self._stderr, self.console, "stderr")

        self.executor = None
        try:
            self.executor = _load_module("macro_executor_v23", "宏执行框架3.2.py")
        except Exception as exc:
            self.console.push(f"宏执行框架加载失败: {exc}", "stderr")

        self.recorder = None
        try:
            from recorder import recorder_3d as _rec_mod
            self.recorder = _rec_mod
        except Exception as exc:
            self.console.push(f"录制模块加载失败: {exc}", "stderr")

        self.simplify_tool = None
        try:
            from recorder import simplify_tool as _simp_mod
            self.simplify_tool = _simp_mod
        except Exception as exc:
            self.console.push(f"化简工具加载失败: {exc}", "stderr")

        if self.recorder is not None:
            recorder_hotkey_defaults = {
                "RECORD_TOGGLE_LISTENER_HOTKEY": "不可使用！",
                "RECORD_ARM_HOTKEY": "f7",
                "RECORD_STOP_HOTKEY": "f8",
                "RECORD_SAVE_HOTKEY": "f9",
                "RECORD_CLEAR_HOTKEY": "f10",
                "ENABLE_RECORD_HOTKEY_ACTIONS": False,
            }
            for key, value in recorder_hotkey_defaults.items():
                if not hasattr(self.recorder, key):
                    setattr(self.recorder, key, value)

        self.interception = None
        try:
            from engine import input_interception as _ic_mod
            self.interception = _ic_mod
        except Exception as exc:
            self.console.push(f"Interception 模块加载失败: {exc}", "stderr")

        self._window: Optional[object] = None
        self._bridge_lock = threading.Lock()

        self._listener_thread: Optional[threading.Thread] = None
        self._record_key_listener = None
        self._record_mouse_listener = None
        self.param_config_path = BASE_DIR / "webui_param_config.json"
        self._default_param_values = self._collect_param_snapshot(include_debug=True)

        loaded = self._load_param_config_from_disk()
        if not loaded:
            self._save_param_config_to_disk(self._default_param_values)

        self.console.push("PyWebView 桥接已初始化", "stdout")

    def set_window(self, window) -> None:
        self._window = window

    def _ok(self, **kwargs):
        return ok(**kwargs)

    def _fail(self, message: str, detail: Optional[str] = None):
        return fail(message, detail)

    def health(self):
        return self._ok(version="1.0.0", now=time.strftime("%Y-%m-%d %H:%M:%S"))

    def get_dashboard_snapshot(self):
        if self.executor is None:
            return self._ok(active_macros=0, global_paused=False, cache_loading=False, recording={})
        with self.executor.active_macros_lock:
            active_count = 0
            for info in self.executor.active_macros.values():
                stop_event = info.get("stop_event")
                thread = info.get("thread")
                if stop_event is not None and stop_event.is_set():
                    continue
                if thread is not None and not thread.is_alive():
                    continue
                active_count += 1
            paused = self.executor.global_trigger_paused
            loading = self.executor.macro_loading_in_progress
        rec_state = self.get_recording_state()
        return self._ok(
            active_macros=active_count,
            global_paused=paused,
            cache_loading=loading,
            recording=rec_state.get("recording", {}),
        )

    def poll_console(self, last_id: int = 0, limit: int = 300):
        return self._ok(**self.console.poll(last_id=last_id, limit=limit))

    def clear_console(self):
        return self.console.clear()

    def shutdown(self):
        try:
            self.stop_all_macros()
        except Exception:
            pass
        try:
            self.stop_global_listeners()
        except Exception:
            pass
        try:
            self.stop_recorder_service()
        except Exception:
            pass

    def _collect_param_snapshot(self, include_debug: bool = True):
        from core.param_helpers import friendly_value, resolve_attr_target
        import copy

        payload = {}
        for section, fields in self.PARAM_SCHEMA.items():
            section_values = {}
            for key, meta in fields.items():
                if not include_debug and meta.get("tier") == "debug":
                    continue
                try:
                    module = self._module_by_section(section)
                    if module is None:
                        continue
                    target, leaf = resolve_attr_target(module, key)
                    value = friendly_value(getattr(target, leaf))
                except Exception:
                    continue
                if isinstance(value, (dict, list)):
                    section_values[key] = copy.deepcopy(value)
                else:
                    section_values[key] = value
            payload[section] = section_values
        return payload

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

    def _save_param_config_to_disk(self, values):
        import json
        data = {
            "version": 1,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "values": values,
        }
        self.param_config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_param_config_from_disk(self) -> bool:
        if not self.param_config_path.exists():
            return False
        try:
            import json
            raw = self.param_config_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            values = self._extract_param_values_from_obj(data)
            self.update_global_params(values, save_to_disk=False)
            self.console.push(f"参数已从配置文件加载: {self.param_config_path.name}", "stdout")
            return True
        except Exception as exc:
            self.console.push(f"参数配置加载失败，已忽略: {exc}", "stderr")
            return False

    def _extract_param_values_from_obj(self, obj):
        if "values" in obj and isinstance(obj["values"], dict):
            return obj["values"]
        if all(isinstance(v, dict) for v in obj.values()):
            return obj
        raise ValueError("参数文件格式错误")

    def _persist_param_config(self):
        self._save_param_config_to_disk(self._collect_param_snapshot(include_debug=True))
