import json
import threading
import time
from typing import Optional, List

from pynput import keyboard, mouse


class EditorRecordApiMixin:

    def __init__(self):
        super().__init__()
        self._ed_rec_active = False
        self._ed_rec_lock = threading.Lock()
        self._ed_rec_key_listener: Optional[keyboard.Listener] = None
        self._ed_rec_mouse_listener: Optional[mouse.Listener] = None
        self._ed_rec_actions: List[list] = []
        self._ed_rec_last_cmd: Optional[str] = None
        self._ed_rec_last_key: Optional[str] = None
        self._ed_rec_last_ts_ns: Optional[int] = None
        self._ed_rec_first_event_ns: Optional[int] = None
        self._ed_rec_pressed_keys: set = set()

    def _ed_rec_perf_ns(self) -> int:
        return time.perf_counter_ns()

    def _ed_rec_normalize_key(self, key) -> Optional[str]:
        if isinstance(key, keyboard.Key):
            return key.name
        if isinstance(key, keyboard.KeyCode):
            return key.char.lower() if key.char else None
        return None

    def _ed_rec_normalize_mouse_btn(self, btn: mouse.Button) -> Optional[str]:
        if btn == mouse.Button.left:
            return "left"
        if btn == mouse.Button.right:
            return "right"
        if btn == mouse.Button.middle:
            return "middle"
        return None

    def _ed_rec_push_action(self, cmd: str, key: str, delay_ms: int):
        with self._ed_rec_lock:
            if self._ed_rec_actions:
                last = self._ed_rec_actions[-1]
                if last[0] in ("kd", "ku", "md", "mu") and last[2] == 0:
                    last[2] = delay_ms
            self._ed_rec_actions.append([cmd, key, 0])
        self._ed_rec_notify_frontend(cmd, key, delay_ms)

    def _ed_rec_notify_frontend(self, cmd: str, key: str, prev_delay_ms: int):
        try:
            window = getattr(self, "_window", None)
            if window is None:
                return
            payload = {
                "type": "editor_record_event",
                "cmd": cmd,
                "key": key,
                "prev_delay_ms": prev_delay_ms,
            }
            js_code = (
                "if(window._onEditorRecordEvent)"
                f"window._onEditorRecordEvent({json.dumps(payload)});"
            )
            window.evaluate_js(js_code)
        except Exception:
            pass

    def _ed_rec_on_key_press(self, key):
        try:
            if not self._ed_rec_active:
                return True
            now_ns = self._ed_rec_perf_ns()
            key_name = self._ed_rec_normalize_key(key)
            if not key_name:
                return True

            if key_name in self._ed_rec_pressed_keys:
                return True
            self._ed_rec_pressed_keys.add(key_name)

            with self._ed_rec_lock:
                if self._ed_rec_first_event_ns is None:
                    self._ed_rec_first_event_ns = now_ns
                    self._ed_rec_last_ts_ns = now_ns

                delay_ms = 0
                if self._ed_rec_last_ts_ns is not None:
                    delay_ns = now_ns - self._ed_rec_last_ts_ns
                    delay_ms = max(0, round(delay_ns / 1_000_000))

                if self._ed_rec_last_cmd == "kd" and self._ed_rec_last_key == key_name:
                    self._ed_rec_last_ts_ns = now_ns
                    return True

                self._ed_rec_last_cmd = "kd"
                self._ed_rec_last_key = key_name
                self._ed_rec_last_ts_ns = now_ns

            self._ed_rec_push_action("kd", key_name, delay_ms)
            return True
        except Exception:
            return True

    def _ed_rec_on_key_release(self, key):
        try:
            if not self._ed_rec_active:
                return True
            now_ns = self._ed_rec_perf_ns()
            key_name = self._ed_rec_normalize_key(key)
            if not key_name:
                return True

            self._ed_rec_pressed_keys.discard(key_name)

            with self._ed_rec_lock:
                if self._ed_rec_first_event_ns is None:
                    self._ed_rec_first_event_ns = now_ns
                    self._ed_rec_last_ts_ns = now_ns

                delay_ms = 0
                if self._ed_rec_last_ts_ns is not None:
                    delay_ns = now_ns - self._ed_rec_last_ts_ns
                    delay_ms = max(0, round(delay_ns / 1_000_000))

                if self._ed_rec_last_cmd == "ku" and self._ed_rec_last_key == key_name:
                    self._ed_rec_last_ts_ns = now_ns
                    return True

                self._ed_rec_last_cmd = "ku"
                self._ed_rec_last_key = key_name
                self._ed_rec_last_ts_ns = now_ns

            self._ed_rec_push_action("ku", key_name, delay_ms)
            return True
        except Exception:
            return True

    def _ed_rec_on_mouse_click(self, x, y, button, pressed):
        try:
            if not self._ed_rec_active:
                return
            now_ns = self._ed_rec_perf_ns()
            btn_name = self._ed_rec_normalize_mouse_btn(button)
            if not btn_name:
                return

            cmd = "md" if pressed else "mu"

            with self._ed_rec_lock:
                if self._ed_rec_first_event_ns is None:
                    self._ed_rec_first_event_ns = now_ns
                    self._ed_rec_last_ts_ns = now_ns

                delay_ms = 0
                if self._ed_rec_last_ts_ns is not None:
                    delay_ns = now_ns - self._ed_rec_last_ts_ns
                    delay_ms = max(0, round(delay_ns / 1_000_000))

                if self._ed_rec_last_cmd == cmd and self._ed_rec_last_key == btn_name:
                    self._ed_rec_last_ts_ns = now_ns
                    return

                self._ed_rec_last_cmd = cmd
                self._ed_rec_last_key = btn_name
                self._ed_rec_last_ts_ns = now_ns

            self._ed_rec_push_action(cmd, btn_name, delay_ms)
        except Exception:
            pass

    def editor_record_start(self):
        with self._ed_rec_lock:
            if self._ed_rec_active:
                return self._ok(already_recording=True)

            try:
                listener_state = (
                    self.executor.get_listener_state()
                    if hasattr(self, "executor") and hasattr(self.executor, "get_listener_state")
                    else {"running": False}
                )
                if bool(listener_state.get("running")) and hasattr(self.executor, "request_stop_listeners"):
                    self.executor.request_stop_listeners()
                    self.console.push("编辑器录制启动时已自动关闭宏执行全局监听", "stdout")
            except Exception as exc:
                self.console.push(f"自动关闭宏监听失败: {exc}", "stderr")

            self._ed_rec_actions = []
            self._ed_rec_last_cmd = None
            self._ed_rec_last_key = None
            self._ed_rec_last_ts_ns = None
            self._ed_rec_first_event_ns = None
            self._ed_rec_pressed_keys = set()
            self._ed_rec_active = True

        self._ed_rec_key_listener = keyboard.Listener(
            on_press=self._ed_rec_on_key_press,
            on_release=self._ed_rec_on_key_release,
        )
        self._ed_rec_mouse_listener = mouse.Listener(
            on_click=self._ed_rec_on_mouse_click,
            on_move=lambda x, y: None,
        )
        self._ed_rec_key_listener.start()
        self._ed_rec_mouse_listener.start()

        return self._ok(started=True)

    def editor_record_stop(self):
        with self._ed_rec_lock:
            if not self._ed_rec_active:
                return self._ok(actions=[])

            self._ed_rec_active = False

            # 仅剔除最后一对左键单击（md left + mu left），
            # 用于消除点击“停止”按钮时多录入的一次左键点击。
            # 使用 if 而非 while，避免误伤用户在停止前故意做的左键收尾连击。
            if self._ed_rec_actions:
                tail = self._ed_rec_actions[-1]
                if tail[0] == "mu" and tail[1] == "left":
                    self._ed_rec_actions.pop()
                    if self._ed_rec_actions and self._ed_rec_actions[-1][0] == "md" and self._ed_rec_actions[-1][1] == "left":
                        self._ed_rec_actions.pop()

            now_ns = self._ed_rec_perf_ns()
            if (
                self._ed_rec_actions
                and self._ed_rec_last_ts_ns is not None
                and self._ed_rec_first_event_ns is not None
            ):
                tail_delay_ns = now_ns - self._ed_rec_last_ts_ns
                tail_delay_ms = max(0, round(tail_delay_ns / 1_000_000))
                last = self._ed_rec_actions[-1]
                if last[0] in ("kd", "ku", "md", "mu") and last[2] == 0:
                    last[2] = tail_delay_ms

            actions = [list(a) for a in self._ed_rec_actions]
            self._ed_rec_actions = []
            self._ed_rec_last_cmd = None
            self._ed_rec_last_key = None
            self._ed_rec_last_ts_ns = None
            self._ed_rec_first_event_ns = None
            self._ed_rec_pressed_keys = set()

        if self._ed_rec_key_listener is not None:
            self._ed_rec_key_listener.stop()
            self._ed_rec_key_listener = None
        if self._ed_rec_mouse_listener is not None:
            self._ed_rec_mouse_listener.stop()
            self._ed_rec_mouse_listener = None

        try:
            window = getattr(self, "_window", None)
            if window is not None:
                tail_delay = 0
                if actions and actions[-1][0] in ("kd", "ku", "md", "mu"):
                    tail_delay = actions[-1][2]
                payload = {"tail_delay_ms": tail_delay}
                window.evaluate_js(
                    f"if(window._onEditorRecordStop)"
                    f"window._onEditorRecordStop({json.dumps(payload)});"
                )
        except Exception:
            pass

        return self._ok(actions=actions)

    def editor_record_is_active(self):
        with self._ed_rec_lock:
            return self._ok(active=self._ed_rec_active)
