# -*- coding: utf-8 -*-
"""
JS Bridge API — 前端与后端的通信接口
"""
import json
import os
import threading
import time
import numpy as np

from core.paths import BASE_DIR, MACRO_ROOT

_automation_available = True
try:
    from automation.compiler import parse_graph, serialize_graph
    from automation.engine import execute_graph
    from automation.registry import PluginRegistry, register_builtin_nodes
except ImportError:
    _automation_available = False

_pynput_available = True
try:
    from pynput import keyboard as _pynput_keyboard
except ImportError:
    _pynput_available = False


def _ok(data=None):
    return {"ok": True, "data": data, "error": None}


def _err(msg):
    return {"ok": False, "data": None, "error": str(msg)}


_PYNPUT_KEY_MAP = {
    "f1": _pynput_keyboard.Key.f1 if _pynput_available else None,
    "f2": _pynput_keyboard.Key.f2 if _pynput_available else None,
    "f3": _pynput_keyboard.Key.f3 if _pynput_available else None,
    "f4": _pynput_keyboard.Key.f4 if _pynput_available else None,
    "f5": _pynput_keyboard.Key.f5 if _pynput_available else None,
    "f6": _pynput_keyboard.Key.f6 if _pynput_available else None,
    "f7": _pynput_keyboard.Key.f7 if _pynput_available else None,
    "f8": _pynput_keyboard.Key.f8 if _pynput_available else None,
    "f9": _pynput_keyboard.Key.f9 if _pynput_available else None,
    "f10": _pynput_keyboard.Key.f10 if _pynput_available else None,
    "f11": _pynput_keyboard.Key.f11 if _pynput_available else None,
    "f12": _pynput_keyboard.Key.f12 if _pynput_available else None,
    "esc": _pynput_keyboard.Key.esc if _pynput_available else None,
    "space": _pynput_keyboard.Key.space if _pynput_available else None,
    "tab": _pynput_keyboard.Key.tab if _pynput_available else None,
    "enter": _pynput_keyboard.Key.enter if _pynput_available else None,
    "caps_lock": _pynput_keyboard.Key.caps_lock if _pynput_available else None,
    "home": _pynput_keyboard.Key.home if _pynput_available else None,
    "end": _pynput_keyboard.Key.end if _pynput_available else None,
    "page_up": _pynput_keyboard.Key.page_up if _pynput_available else None,
    "page_down": _pynput_keyboard.Key.page_down if _pynput_available else None,
    "insert": _pynput_keyboard.Key.insert if _pynput_available else None,
    "delete": _pynput_keyboard.Key.delete if _pynput_available else None,
    "up": _pynput_keyboard.Key.up if _pynput_available else None,
    "down": _pynput_keyboard.Key.down if _pynput_available else None,
    "left": _pynput_keyboard.Key.left if _pynput_available else None,
    "right": _pynput_keyboard.Key.right if _pynput_available else None,
}


def _normalize_hotkey_name(key_obj):
    if not _pynput_available:
        return None
    if isinstance(key_obj, _pynput_keyboard.Key):
        return key_obj.name
    if isinstance(key_obj, _pynput_keyboard.KeyCode):
        if key_obj.char:
            return key_obj.char.lower()
        if key_obj.vk:
            for name, vk_val in vars(_pynput_keyboard.Key).items():
                if not name.startswith('_') and vk_val is key_obj:
                    return name
        return None
    return None


def _hotkey_str_to_pynput(hotkey_str):
    if not hotkey_str or not _pynput_available:
        return None
    name = str(hotkey_str).strip().lower()
    if not name:
        return None
    if name in _PYNPUT_KEY_MAP:
        return _PYNPUT_KEY_MAP[name]
    if len(name) == 1:
        return _pynput_keyboard.KeyCode.from_char(name)
    return None


