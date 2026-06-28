# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from pynput import keyboard, mouse


class RecorderApiMixin:
    def _require_recorder(self):
        if self.recorder is None:
            raise RuntimeError("录制模块不可用")

    def _is_recorder_service_running(self) -> bool:
        key_alive = self._record_key_listener is not None and self._record_key_listener.is_alive()
        mouse_alive = self._record_mouse_listener is not None and self._record_mouse_listener.is_alive()
        return bool(key_alive and mouse_alive)

    def get_recorder_service_state(self):
        return self._ok(running=self._is_recorder_service_running())

    def get_record_hotkeys(self):
        self._require_recorder()
        return self._ok(
            toggle_service=str(getattr(self.recorder, "RECORD_TOGGLE_LISTENER_HOTKEY", "不可使用！") or "").strip().lower(),
            arm=str(getattr(self.recorder, "RECORD_ARM_HOTKEY", "f7") or "").strip().lower(),
            stop=str(getattr(self.recorder, "RECORD_STOP_HOTKEY", "f8") or "").strip().lower(),
            save=str(getattr(self.recorder, "RECORD_SAVE_HOTKEY", "f9") or "").strip().lower(),
            clear=str(getattr(self.recorder, "RECORD_CLEAR_HOTKEY", "f10") or "").strip().lower(),
        )

    def start_recorder_service(self):
        self._require_recorder()
        with self._bridge_lock:
            key_alive = self._record_key_listener is not None and self._record_key_listener.is_alive()
            mouse_alive = self._record_mouse_listener is not None and self._record_mouse_listener.is_alive()
            if key_alive and mouse_alive:
                return self._ok(already_running=True, running=True)

            try:
                listener_state = self.executor.get_listener_state() if hasattr(self.executor, "get_listener_state") else {"running": False}
                if bool(listener_state.get("running")) and hasattr(self.executor, "request_stop_listeners"):
                    self.executor.request_stop_listeners()
                    self.console.push("录制启动时已自动关闭宏执行全局监听，避免按键冲突", "stdout")
            except Exception as exc:
                self.console.push(f"自动关闭宏监听失败: {exc}", "stderr")

            self.recorder.set_high_priority()
            self._record_key_listener = keyboard.Listener(
                on_press=self.recorder.on_key_press,
                on_release=self.recorder.on_key_release,
            )
            self._record_mouse_listener = mouse.Listener(
                on_click=self.recorder.on_mouse_click,
                on_move=self.recorder.on_mouse_move,
            )
            self._record_key_listener.start()
            self._record_mouse_listener.start()

        return self._ok(started=True, running=True)

    def stop_recorder_service(self):
        with self._bridge_lock:
            if self._record_key_listener is not None:
                self._record_key_listener.stop()
            if self._record_mouse_listener is not None:
                self._record_mouse_listener.stop()
            self._record_key_listener = None
            self._record_mouse_listener = None
        return self._ok(stopped=True, running=False)

    def arm_recording(self, start_mode: str = "delayed", start_delay_seconds: float = 0.2):
        self._require_recorder()
        try:
            mode = str(start_mode).strip().lower()
            if mode not in ("delayed", "first_event"):
                return self._fail("start_mode 仅支持 delayed 或 first_event")

            with self.recorder.state_lock:
                self.recorder.START_MODE = mode
                self.recorder.START_DELAY_SECONDS = max(0.0, float(start_delay_seconds))
                self.recorder._arm_recording(self.recorder.perf_ns())

            return self._ok(mode=mode, start_delay_seconds=self.recorder.START_DELAY_SECONDS)
        except Exception as exc:
            return self._fail("布防录制失败", str(exc))

    def stop_recording(self):
        self._require_recorder()
        with self.recorder.state_lock:
            self.recorder._stop_recording()
        return self._ok(stopped=True)

    def save_recording(self):
        self._require_recorder()
        try:
            self.recorder.process_and_save()
            return self._ok(saved=True)
        except Exception as exc:
            return self._fail("保存录制失败", str(exc))

    def get_recording_output_targets(self):
        self._require_recorder()
        try:
            out_dir_raw = str(getattr(self.recorder, "OUTPUT_DIR", "宏\录制宏"))
            base_name = str(getattr(self.recorder, "OUTPUT_BASE_NAME", "3d宏")).strip() or "3d宏"
            out_dir = Path(out_dir_raw)
            if not out_dir.is_absolute():
                out_dir = (self.BASE_DIR / out_dir).resolve()

            suffixes = [
                ("full", str(getattr(self.recorder, "SUFFIX_FULL", "_完整"))),
                ("action", str(getattr(self.recorder, "SUFFIX_ACTION", "_仅按键"))),
                ("track", str(getattr(self.recorder, "SUFFIX_TRACK", "_仅轨迹"))),
            ]

            items = []
            for kind, suffix in suffixes:
                abs_path = (out_dir / f"{base_name}{suffix}.json").resolve()
                exists = abs_path.exists()
                row_count = 0
                if exists:
                    try:
                        rows = self.simplify_tool.load_macro(str(abs_path))
                        row_count = len(rows) if isinstance(rows, list) else 0
                    except Exception:
                        row_count = 0

                try:
                    display_path = abs_path.relative_to(self.BASE_DIR.resolve()).as_posix()
                except Exception:
                    display_path = str(abs_path)

                items.append(
                    {
                        "kind": kind,
                        "path": display_path,
                        "exists": exists,
                        "row_count": row_count,
                        "has_content": bool(exists and row_count > 0),
                    }
                )

            return self._ok(items=items)
        except Exception as exc:
            return self._fail("获取录制输出目标失败", str(exc))

    def clear_recording_buffer(self):
        self._require_recorder()
        with self.recorder.state_lock:
            self.recorder.action_events.clear()
            self.recorder.track_events.clear()
            self.recorder.record_start_ns = None
            self.recorder.scheduled_start_ns = None
            self.recorder.is_armed = False
            self.recorder.is_recording = False
        return self._ok(cleared=True)

    def get_recording_state(self):
        if self.recorder is None:
            return self._ok(recording={"is_armed": False, "is_recording": False, "action_count": 0, "track_count": 0, "start_mode": "delayed", "start_delay_seconds": 0.2})
        with self.recorder.state_lock:
            state = {
                "is_armed": bool(self.recorder.is_armed),
                "is_recording": bool(self.recorder.is_recording),
                "action_count": len(self.recorder.action_events),
                "track_count": len(self.recorder.track_events),
                "start_mode": str(self.recorder.START_MODE),
                "start_delay_seconds": float(self.recorder.START_DELAY_SECONDS),
            }
        return self._ok(recording=state)
