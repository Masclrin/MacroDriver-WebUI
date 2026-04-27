# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time
import traceback
from typing import Optional


class ListenerApiMixin:
    def _require_executor(self):
        if self.executor is None:
            raise RuntimeError("宏执行框架不可用")

    def start_global_listeners(self):
        self._require_executor()
        with self._bridge_lock:
            state = self.executor.get_listener_state() if hasattr(self.executor, "get_listener_state") else {"running": False}
            running = bool(state.get("running"))
            if running and self._listener_thread and self._listener_thread.is_alive():
                return self._ok(already_running=True)

            def _worker():
                try:
                    self.executor.start_listeners()
                except Exception:
                    self.console.push(traceback.format_exc(), "stderr")
                finally:
                    with self._bridge_lock:
                        self._listener_thread = None

            self._listener_thread = threading.Thread(target=_worker, name="MacroGlobalListenerThread", daemon=True)
            self._listener_thread.start()

        return self._ok(started=True)

    def stop_global_listeners(self):
        self._require_executor()
        with self._bridge_lock:
            try:
                if hasattr(self.executor, "request_stop_listeners"):
                    self.executor.request_stop_listeners()
            except Exception as exc:
                return self._fail("停止监听失败", str(exc))

        return self._ok(stopped=True)

    def get_listener_state(self):
        running = False
        try:
            if hasattr(self.executor, "get_listener_state"):
                running = bool(self.executor.get_listener_state().get("running"))
        except Exception:
            running = False
        if not running and self._listener_thread is not None and self._listener_thread.is_alive():
            running = True
        return self._ok(running=running)

    def toggle_global_listeners(self):
        state = self.get_listener_state()
        if not state.get("ok"):
            return state
        if state.get("running"):
            ret = self.stop_global_listeners()
            if not ret.get("ok"):
                return ret
            return self._ok(running=False)

        ret = self.start_global_listeners()
        if not ret.get("ok"):
            return ret
        return self._ok(running=True)

    def toggle_global_pause(self):
        self._require_executor()
        try:
            self.executor.toggle_global_trigger_pause()
            paused = bool(self.executor.global_trigger_paused)
            return self._ok(paused=paused)
        except Exception as exc:
            return self._fail("切换全局暂停失败", str(exc))

    def trigger_macro(self, trigger: str):
        self._require_executor()
        key = str(trigger).strip().lower()
        if not key:
            return self._fail("触发键不能为空")
        self.executor.handle_trigger_press(key)
        return self._ok(trigger=key)

    def stop_all_macros(self):
        self._require_executor()
        self.executor.stop_all_macros("UI 手动停止")
        return self._ok(stopped=True)

    def get_runtime_status(self):
        self._require_executor()
        rows = []
        with self.executor.active_macros_lock:
            for macro_id, info in self.executor.active_macros.items():
                rows.append(
                    {
                        "macro_id": macro_id,
                        "trigger_key": info.get("trigger_key"),
                        "macro_name": info.get("macro_name"),
                        "alive": bool(info.get("thread") and info["thread"].is_alive()),
                        "paused": bool(info.get("pause_event") and info["pause_event"].is_set()),
                    }
                )
            paused = self.executor.global_trigger_paused

        return self._ok(active=rows, global_paused=paused)