class AutomationApiMixin:
    _automation_stop_event = None
    _automation_thread = None
    _automation_graph = None
    _preview_ocr_engine = None
    _last_log_data = {"runs": [], "enabled": False, "continuous": False, "current_run_id": 0}
    _continuous_log = False
    _editor_hotkey_listener = None

    def _init_automation(self):
        if not hasattr(self, '_editor_hotkey_lock'):
            self._editor_hotkey_lock = threading.Lock()
        if not hasattr(self, '_editor_hotkey_pressed_keys'):
            self._editor_hotkey_pressed_keys = set()
        if _automation_available:
            register_builtin_nodes()
        self._start_editor_hotkey_listener()

    def _get_editor_hotkey_config(self):
        enabled = getattr(self, 'HOTKEY_ENABLED', True)
        run_key = str(getattr(self, 'HOTKEY_RUN', 'F6')).strip()
        pause_key = str(getattr(self, 'HOTKEY_PAUSE', 'F7')).strip()
        stop_key = str(getattr(self, 'HOTKEY_STOP', 'F8')).strip()
        fullscreen_key = str(getattr(self, 'HOTKEY_FULLSCREEN', 'F11')).strip()
        return {
            "enabled": enabled,
            "run": run_key,
            "pause": pause_key,
            "stop": stop_key,
            "fullscreen": fullscreen_key,
        }

    def _build_hotkey_action_map(self):
        cfg = self._get_editor_hotkey_config()
        action_map = {}
        if cfg["enabled"]:
            if cfg["run"]:
                key_lower = cfg["run"].lower()
                pk = _hotkey_str_to_pynput(key_lower)
                if pk is not None:
                    action_map[key_lower] = ("run", pk)
            if cfg["pause"]:
                key_lower = cfg["pause"].lower()
                pk = _hotkey_str_to_pynput(key_lower)
                if pk is not None and key_lower not in action_map:
                    action_map[key_lower] = ("pause", pk)
            if cfg["stop"]:
                key_lower = cfg["stop"].lower()
                pk = _hotkey_str_to_pynput(key_lower)
                if pk is not None and key_lower not in action_map:
                    action_map[key_lower] = ("stop", pk)
            if cfg["fullscreen"]:
                key_lower = cfg["fullscreen"].lower()
                pk = _hotkey_str_to_pynput(key_lower)
                if pk is not None and key_lower not in action_map:
                    action_map[key_lower] = ("fullscreen", pk)
        return action_map

    def _is_webview_focused(self):
        try:
            import ctypes
            hwnd_foreground = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd_foreground:
                return False
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd_foreground, ctypes.byref(pid))
            return pid.value == os.getpid()
        except Exception:
            return False

    def _on_editor_hotkey_press(self, key):
        try:
            key_name = _normalize_hotkey_name(key)
            if not key_name:
                return
            with self._editor_hotkey_lock:
                if key_name in self._editor_hotkey_pressed_keys:
                    return
                self._editor_hotkey_pressed_keys.add(key_name)
            focused = self._is_webview_focused()
            action_map = self._build_hotkey_action_map()
            if key_name in action_map:
                action = action_map[key_name][0]
                if focused:
                    return
                print(f"[编辑器热键] 全局按键 {key_name} → 动作 {action} (webview未聚焦，后端派发)")
                self._dispatch_editor_hotkey_action(action)
        except Exception as e:
            print(f"[编辑器热键] 按键处理异常: {e}")

    def _on_editor_hotkey_release(self, key):
        try:
            key_name = _normalize_hotkey_name(key)
            if not key_name:
                return
            with self._editor_hotkey_lock:
                self._editor_hotkey_pressed_keys.discard(key_name)
        except Exception:
            pass

    def _dispatch_editor_hotkey_action(self, action):
        try:
            import webview
            window = None
            if self._window is not None:
                window = self._window
            elif webview.windows:
                window = webview.windows[0]
            if window is None:
                return
            js_code = (
                "if(window._onGlobalEditorHotkey)"
                "{window._onGlobalEditorHotkey('" + action + "');}"
            )
            try:
                window.evaluate_js(js_code)
            except Exception:
                def _retry():
                    try:
                        window.evaluate_js(js_code)
                    except Exception:
                        pass
                threading.Timer(0.1, _retry).start()
        except Exception:
            pass

    def _start_editor_hotkey_listener(self):
        if not _pynput_available:
            print("[编辑器热键] pynput 不可用，全局热键监听未启动")
            return
        with self._editor_hotkey_lock:
            if self._editor_hotkey_listener is not None:
                return
            try:
                listener = _pynput_keyboard.Listener(
                    on_press=self._on_editor_hotkey_press,
                    on_release=self._on_editor_hotkey_release,
                )
                listener.daemon = True
                listener.start()
                self._editor_hotkey_listener = listener
                cfg = self._get_editor_hotkey_config()
                print(f"[编辑器热键] 全局监听已启动: enabled={cfg['enabled']}, run={cfg['run']}, pause={cfg['pause']}, stop={cfg['stop']}, fullscreen={cfg['fullscreen']}")
            except Exception as e:
                self._editor_hotkey_listener = None
                print(f"[编辑器热键] 启动失败: {e}")

    def _stop_editor_hotkey_listener(self):
        with self._editor_hotkey_lock:
            if self._editor_hotkey_listener is not None:
                try:
                    self._editor_hotkey_listener.stop()
                except Exception:
                    pass
                self._editor_hotkey_listener = None
            self._editor_hotkey_pressed_keys.clear()

    def _restart_editor_hotkey_listener(self):
        self._stop_editor_hotkey_listener()
        self._start_editor_hotkey_listener()

    def sync_editor_hotkeys(self):
        return _ok({"synced": True})

    def get_editor_hotkey_config(self):
        cfg = self._get_editor_hotkey_config()
        return _ok(cfg)

    def get_node_definitions(self):
        if not _automation_available:
            return _err("自动化模块不可用")
        payload = PluginRegistry.get_frontend_payload()
        return _ok(payload)

    def run_automation(self, graph_json, breakpoints=None, log_enabled=False):
        if not _automation_available:
            return _err("自动化模块不可用")
        try:
            if isinstance(graph_json, str):
                json_data = json.loads(graph_json)
            else:
                json_data = graph_json

            graph = parse_graph(json_data)
            if graph.errors:
                return _err("编译错误: " + "; ".join(str(e) for e in graph.errors))
            if not graph.entry_node_id:
                return _err("未找到入口节点")

            if hasattr(self, 'NODE_RETRY_COUNT'):
                graph.settings.setdefault("node_retry_count", self.NODE_RETRY_COUNT)
            if hasattr(self, 'NODE_RETRY_DELAY_MS'):
                graph.settings.setdefault("node_retry_delay_ms", self.NODE_RETRY_DELAY_MS)

            old_stop = self._automation_stop_event
            old_thread = self._automation_thread
            if old_stop and old_thread and old_thread.is_alive():
                old_stop.set()
                old_thread.join(timeout=3.0)
                if old_thread.is_alive():
                    return _err("旧任务仍在运行，请稍后重试")

            new_stop = threading.Event()
            self._automation_stop_event = new_stop

            def worker():
                try:
                    execute_graph(graph, new_stop, breakpoints=set(breakpoints or []), log_enabled=log_enabled)
                except Exception as e:
                    print(f"[自动化] 执行出错: {e}")
                finally:
                    if self._automation_graph:
                        ctx = getattr(self._automation_graph, '_exec_ctx', None)
                        if ctx and ctx.node_logger:
                            new_data = ctx.node_logger.get_data()
                            if self._continuous_log:
                                old_runs = self._last_log_data.get("runs", []) if isinstance(self._last_log_data, dict) else []
                                merged_runs = old_runs + new_data.get("runs", [])
                                if len(merged_runs) > 100:
                                    merged_runs = merged_runs[-100:]
                                new_data["runs"] = merged_runs
                            self._last_log_data = new_data
                    if self._automation_stop_event is new_stop:
                        self._automation_stop_event = None
                        self._automation_thread = None
                        self._automation_graph = None

            self._automation_graph = graph
            self._automation_thread = threading.Thread(target=worker, daemon=True)
            self._automation_thread.start()

            if not self._continuous_log:
                self._last_log_data = {"runs": [], "enabled": True, "continuous": False, "current_run_id": 0}

            return _ok({"status": "running"})
        except Exception as e:
            return _err(f"启动失败: {e}")

    def stop_automation(self):
        if not _automation_available:
            return _err("自动化模块不可用")
        if self._automation_stop_event:
            self._automation_stop_event.set()
            if self._automation_thread and self._automation_thread.is_alive():
                self._automation_thread.join(timeout=3.0)
            return _ok({"status": "stopped"})
        return _ok({"status": "idle"})

    def get_automation_status(self):
        if not _automation_available:
            return _err("自动化模块不可用")
        if not self._automation_thread or not self._automation_thread.is_alive():
            if self._automation_graph:
                ctx = getattr(self._automation_graph, '_exec_ctx', None)
                if ctx and ctx.errors:
                    last_err = ctx.errors[-1] if ctx.errors else {}
                    err_msg = last_err.get("message", str(last_err)) if isinstance(last_err, dict) else str(last_err)
                    return _ok({"status": "error", "error": err_msg})
            return _ok({"status": "completed"})
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if ctx and ctx.pause_event.is_set():
                return _ok({
                    "status": "paused",
                    "current_node": ctx._current_executing_node,
                    "breakpoint_hit": ctx._breakpoint_hit_node,
                })
            if ctx:
                return _ok({
                    "status": "running",
                    "current_node": ctx._current_executing_node,
                })
        return _ok({"status": "running"})

    def pause_automation(self, task_id=None):
        if not _automation_available:
            return _err("自动化模块不可用")
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if task_id and ctx:
                ctx.task_pool.pause(task_id)
            elif ctx:
                ctx.pause_event.set()
            return _ok({"status": "paused"})
        return _err("无运行中的自动化任务")

    def resume_automation(self, task_id=None):
        if not _automation_available:
            return _err("自动化模块不可用")
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if task_id and ctx:
                ctx.task_pool.resume(task_id)
            elif ctx:
                ctx.pause_event.clear()
            return _ok({"status": "resumed"})
        return _err("无运行中的自动化任务")

    def enable_execution_log(self, enabled=True):
        if not _automation_available:
            return _err("自动化模块不可用")
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if ctx:
                if enabled:
                    ctx.node_logger.enable()
                else:
                    ctx.node_logger.disable()
                return _ok({"log_enabled": ctx.node_logger._enabled})
        return _ok({"log_enabled": False})

    def set_continuous_log(self, continuous=True):
        if not _automation_available:
            return _err("自动化模块不可用")
        self._continuous_log = continuous
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if ctx:
                ctx.node_logger.set_continuous(continuous)
        return _ok({"continuous": continuous})

    def get_execution_log(self):
        if not _automation_available:
            return _err("自动化模块不可用")
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if ctx:
                data = ctx.node_logger.get_data()
                return _ok(data)
        return _ok(self._last_log_data if isinstance(self._last_log_data, dict) and self._last_log_data else {
            "runs": [], "enabled": False, "continuous": False, "current_run_id": 0
        })

    def clear_execution_log(self):
        if not _automation_available:
            return _err("自动化模块不可用")
        self._last_log_data = {"runs": [], "enabled": False, "continuous": False, "current_run_id": 0}
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if ctx:
                ctx.node_logger.clear()
        return _ok()

    def preview_color(self, mode="screen", rect=None, hwnd_var="",
                      target_color="#FF0000", tolerance=10,
                      check_mode="contain", sample_mode="center",
                      area_ratio_threshold=0.5):
        if not _automation_available:
            return _err("自动化模块不可用")
        try:
            from automation.detection.capture import capture_screen
            from automation.detection.color import check_color
            from engine.coordinate import resolve_region

            if rect is None:
                rect = [0, 0, 10, 10]
            if isinstance(rect, str):
                try:
                    rect = json.loads(rect)
                except (json.JSONDecodeError, ValueError):
                    rect = [0, 0, 10, 10]
            rect = [float(v) for v in rect]
            hwnd = None
            if hwnd_var:
                try:
                    hwnd = int(hwnd_var)
                except (ValueError, TypeError):
                    pass
            region = resolve_region(mode, rect, hwnd)
            img = capture_screen(region)
            h, w = img.shape[:2]
            center_pixel = img[h // 2, w // 2]
            mean_color = img.mean(axis=(0, 1))
            center_hex = "#{:02X}{:02X}{:02X}".format(
                int(center_pixel[2]), int(center_pixel[1]), int(center_pixel[0]))
            mean_hex = "#{:02X}{:02X}{:02X}".format(
                int(mean_color[2]), int(mean_color[1]), int(mean_color[0]))

            result = {"center_color": center_hex, "mean_color": mean_hex}

            if target_color and target_color.startswith("#") and len(target_color) == 7:
                r = int(target_color[1:3], 16)
                g = int(target_color[3:5], 16)
                b = int(target_color[5:7], 16)
                target_bgr = (b, g, r)

                if check_mode == "change":
                    import time
                    img1 = img.copy()
                    time.sleep(0.5)
                    img2 = capture_screen(region)
                    check_result = check_color(
                        img2, target_bgr, tolerance,
                        mode=check_mode, sample=sample_mode,
                        last_image=img1,
                        area_ratio_threshold=area_ratio_threshold
                    )
                else:
                    check_result = check_color(
                        img, target_bgr, tolerance,
                        mode=check_mode, sample=sample_mode,
                        area_ratio_threshold=area_ratio_threshold
                    )
                result["check_found"] = check_result["found"]
                result["actual_color"] = check_result["actual_color"]
                result["diff"] = round(check_result["diff"], 2)
                result["check_mode"] = check_mode

            return _ok(result)
        except Exception as e:
            return _err(f"预览颜色失败: {e}")

    def preview_ocr(self, mode="screen", rect=None, hwnd_var="", engine="rapidocr"):
        if not _automation_available:
            return _err("自动化模块不可用")
        try:
            from automation.detection.capture import capture_screen
            from automation.detection.ocr import OCREngine
            from engine.coordinate import resolve_region

            if rect is None:
                rect = [0, 0, 100, 30]
            if isinstance(rect, str):
                try:
                    rect = json.loads(rect)
                except (json.JSONDecodeError, ValueError):
                    rect = [0, 0, 100, 30]
            rect = [float(v) for v in rect]
            hwnd = None
            if hwnd_var:
                try:
                    hwnd = int(hwnd_var)
                except (ValueError, TypeError):
                    pass
            region = resolve_region(mode, rect, hwnd)
            img = capture_screen(region)
            if self._preview_ocr_engine is None:
                from automation.detection.ocr import OCREngine
                self._preview_ocr_engine = OCREngine()
            result = self._preview_ocr_engine.detect(img)
            return _ok({
                "text": result.get("text", ""),
                "confidence": result.get("confidence", 0),
                "cost_ms": result.get("cost_ms", 0),
            })
        except Exception as e:
            return _err(f"预览OCR失败: {e}")

    def preview_image_match(self, mode="screen", rect=None, hwnd_var="",
                            template_path="", threshold=0.8, method="tm_ccoeff_normed",
                            multi_match=False, pyramid_levels=2):
        if not _automation_available:
            return _err("自动化模块不可用")
        try:
            from automation.detection.capture import capture_screen
            from automation.handlers.detection import do_image_match
            from engine.coordinate import resolve_region
            import ctypes

            if not template_path:
                return _err("请先选择模板图片")

            if rect is None:
                rect = [0, 0, 0, 0]
            if isinstance(rect, str):
                try:
                    rect = json.loads(rect)
                except (json.JSONDecodeError, ValueError):
                    rect = [0, 0, 0, 0]
            rect = [float(v) for v in rect]
            hwnd = None
            if hwnd_var:
                try:
                    hwnd = int(hwnd_var)
                except (ValueError, TypeError):
                    pass

            if all(float(v) == 0 for v in rect):
                sw = ctypes.windll.user32.GetSystemMetrics(0)
                sh = ctypes.windll.user32.GetSystemMetrics(1)
                region = (0, 0, sw, sh)
            else:
                region = resolve_region(mode, rect, hwnd)

            img = capture_screen(region)

            method_map = {
                "tm_ccoeff_normed": 0,
                "tm_ccorr_normed": 1,
                "tm_sqdiff_normed": 2,
            }
            cv_method = method_map.get(method, 0)

            result = do_image_match(
                img, template_path, threshold=threshold,
                method=cv_method, multi_match=multi_match,
                pyramid_levels=int(pyramid_levels)
            )
            return _ok({
                "found": result["found"],
                "score": round(result.get("confidence", result.get("score", 0)), 4),
                "match_x": result.get("match_x", 0),
                "match_y": result.get("match_y", 0),
                "match_count": result.get("match_count", 0),
                "threshold": threshold,
            })
        except Exception as e:
            return _err(f"预览图像匹配失败: {e}")

    def preview_read_text(self, mode="screen", rect=None, hwnd_var="", read_mode="all"):
        if not _automation_available:
            return _err("自动化模块不可用")
        try:
            from automation.detection.capture import capture_screen
            from automation.detection.ocr import OCREngine
            from engine.coordinate import resolve_region

            if rect is None:
                rect = [0, 0, 100, 30]
            if isinstance(rect, str):
                try:
                    rect = json.loads(rect)
                except (json.JSONDecodeError, ValueError):
                    rect = [0, 0, 100, 30]
            rect = [float(v) for v in rect]
            hwnd = None
            if hwnd_var:
                try:
                    hwnd = int(hwnd_var)
                except (ValueError, TypeError):
                    pass
            region = resolve_region(mode, rect, hwnd)
            img = capture_screen(region)
            if self._preview_ocr_engine is None:
                self._preview_ocr_engine = OCREngine()
            result = self._preview_ocr_engine.detect(img)
            raw_text = result.get("text", "")
            raw_number = result.get("number", "")
            if read_mode == "number":
                display_text = raw_number or "(未识别到数字)"
            elif read_mode == "text":
                display_text = raw_text or "(未识别到文本)"
            else:
                display_text = raw_text or "(空)"
            return _ok({
                "text": display_text,
                "raw_text": raw_text,
                "raw_number": raw_number,
                "confidence": result.get("confidence", 0),
            })
        except Exception as e:
            return _err(f"预览读取文字失败: {e}")

    def get_screen_info(self):
        try:
            import ctypes
            from engine.coordinate import get_dpi_scale
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            dpi_scale = get_dpi_scale()
            return _ok({
                "width": width, "height": height,
                "dpi": int(dpi_scale * 96), "dpi_scale": dpi_scale,
            })
        except Exception as e:
            return _err(f"获取屏幕信息失败: {e}")

    def get_window_list(self):
        try:
            windows = []

            def enum_callback(hwnd, _):
                import ctypes
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value
                        if title:
                            cls_buf = ctypes.create_unicode_buffer(256)
                            ctypes.windll.user32.GetClassNameW(hwnd, cls_buf, 256)
                            windows.append({
                                "title": title,
                                "hwnd": hwnd,
                                "class_name": cls_buf.value,
                            })

            import ctypes
            ctypes.windll.user32.EnumWindows(
                ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong)(enum_callback), 0
            )
            return _ok(windows)
        except Exception as e:
            return _err(f"获取窗口列表失败: {e}")

    def capture_monitor_at_mouse(self):
        try:
            import mss
            import ctypes
            import numpy as np
            import cv2
            import base64
            from engine.coordinate import get_monitor_dpi_scale

            user32 = ctypes.windll.user32
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))

            sct = mss.mss()
            target_monitor = None
            for mon in sct.monitors[1:]:
                if (mon["left"] <= pt.x < mon["left"] + mon["width"] and
                        mon["top"] <= pt.y < mon["top"] + mon["height"]):
                    target_monitor = mon
                    break

            if target_monitor is None:
                target_monitor = sct.monitors[1]

            abs_x = target_monitor["left"]
            abs_y = target_monitor["top"]
            abs_w = target_monitor["width"]
            abs_h = target_monitor["height"]

            grab_region = {"left": abs_x, "top": abs_y, "width": abs_w, "height": abs_h}
            sct_img = sct.grab(grab_region)

            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            img_h, img_w = img.shape[:2]

            _, buf = cv2.imencode(".png", img)
            img_b64 = base64.b64encode(buf).decode("ascii")

            monitor_dpi = get_monitor_dpi_scale(abs_x, abs_y)
            return _ok({
                "image": img_b64,
                "origin_x": abs_x,
                "origin_y": abs_y,
                "width": img_w,
                "height": img_h,
                "dpi_scale": monitor_dpi,
            })
        except Exception as e:
            return _err(f"截图失败: {e}")

    def capture_window(self, hwnd=None):
        try:
            import ctypes
            import mss
            import numpy as np
            import cv2
            import base64
            from engine.coordinate import get_monitor_dpi_scale

            if not hwnd:
                return _err("缺少窗口句柄")
            hwnd = int(hwnd)

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                             ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            rect = RECT()
            ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
            pt = POINT()
            pt.x = rect.left
            pt.y = rect.top
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))

            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return _err("窗口尺寸无效")

            abs_x = pt.x
            abs_y = pt.y
            grab_region = {"left": abs_x, "top": abs_y, "width": w, "height": h}
            sct = mss.mss()
            sct_img = sct.grab(grab_region)

            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            img_h, img_w = img.shape[:2]

            _, buf = cv2.imencode(".png", img)
            img_b64 = base64.b64encode(buf).decode("ascii")

            window_dpi = get_monitor_dpi_scale(abs_x, abs_y)
            return _ok({
                "image": img_b64,
                "origin_x": abs_x,
                "origin_y": abs_y,
                "width": img_w,
                "height": img_h,
                "dpi_scale": window_dpi,
                "hwnd": hwnd,
            })
        except Exception as e:
            return _err(f"窗口截图失败: {e}")

    def get_window_at_mouse(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32

            cursor_pt = ctypes.Structure()
            cursor_pt._fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            user32.GetCursorPos(ctypes.byref(cursor_pt))

            hwnd = user32.WindowFromPoint(cursor_pt)
            if hwnd:
                root_hwnd = user32.GetAncestor(hwnd, 2)
                if root_hwnd:
                    hwnd = root_hwnd

            if not hwnd or not user32.IsWindowVisible(hwnd):
                return _ok({"hwnd": None, "title": "", "class_name": "", "rect": [0, 0, 0, 0]})

            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                             ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            return _ok({
                "hwnd": hwnd,
                "title": title,
                "class_name": cls_buf.value,
                "rect": [rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top],
            })
        except Exception as e:
            return _err(f"获取窗口信息失败: {e}")

    def pick_coordinate(self, mode="screen"):
        try:
            from threading import Event
            from pynput import mouse

            done = Event()
            result = {}

            def on_click(x, y, button, pressed):
                if button == mouse.Button.left and pressed:
                    import ctypes
                    user32 = ctypes.windll.user32
                    class POINT(ctypes.Structure):
                        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                    pt = POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    result["phys_x"] = pt.x
                    result["phys_y"] = pt.y

                    if mode == "window":
                        try:
                            pt2 = POINT(pt.x, pt.y)
                            hwnd = user32.WindowFromPoint(pt2)
                            if hwnd:
                                root = user32.GetAncestor(hwnd, 2)
                                if root:
                                    hwnd = root
                                result["hwnd"] = hwnd
                                result["mode"] = "window"
                        except Exception:
                            pass

                    done.set()
                    return False

            listener = mouse.Listener(on_click=on_click)
            listener.start()

            def wait_and_respond():
                done.wait(timeout=30)
                listener.stop()
                if not result:
                    self._pending_pick_result = _err("坐标拾取超时")
                else:
                    self._pending_pick_result = _ok(result)

            self._pending_pick_result = None
            t = threading.Thread(target=wait_and_respond, daemon=True)
            t.start()

            return _ok({"status": "picking"})
        except Exception as e:
            return _err(f"坐标拾取失败: {e}")

    def get_pick_result(self):
        if hasattr(self, '_pending_pick_result') and self._pending_pick_result is not None:
            result = self._pending_pick_result
            self._pending_pick_result = None
            return result
        return _ok({"status": "picking"})

    def pick_region(self, mode="screen"):
        try:
            from threading import Event
            from pynput import mouse

            done = Event()
            start = {"x": None, "y": None}
            end = {"x": None, "y": None}

            def _get_cursor_pos():
                import ctypes
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                pt = POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                return pt.x, pt.y

            def on_click(x, y, button, pressed):
                if button != mouse.Button.left:
                    return
                cx, cy = _get_cursor_pos()
                if pressed:
                    start["x"] = cx
                    start["y"] = cy
                else:
                    end["x"] = cx
                    end["y"] = cy
                    done.set()
                    return False

            listener = mouse.Listener(on_click=on_click)
            listener.start()

            def wait_and_respond():
                done.wait(timeout=30)
                listener.stop()
                if start["x"] is None or end["x"] is None:
                    self._pending_region_result = _err("区域拾取超时")
                    return
                x = min(start["x"], end["x"])
                y = min(start["y"], end["y"])
                w = abs(end["x"] - start["x"])
                h = abs(end["y"] - start["y"])
                self._pending_region_result = _ok({
                    "phys_rect": [x, y, w, h],
                    "rect": [x, y, w, h],
                })

            self._pending_region_result = None
            t = threading.Thread(target=wait_and_respond, daemon=True)
            t.start()

            return _ok({"status": "picking"})
        except Exception as e:
            return _err(f"区域拾取失败: {e}")

    def get_region_result(self):
        if hasattr(self, '_pending_region_result') and self._pending_region_result is not None:
            result = self._pending_region_result
            self._pending_region_result = None
            return result
        return _ok({"status": "picking"})

    def screen_capture_pick(self):
        try:
            import mss
            import ctypes
            import numpy as np
            import base64
            import cv2
            from engine.coordinate import get_monitor_dpi_scale

            user32 = ctypes.windll.user32
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))

            sct = mss.mss()
            target = None
            for mon in sct.monitors[1:]:
                if (mon["left"] <= pt.x < mon["left"] + mon["width"] and
                        mon["top"] <= pt.y < mon["top"] + mon["height"]):
                    target = mon
                    break
            if target is None:
                target = sct.monitors[1]

            abs_x = target["left"]
            abs_y = target["top"]
            abs_w = target["width"]
            abs_h = target["height"]

            grab_region = {"left": abs_x, "top": abs_y, "width": abs_w, "height": abs_h}
            sct_img = sct.grab(grab_region)

            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            img_h, img_w = img.shape[:2]

            _, buf = cv2.imencode(".png", img)
            img_b64 = base64.b64encode(buf).decode("ascii")

            monitor_dpi = get_monitor_dpi_scale(abs_x, abs_y)
            return _ok({
                "image": img_b64,
                "origin_x": abs_x,
                "origin_y": abs_y,
                "width": img_w,
                "height": img_h,
                "dpi_scale": monitor_dpi,
                "mode": "screen",
            })
        except Exception as e:
            return _err(f"屏幕截图拾取失败: {e}")

    def window_capture_pick(self, hwnd=None):
        try:
            import ctypes
            import mss
            import numpy as np
            import base64
            import cv2
            from engine.coordinate import get_monitor_dpi_scale

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                             ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            if not hwnd:
                user32 = ctypes.windll.user32
                pt = POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                hwnd = user32.WindowFromPoint(pt)
                if hwnd:
                    root = user32.GetAncestor(hwnd, 2)
                    if root:
                        hwnd = root

            if not hwnd:
                return _err("未找到目标窗口")
            hwnd = int(hwnd)

            rect = RECT()
            ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
            pt2 = POINT()
            pt2.x = rect.left
            pt2.y = rect.top
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt2))

            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return _err("窗口尺寸无效")

            abs_x = pt2.x
            abs_y = pt2.y
            grab_region = {"left": abs_x, "top": abs_y, "width": w, "height": h}
            sct = mss.mss()
            sct_img = sct.grab(grab_region)

            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            img_h, img_w = img.shape[:2]

            _, buf = cv2.imencode(".png", img)
            img_b64 = base64.b64encode(buf).decode("ascii")

            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf_title = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf_title, length + 1)

            cls_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, cls_buf, 256)

            window_dpi = get_monitor_dpi_scale(abs_x, abs_y)
            return _ok({
                "image": img_b64,
                "origin_x": abs_x,
                "origin_y": abs_y,
                "width": img_w,
                "height": img_h,
                "dpi_scale": window_dpi,
                "mode": "window",
                "hwnd": hwnd,
                "title": buf_title.value,
                "class_name": cls_buf.value,
            })
        except Exception as e:
            return _err(f"窗口截图拾取失败: {e}")

    def relative_capture_pick(self, hwnd=None):
        try:
            import ctypes
            import mss
            import numpy as np
            import base64
            import cv2
            from engine.coordinate import get_monitor_dpi_scale

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                             ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            if not hwnd:
                user32 = ctypes.windll.user32
                pt = POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                hwnd = user32.WindowFromPoint(pt)
                if hwnd:
                    root = user32.GetAncestor(hwnd, 2)
                    if root:
                        hwnd = root

            if not hwnd:
                return _err("未找到目标窗口")
            hwnd = int(hwnd)

            rect = RECT()
            ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
            pt2 = POINT()
            pt2.x = rect.left
            pt2.y = rect.top
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt2))

            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return _err("窗口尺寸无效")

            abs_x = pt2.x
            abs_y = pt2.y
            grab_region = {"left": abs_x, "top": abs_y, "width": w, "height": h}
            sct = mss.mss()
            sct_img = sct.grab(grab_region)

            img_arr = np.array(sct_img)
            img_arr = cv2.cvtColor(img_arr, cv2.COLOR_BGRA2BGR)

            img_h, img_w = img_arr.shape[:2]

            _, buf = cv2.imencode(".png", img_arr)
            img_b64 = base64.b64encode(buf).decode("ascii")

            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf_title = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf_title, length + 1)

            cls_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, cls_buf, 256)

            window_dpi = get_monitor_dpi_scale(abs_x, abs_y)
            return _ok({
                "image": img_b64,
                "origin_x": abs_x,
                "origin_y": abs_y,
                "width": img_w,
                "height": img_h,
                "window_width": img_w,
                "window_height": img_h,
                "dpi_scale": window_dpi,
                "mode": "relative",
                "hwnd": hwnd,
                "title": buf_title.value,
                "class_name": cls_buf.value,
            })
        except Exception as e:
            return _err(f"相对坐标截图拾取失败: {e}")

    def list_auto_scripts(self):
        try:
            scripts = []
            script_dir = str(BASE_DIR / "自动化脚本")
            if os.path.exists(script_dir):
                for f in os.listdir(script_dir):
                    if f.endswith(".auto.json"):
                        path = os.path.join(script_dir, f)
                        scripts.append({
                            "name": f,
                            "path": path,
                            "modified": os.path.getmtime(path),
                        })
            return _ok(scripts)
        except Exception as e:
            return _err(f"列出脚本失败: {e}")

    def load_auto_script(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _ok(data)
        except Exception as e:
            return _err(f"加载脚本失败: {e}")

    def save_auto_script(self, path, graph_json):
        try:
            if isinstance(graph_json, str):
                data = json.loads(graph_json)
            else:
                data = graph_json
            script_dir = os.path.dirname(path)
            if script_dir and not os.path.exists(script_dir):
                os.makedirs(script_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return _ok()
        except Exception as e:
            return _err(f"保存脚本失败: {e}")

    def list_macros(self):
        try:
            macros = []
            macro_dir = str(MACRO_ROOT)
            if os.path.exists(macro_dir):
                for root, dirs, files in os.walk(macro_dir):
                    for f in files:
                        if f.endswith(".json"):
                            path = os.path.join(root, f)
                            macros.append({
                                "name": f,
                                "path": path,
                            })
            return _ok(macros)
        except Exception as e:
            return _err(f"列出宏文件失败: {e}")

    def list_templates(self):
        try:
            templates = []
            tpl_dir = str(BASE_DIR / "图片模板")
            if not os.path.exists(tpl_dir):
                os.makedirs(tpl_dir, exist_ok=True)
            for root, dirs, files in os.walk(tpl_dir):
                for f in files:
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                        path = os.path.join(root, f)
                        templates.append({
                            "name": f,
                            "path": path,
                        })
            return _ok(templates)
        except Exception as e:
            return _err(f"列出模板图片失败: {e}")

    def choose_program_file(self):
        try:
            from webview import FileDialog
            if self._window is None:
                return _err("窗口未就绪")
            result = self._window.create_file_dialog(
                FileDialog.OPEN,
                allow_multiple=False,
                file_types=("可执行文件 (*.exe;*.bat;*.cmd;*.lnk;*.ps1)", "所有文件 (*.*)"),
            )
            if not result:
                return _ok(canceled=True)
            return _ok(data={"path": str(result[0])})
        except Exception as e:
            return _err(f"选择程序文件失败: {e}")

    def choose_script_file(self):
        try:
            from webview import FileDialog
            if self._window is None:
                return _err("窗口未就绪")
            script_dir = str(BASE_DIR / "自动化脚本")
            if not os.path.exists(script_dir):
                os.makedirs(script_dir, exist_ok=True)
            result = self._window.create_file_dialog(
                FileDialog.OPEN,
                allow_multiple=False,
                directory=script_dir,
                file_types=("自动化脚本 (*.auto.json;*.json)", "所有文件 (*.*)"),
            )
            if not result:
                return _ok(canceled=True)
            return _ok(data={"path": str(result[0])})
        except Exception as e:
            return _err(f"选择脚本文件失败: {e}")

    def choose_folder(self, initial_dir=None):
        try:
            from webview import FileDialog
            if self._window is None:
                return _err("窗口未就绪")
            if not initial_dir:
                initial_dir = str(BASE_DIR / "数字匹配模板")
            if not os.path.exists(initial_dir):
                os.makedirs(initial_dir, exist_ok=True)
            result = self._window.create_file_dialog(
                FileDialog.FOLDER,
                directory=initial_dir,
            )
            if not result:
                return _ok(canceled=True)
            return _ok(data={"path": str(result[0])})
        except Exception as e:
            return _err(f"选择文件夹失败: {e}")

    def get_process_list(self):
        try:
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            processes = []
            seen = set()
            for line in result.stdout.strip().split("\n"):
                parts = line.strip().strip('"').split('","')
                if len(parts) >= 2:
                    name = parts[0].strip('"')
                    pid = parts[1].strip('"')
                    key = name.lower()
                    if key not in seen:
                        seen.add(key)
                        processes.append({"name": name, "pid": pid})
            processes.sort(key=lambda p: p["name"].lower())
            return _ok(processes)
        except Exception as e:
            return _err(f"获取进程列表失败: {e}")

    def preview_digits(self, mode="screen", rect=None, hwnd_var="",
                       binary_method="otsu", split_method="contour", split_width=0,
                       template_folder="", template_sets="", match_method="auto", threshold=0.8):
        if not _automation_available:
            return _err("自动化模块不可用")
        try:
            from automation.detection.capture import capture_screen
            from engine.coordinate import resolve_region
            import numpy as np
            import cv2
            import base64

            if rect is None:
                rect = [0, 0, 0, 0]
            if isinstance(rect, str):
                try:
                    rect = json.loads(rect)
                except (json.JSONDecodeError, ValueError):
                    rect = [0, 0, 0, 0]
            rect = [float(v) for v in rect]
            hwnd = None
            if hwnd_var:
                try:
                    hwnd = int(hwnd_var)
                except (ValueError, TypeError):
                    pass
            import ctypes
            if all(float(v) == 0 for v in rect):
                sw = ctypes.windll.user32.GetSystemMetrics(0)
                sh = ctypes.windll.user32.GetSystemMetrics(1)
                region = (0, 0, sw, sh)
            else:
                region = resolve_region(mode, rect, hwnd)

            img = capture_screen(region)
            if img is None:
                return _err("截图失败")

            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img

            if binary_method == "adaptive_gaussian":
                binary = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 15, 5
                )
            else:
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            if np.mean(binary > 127) > 0.5:
                binary = 255 - binary

            rois = []
            split_info = []
            h = binary.shape[0]

            if split_method == "fixed_width":
                w = int(split_width) if split_width > 0 else max(1, binary.shape[1] // 5)
                num_segments = binary.shape[1] // w
                for i in range(num_segments):
                    x1 = i * w
                    x2 = (i + 1) * w
                    roi = binary[:, x1:x2]
                    rois.append(roi)
                    split_info.append({"x": x1, "w": w, "index": i})
            elif split_method == "projection":
                min_char_width = int(split_width) if split_width > 0 else 2
                proj = np.sum(binary > 127, axis=0)
                max_proj = np.max(proj) if proj.size > 0 else 1
                gap_threshold = max_proj * 0.1
                in_char = False
                start = 0
                for col in range(binary.shape[1]):
                    if proj[col] > gap_threshold:
                        if not in_char:
                            start = col
                            in_char = True
                    else:
                        if in_char:
                            end = col
                            if end - start >= min_char_width:
                                roi = binary[:, start:end]
                                rois.append(roi)
                                split_info.append({"x": start, "w": end - start, "index": len(rois) - 1})
                            in_char = False
                if in_char:
                    end = binary.shape[1]
                    if end - start >= min_char_width:
                        roi = binary[:, start:end]
                        rois.append(roi)
                        split_info.append({"x": start, "w": end - start, "index": len(rois) - 1})
            else:
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                valid_contours = []
                for c in contours:
                    xc, yc, wc, hc = cv2.boundingRect(c)
                    if wc > 1 and hc > 3:
                        valid_contours.append((c, xc))
                valid_contours.sort(key=lambda t: t[1])
                for c, xc in valid_contours:
                    cx, cy, cw, ch = cv2.boundingRect(c)
                    roi = binary[cy:cy + ch, cx:cx + cw]
                    rois.append(roi)
                    split_info.append({"x": cx, "w": cw, "index": len(rois) - 1})

            digit_matches = []
            templates_loaded = False
            template_error = None
            templates = None
            templates_bin = {}
            tpl_h = tpl_w = 0

            if template_folder and os.path.isdir(template_folder):
                try:
                    from automation.handlers.detection import _load_digit_templates
                    templates = _load_digit_templates(template_folder)
                    if templates:
                        sets_raw = str(template_sets) if template_sets else ""
                        selected_sets = [s.strip() for s in sets_raw.split(',') if s.strip()]
                        if selected_sets:
                            filtered = {}
                            for sname in selected_sets:
                                if sname in templates:
                                    filtered[sname] = templates[sname]
                            if filtered:
                                templates = filtered
                        first_template = None
                        for ft in templates.values():
                            for tpl in ft.values():
                                first_template = tpl
                                break
                            if first_template is not None:
                                break
                        tpl_h, tpl_w = (first_template.shape[0], first_template.shape[1]) if first_template is not None else (0, 0)
                        for name, ft in templates.items():
                            templates_bin[name] = {}
                            for digit_val, tpl in ft.items():
                                templates_bin[name][digit_val] = (tpl > 127).astype(np.uint8)
                        templates_loaded = True
                    else:
                        template_error = "模板文件夹中未找到数字模板(需0-9.png)"
                except Exception as e:
                    template_error = f"加载模板失败: {e}"
            else:
                if template_folder:
                    template_error = "模板文件夹路径无效"

            use_hamming = False
            if templates_loaded:
                if match_method == "hamming":
                    use_hamming = True
                elif match_method == "auto" and tpl_h > 0:
                    use_hamming = all(
                        roi.shape[0] == tpl_h and roi.shape[1] == tpl_w
                        for roi in rois
                    ) if rois else False

            for i, roi in enumerate(rois):
                best_digit = -1
                best_score = 0.0
                best_font = ""
                if templates_loaded:
                    if roi.shape[0] < 2 or roi.shape[1] < 1:
                        digit_matches.append({"index": i, "digit": -1, "score": 0, "font": "", "note": "ROI太小"})
                        continue
                    if use_hamming:
                        for name, ft_bin in templates_bin.items():
                            for digit_val, tpl_bin in ft_bin.items():
                                diff = np.count_nonzero(
                                    (cv2.resize(roi, (tpl_bin.shape[1], tpl_bin.shape[0]),
                                                interpolation=cv2.INTER_NEAREST) if roi.shape != tpl_bin.shape else roi) > 127
                                    .astype(np.uint8) != tpl_bin
                                )
                                total = tpl_bin.shape[0] * tpl_bin.shape[1]
                                score = 1.0 - diff / max(total, 1)
                                if score > best_score:
                                    best_score = score
                                    best_digit = digit_val
                                    best_font = name
                    else:
                        for name, ft in templates.items():
                            for digit_val, template in ft.items():
                                try:
                                    if template.shape[0] > roi.shape[0] or template.shape[1] > roi.shape[1]:
                                        roi_resized = cv2.resize(roi, (template.shape[1], template.shape[0]),
                                                                 interpolation=cv2.INTER_NEAREST)
                                    else:
                                        roi_resized = roi
                                    result = cv2.matchTemplate(roi_resized, template, cv2.TM_CCOEFF_NORMED)
                                    _, max_val, _, _ = cv2.minMaxLoc(result)
                                    if max_val > best_score:
                                        best_score = max_val
                                        best_digit = digit_val
                                        best_font = name
                                except Exception:
                                    continue
                    if best_score < threshold:
                        best_digit = -1
                    digit_matches.append({"index": i, "digit": int(best_digit), "score": round(best_score, 4),
                                          "font": best_font, "note": "" if best_digit >= 0 else "低于阈值"})
                else:
                    digit_matches.append({"index": i, "digit": -1, "score": 0, "font": "", "note": template_error or "无模板"})

            digit_str = "".join(str(m["digit"]) if m["digit"] >= 0 else "?" for m in digit_matches)

            vis_img = img.copy()
            for si in split_info:
                sx = si["x"]
                sw = si["w"]
                cv2.rectangle(vis_img, (sx, 0), (sx + sw, h - 1), (0, 255, 0), 1)
                label = str(si["index"])
                if si["index"] < len(digit_matches):
                    dm = digit_matches[si["index"]]
                    if dm["digit"] >= 0:
                        label = str(dm["digit"])
                cv2.putText(vis_img, label, (sx + 2, h - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            _, buffer = cv2.imencode('.jpg', vis_img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            vis_b64 = base64.b64encode(buffer).decode('utf-8')

            bin_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
            _, bin_buffer = cv2.imencode('.jpg', bin_rgb, [cv2.IMWRITE_JPEG_QUALITY, 80])
            bin_b64 = base64.b64encode(bin_buffer).decode('utf-8')

            return _ok({
                "segment_count": len(split_info),
                "segments": split_info,
                "digit_string": digit_str,
                "digit_matches": digit_matches,
                "templates_loaded": templates_loaded,
                "template_error": template_error,
                "image_width": binary.shape[1],
                "image_height": h,
                "visualization_b64": vis_b64,
                "binary_b64": bin_b64,
            })
        except Exception as e:
            return _err(f"预览数字分割失败: {e}")

    _NODE_COLOR_PALETTE = [
        (0, 255, 128), (255, 200, 0), (128, 128, 255), (0, 200, 255),
        (255, 128, 0), (200, 0, 255), (255, 100, 100), (100, 255, 200),
        (200, 255, 100), (255, 180, 180), (180, 180, 255), (180, 255, 180),
    ]

    _COORD_NODE_RULES = {
        "action/mouse_click": {"points": [("x", "y")], "regions": [], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "action/mouse_move": {"points": [("x", "y")], "regions": [], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "action/mouse_move_rel": {"points": [("dx", "dy")], "regions": [], "mode_key": None, "hwnd_key": None},
        "detection/capture_source": {"points": [], "regions": [], "mode_key": None, "hwnd_key": None},
        "detection/check_color": {"points": [], "regions": ["rect"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "detection/check_ocr": {"points": [], "regions": ["rect"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "detection/check_image": {"points": [], "regions": ["rect"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "detection/check_screen": {"points": [], "regions": ["region"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "detection/check_digits": {"points": [], "regions": ["rect"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "monitor/monitor_color": {"points": [], "regions": ["rect"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "monitor/monitor_ocr": {"points": [], "regions": ["rect"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "preset/preset_click": {"points": [("x", "y")], "regions": [], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "preset/preset_find_click": {"points": [], "regions": ["rect"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "preset/preset_read_text": {"points": [], "regions": ["rect"], "mode_key": "mode", "hwnd_key": "hwnd_var"},
        "utility/bookmark": {"points": [("x", "y")], "regions": [["x", "y", "w", "h"]], "mode_key": "mode", "hwnd_key": "hwnd_var"},
    }

    def _extract_coord_overlays(self, nodes, node_defs=None):
        import logging
        _logger = logging.getLogger("coord_overlay")
        overlays = []
        color_idx = 0
        coord_types = set()
        for node in nodes:
            ntype = node.get("type", "")
            params = node.get("params", {}) or {}
            node_id = node.get("id", "")
            custom_name = node.get("customName", "")

            rules = self._COORD_NODE_RULES.get(ntype)
            if not rules:
                if ntype.startswith("plugin/"):
                    rules = self._extract_plugin_coord_rules(params)
                if not rules:
                    continue

            coord_types.add(ntype)
            mode = params.get(rules.get("mode_key"), "screen") if rules.get("mode_key") else "screen"
            hwnd_var = params.get(rules.get("hwnd_key"), "") if rules.get("hwnd_key") else ""

            display_name = custom_name or ntype.split("/")[-1]
            color = self._NODE_COLOR_PALETTE[color_idx % len(self._NODE_COLOR_PALETTE)]
            color_idx += 1

            for point_keys in rules.get("points", []):
                if isinstance(point_keys, tuple) and len(point_keys) == 2:
                    x_val = params.get(point_keys[0], 0)
                    y_val = params.get(point_keys[1], 0)
                    try:
                        x_val = float(x_val) if str(x_val).strip() else 0
                        y_val = float(y_val) if str(y_val).strip() else 0
                    except (ValueError, TypeError):
                        continue
                    if x_val == 0 and y_val == 0:
                        continue
                    overlays.append({
                        "type": "point",
                        "x": x_val, "y": y_val,
                        "mode": mode, "hwnd_var": hwnd_var,
                        "label": display_name,
                        "color": color,
                        "node_id": node_id,
                    })

            for region_key in rules.get("regions", []):
                rect_val = params.get(region_key, [0, 0, 0, 0])
                if isinstance(region_key, list):
                    try:
                        vals = [float(params.get(k, 0)) for k in region_key]
                        rect_val = vals
                    except (ValueError, TypeError):
                        continue
                if not isinstance(rect_val, (list, tuple)) or len(rect_val) < 4:
                    continue
                try:
                    r = [float(v) for v in rect_val[:4]]
                except (ValueError, TypeError):
                    continue
                if r[2] == 0 and r[3] == 0:
                    continue
                overlays.append({
                    "type": "region",
                    "rect": r,
                    "mode": mode, "hwnd_var": hwnd_var,
                    "label": display_name,
                    "color": color,
                    "node_id": node_id,
                })

        _logger.info("[截图坐标] 匹配的坐标节点类型: %s, 总叠加数: %d", coord_types, len(overlays))
        return overlays

    def _extract_plugin_coord_rules(self, params):
        has_mode = "mode" in params and isinstance(params.get("mode"), str)
        mode_val = params.get("mode", "screen")
        if has_mode and mode_val in ("screen", "window", "relative"):
            points = []
            regions = []
            for k, v in params.items():
                if isinstance(v, (list, tuple)) and len(v) == 4:
                    regions.append(k)
            if regions:
                return {
                    "points": points, "regions": regions,
                    "mode_key": "mode", "hwnd_key": "hwnd_var",
                }
        return None

    def _draw_coord_overlays(self, img, overlays, hwnd=None, origin_x=0, origin_y=0):
        import cv2
        from engine.coordinate import resolve_coords, resolve_region

        if not overlays or img is None or img.size == 0:
            return img

        h, w = img.shape[:2]

        def _resolve_hwnd(ov):
            hv = ov.get("hwnd_var", "")
            if hv:
                try:
                    return int(hv)
                except (ValueError, TypeError):
                    pass
            if hwnd:
                try:
                    return int(hwnd)
                except (ValueError, TypeError):
                    pass
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont
            has_pil = True
        except ImportError:
            has_pil = False

        font_path = None
        if has_pil:
            import os
            for fp in [
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/simsun.ttc",
            ]:
                if os.path.exists(fp):
                    font_path = fp
                    break

        use_pil = has_pil and font_path is not None
        pil_img = None
        pil_draw = None
        pil_font = None
        has_chinese = any(ord(c) > 127 for ov in overlays for c in str(ov.get("label", "")))

        if use_pil and has_chinese:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            pil_draw = ImageDraw.Draw(pil_img)
            try:
                pil_font = ImageFont.truetype(font_path, 14)
            except Exception:
                pil_font = None
                use_pil = False
        else:
            use_pil = False

        for ov in overlays:
            color = ov.get("color", (0, 255, 128))
            color_rgb = (color[2], color[1], color[0])
            label = ov.get("label", "")
            mode = ov.get("mode", "screen")

            if ov["type"] == "point":
                x, y = ov["x"], ov["y"]
                if mode == "screen":
                    sx, sy = int(x) - origin_x, int(y) - origin_y
                else:
                    ov_hwnd = _resolve_hwnd(ov)
                    abs_x, abs_y = resolve_coords(mode, x, y, ov_hwnd)
                    sx, sy = abs_x - origin_x, abs_y - origin_y

                if -50 <= sx < w + 50 and -50 <= sy < h + 50:
                    cross_len = 15
                    if use_pil:
                        pil_draw.line([(sx - cross_len, sy), (sx + cross_len, sy)], fill=color_rgb, width=2)
                        pil_draw.line([(sx, sy - cross_len), (sx, sy + cross_len)], fill=color_rgb, width=2)
                        pil_draw.ellipse([(sx - 4, sy - 4), (sx + 4, sy + 4)], fill=color_rgb)
                        text = f"{label} ({int(x)},{int(y)})"
                        if pil_font:
                            pil_draw.text((sx + 8, sy - 18), text, fill=color_rgb, font=pil_font)
                    else:
                        cv2.line(img, (sx - cross_len, sy), (sx + cross_len, sy), color, 2)
                        cv2.line(img, (sx, sy - cross_len), (sx, sy + cross_len), color, 2)
                        cv2.circle(img, (sx, sy), 4, color, -1)
                        text = f"({int(x)},{int(y)})"
                        cv2.putText(img, text, (sx + 8, sy - 8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            elif ov["type"] == "region":
                rect = ov["rect"]
                if mode == "screen":
                    rx = int(rect[0]) - origin_x
                    ry = int(rect[1]) - origin_y
                    rw, rh = int(rect[2]), int(rect[3])
                else:
                    ov_hwnd = _resolve_hwnd(ov)
                    abs_x, abs_y, rw, rh = resolve_region(mode, rect, ov_hwnd)
                    rx, ry = abs_x - origin_x, abs_y - origin_y

                if rw > 0 and rh > 0:
                    if use_pil:
                        pil_draw.rectangle([(rx, ry), (rx + rw, ry + rh)], outline=color_rgb, width=2)
                        text = f"{label} [{int(rect[0])},{int(rect[1])},{int(rect[2])},{int(rect[3])}]"
                        if pil_font:
                            pil_draw.text((rx + 4, ry - 18), text, fill=color_rgb, font=pil_font)
                    else:
                        cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), color, 2)
                        text = f"[{int(rect[0])},{int(rect[1])},{int(rect[2])},{int(rect[3])}]"
                        cv2.putText(img, text, (rx + 4, ry - 8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        if use_pil and pil_img is not None:
            img_rgb = np.array(pil_img)
            img = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

        return img

    def _capture_bitblt_region(self, left, top, width, height):
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        w, h = int(width), int(height)
        l, t = int(left), int(top)
        if w <= 0 or h <= 0:
            return None
        hdc = user32.GetDC(0)
        if not hdc:
            return None
        hdc_mem = None
        hbitmap = None
        old_bmp = None
        try:
            hdc_mem = gdi32.CreateCompatibleDC(hdc)
            if not hdc_mem:
                return None
            from ctypes import Structure, c_uint, c_long, sizeof, byref, c_ubyte, c_void_p
            class BITMAPINFOHEADER(Structure):
                _fields_ = [
                    ("biSize", c_uint), ("biWidth", c_long), ("biHeight", c_long),
                    ("biPlanes", ctypes.wintypes.WORD), ("biBitCount", ctypes.wintypes.WORD),
                    ("biCompression", c_uint), ("biSizeImage", c_uint),
                    ("biXPelsPerMeter", c_long), ("biYPelsPerMeter", c_long),
                    ("biClrUsed", c_uint), ("biClrImportant", c_uint),
                ]
            bi = BITMAPINFOHEADER()
            bi.biSize = sizeof(BITMAPINFOHEADER)
            bi.biWidth = w
            bi.biHeight = -h
            bi.biPlanes = 1
            bi.biBitCount = 32
            bi.biCompression = 0
            bi.biSizeImage = w * h * 4
            ppv_bits = c_void_p()
            hbitmap = gdi32.CreateDIBSection(hdc_mem, byref(bi), 0, byref(ppv_bits), None, 0)
            if not hbitmap or not ppv_bits:
                return None
            old_bmp = gdi32.SelectObject(hdc_mem, hbitmap)
            gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc, l, t, 0x00CC0020)
            buf_size = w * h * 4
            pixel_buf = (c_ubyte * buf_size)()
            gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, pixel_buf, byref(bi), 0)
            frame = np.frombuffer(pixel_buf, dtype=np.uint8).reshape((h, w, 4))
            return frame[:, :, :3].copy()
        except Exception:
            return None
        finally:
            if hdc_mem is not None and old_bmp is not None:
                try:
                    gdi32.SelectObject(hdc_mem, old_bmp)
                except Exception:
                    pass
            if hbitmap is not None:
                try:
                    gdi32.DeleteObject(hbitmap)
                except Exception:
                    pass
            if hdc_mem is not None:
                try:
                    gdi32.DeleteDC(hdc_mem)
                except Exception:
                    pass
            try:
                user32.ReleaseDC(0, hdc)
            except Exception:
                pass

    def capture_coordinate_overlay(self, graph_json=None, capture_method="mss", hwnd=None, monitor_index=-1):
        try:
            import cv2
            import base64
            import mss
            import ctypes
            import logging
            from engine.coordinate import get_dpi_scale, get_monitor_dpi_scale

            _logger = logging.getLogger("coord_overlay")

            if graph_json is not None:
                self._last_overlay_graph_json = graph_json
            else:
                graph_json = getattr(self, '_last_overlay_graph_json', None)

            if graph_json and isinstance(graph_json, str):
                graph_data = json.loads(graph_json)
            elif graph_json:
                graph_data = graph_json
            else:
                graph_data = {}

            nodes = graph_data.get("nodes", [])
            if not nodes:
                graph_obj = graph_data.get("graph", {})
                if graph_obj:
                    nodes = graph_obj.get("nodes", [])

            _logger.info("[截图坐标] 收到 %d 个节点, graph_json类型=%s", len(nodes), type(graph_json).__name__)

            overlays = self._extract_coord_overlays(nodes)

            _logger.info("[截图坐标] 提取到 %d 个坐标叠加", len(overlays))

            sct = mss.mss()
            img = None
            actual_method = capture_method
            origin_x, origin_y = 0, 0

            if monitor_index >= 0 and monitor_index < len(sct.monitors) - 1:
                target = sct.monitors[monitor_index + 1]
            else:
                target = sct.monitors[0]
            origin_x = target["left"]
            origin_y = target["top"]

            if capture_method == "dxgi":
                if monitor_index < 0:
                    actual_method = "mss (DXGI不支持全部显示器)"
                else:
                    try:
                        from automation.detection.dxgi_capture import _DXGICaptureImpl
                        from engine.coordinate import mss_index_to_dxgi_output
                        output_idx = mss_index_to_dxgi_output(monitor_index)
                        need_reinit = False
                        if not hasattr(self, '_coord_overlay_dxgi'):
                            self._coord_overlay_dxgi = _DXGICaptureImpl()
                            self._coord_overlay_dxgi_initialized = False
                            self._coord_overlay_dxgi_output_idx = -1
                        dxgi = self._coord_overlay_dxgi
                        if self._coord_overlay_dxgi_output_idx != output_idx:
                            need_reinit = True
                        if need_reinit and self._coord_overlay_dxgi_initialized:
                            if dxgi.is_running():
                                dxgi.stop_background()
                            self._coord_overlay_dxgi_initialized = False
                        if not self._coord_overlay_dxgi_initialized:
                            self._coord_overlay_dxgi_initialized = dxgi.initialize(adapter_idx=0, output_idx=output_idx)
                            if self._coord_overlay_dxgi_initialized:
                                self._coord_overlay_dxgi_output_idx = output_idx
                                _logger.info("[截图坐标] DXGI 初始化 output_idx=%d", output_idx)
                        if self._coord_overlay_dxgi_initialized:
                            if not dxgi.is_running():
                                dxgi.start_background(fps=10)
                            frame = dxgi.get_latest_frame()
                            if frame is not None:
                                img = frame[:, :, :3] if frame.ndim == 3 and frame.shape[2] == 4 else frame
                                actual_method = "dxgi(显示器" + str(output_idx + 1) + ")"
                                dxgi_origin = dxgi.get_output_origin()
                                origin_x, origin_y = dxgi_origin[0], dxgi_origin[1]
                            else:
                                actual_method = "dxgi (无帧,回退mss)"
                    except Exception as e:
                        _logger.warning("[截图坐标] DXGI 异常: %s", e)
                        actual_method = "dxgi (异常,回退mss)"

            elif capture_method == "bitblt":
                bitblt_img = self._capture_bitblt_region(
                    target["left"], target["top"], target["width"], target["height"]
                )
                if bitblt_img is not None:
                    img = bitblt_img
                    actual_method = "bitblt"
                    if monitor_index >= 0:
                        actual_method = "bitblt(显示器" + str(monitor_index + 1) + ")"
                else:
                    actual_method = "bitblt (失败,回退mss)"

            if img is None:
                grab_region = {"left": target["left"], "top": target["top"],
                               "width": target["width"], "height": target["height"]}
                sct_img = sct.grab(grab_region)
                img = np.array(sct_img)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                if capture_method not in ("dxgi", "bitblt"):
                    actual_method = "mss"
                elif capture_method == "dxgi":
                    actual_method = "mss (dxgi回退)"
                elif capture_method == "bitblt":
                    actual_method = "mss (bitblt回退)"

            is_black = False
            if img is not None and img.size > 0:
                try:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    mean_val = np.mean(gray)
                    if mean_val < 5:
                        is_black = True
                except cv2.error:
                    is_black = False

            try:
                img = self._draw_coord_overlays(img, overlays, hwnd, origin_x, origin_y)
            except cv2.error as e:
                _logger.warning("[截图坐标] overlay 绘制内存不足，跳过: %s", e)

            img_h, img_w = img.shape[:2]

            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            img_b64 = base64.b64encode(buf).decode("ascii")

            dpi_scale = get_dpi_scale()
            monitor_dpi = get_monitor_dpi_scale(origin_x, origin_y) if origin_x != 0 or origin_y != 0 else dpi_scale

            return _ok({
                "image": img_b64,
                "width": img_w,
                "height": img_h,
                "dpi_scale": monitor_dpi,
                "capture_method": actual_method,
                "is_black": is_black,
                "overlay_count": len(overlays),
                "origin_x": origin_x,
                "origin_y": origin_y,
                "monitor_count": len(sct.monitors) - 1,
                "node_count": len(nodes),
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return _err(f"截图坐标叠加失败: {e}")

    def get_capture_source_status(self):
        try:
            dxgi_available = False
            dxgi_error = None
            try:
                from automation.detection.dxgi_capture import DXGICapture
                test = DXGICapture()
                if test._impl._initialized:
                    dxgi_available = True
                else:
                    dxgi_available = test.initialize()
                    if not dxgi_available:
                        dxgi_error = "DXGI Desktop Duplication 初始化失败"
            except ImportError:
                dxgi_error = "DXGI 模块不可用"
            except Exception as e:
                dxgi_error = f"DXGI 异常: {e}"

            mss_available = False
            mss_error = None
            monitor_info = []
            try:
                import mss
                sct = mss.mss()
                mss_available = True
                for i, mon in enumerate(sct.monitors[1:]):
                    monitor_info.append({
                        "index": i,
                        "left": mon["left"],
                        "top": mon["top"],
                        "width": mon["width"],
                        "height": mon["height"],
                    })
            except Exception as e:
                mss_error = f"mss 异常: {e}"

            bitblt_available = False
            bitblt_error = None
            try:
                import ctypes
                hdc = ctypes.windll.user32.GetDC(0)
                if hdc:
                    ctypes.windll.user32.ReleaseDC(0, hdc)
                    bitblt_available = True
                else:
                    bitblt_error = "GetDC 失败"
            except Exception as e:
                bitblt_error = f"BitBlt 检测异常: {e}"

            from engine.coordinate import get_dpi_scale
            dpi_scale = get_dpi_scale()

            return _ok({
                "dxgi_available": dxgi_available,
                "dxgi_error": dxgi_error,
                "mss_available": mss_available,
                "mss_error": mss_error,
                "bitblt_available": bitblt_available,
                "bitblt_error": bitblt_error,
                "dpi_scale": dpi_scale,
                "monitors": monitor_info,
            })
        except Exception as e:
            return _err(f"获取截图源状态失败: {e}")

    def stop_coord_overlay_dxgi(self):
        try:
            if hasattr(self, '_coord_overlay_dxgi') and self._coord_overlay_dxgi is not None:
                if self._coord_overlay_dxgi.is_running():
                    self._coord_overlay_dxgi.stop_background()
            return _ok({"stopped": True})
        except Exception as e:
            return _err(f"停止DXGI失败: {e}")

    def open_coord_overlay_popout(self):
        """已弃用：坐标浏览器已改回浮动面板模式。保留此API仅作兼容。"""
        return _err("坐标浏览器已改为浮动面板，此API已弃用")

    def cache_overlay_graph_json(self, graph_json=None):
        if graph_json is not None:
            self._last_overlay_graph_json = graph_json
        return _ok({"cached": True})

    def set_coord_overlay_always_on_top(self, pinned=True):
        try:
            import ctypes
            win = getattr(self, '_coord_popout_window', None)
            if win is None:
                return _err("弹出窗口未创建")
            hwnd_val = None
            if hasattr(win, 'gui') and win.gui is not None:
                if hasattr(win.gui, 'hwnd'):
                    hwnd_val = win.gui.hwnd
                elif hasattr(win.gui, '_hwnd'):
                    hwnd_val = win.gui._hwnd
            if hwnd_val is None:
                return _err("无法获取窗口句柄，窗口可能未加载完成")
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            ctypes.windll.user32.SetWindowPos(
                int(hwnd_val),
                HWND_TOPMOST if pinned else HWND_NOTOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE
            )
            return _ok(pinned=pinned)
        except Exception as e:
            return _err(f"设置置顶失败: {e}")
