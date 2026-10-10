# -*- coding: utf-8 -*-
"""
JS Bridge API — 前端与后端的通信接口
"""
import json
import os
import threading
import time

from core.paths import BASE_DIR, MACRO_ROOT

_automation_available = True
try:
    from automation.compiler import parse_graph, serialize_graph
    from automation.engine import execute_graph
    from automation.registry import PluginRegistry, register_builtin_nodes
except ImportError:
    _automation_available = False


def _ok(data=None):
    return {"ok": True, "data": data, "error": None}


def _err(msg):
    return {"ok": False, "data": None, "error": str(msg)}


class AutomationApiMixin:
    _automation_stop_event = None
    _automation_thread = None
    _automation_graph = None

    def _init_automation(self):
        if _automation_available:
            register_builtin_nodes()

    def get_node_definitions(self):
        if not _automation_available:
            return _err("自动化模块不可用")
        payload = PluginRegistry.get_frontend_payload()
        return _ok(payload)

    def run_automation(self, graph_json):
        if not _automation_available:
            return _err("自动化模块不可用")
        try:
            if isinstance(graph_json, str):
                json_data = json.loads(graph_json)
            else:
                json_data = graph_json

            graph = parse_graph(json_data)
            if not graph.entry_node_id:
                return _err("未找到入口节点")

            if self._automation_stop_event and self._automation_thread and self._automation_thread.is_alive():
                self._automation_stop_event.set()
                self._automation_thread.join(timeout=3.0)

            self._automation_stop_event = threading.Event()

            def worker():
                try:
                    execute_graph(graph, self._automation_stop_event)
                except Exception as e:
                    print(f"[自动化] 执行出错: {e}")
                finally:
                    self._automation_stop_event = None
                    self._automation_thread = None
                    self._automation_graph = None

            self._automation_graph = graph
            self._automation_thread = threading.Thread(target=worker, daemon=True)
            self._automation_thread.start()

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
            return _ok({"status": "completed"})
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if ctx and ctx.pause_event.is_set():
                return _ok({"status": "paused"})
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

    def preview_color(self, mode="screen", rect=None, hwnd_var=""):
        if not _automation_available:
            return _err("自动化模块不可用")
        try:
            from automation.detection.capture import capture_screen
            from automation.detection.color import check_color
            from engine.coordinate import resolve_region

            if rect is None:
                rect = [0, 0, 10, 10]
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
            return _ok({"center_color": center_hex, "mean_color": mean_hex})
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
            hwnd = None
            if hwnd_var:
                try:
                    hwnd = int(hwnd_var)
                except (ValueError, TypeError):
                    pass
            region = resolve_region(mode, rect, hwnd)
            img = capture_screen(region)
            ocr_engine = OCREngine()
            result = ocr_engine.detect(img)
            return _ok({
                "text": result.get("text", ""),
                "confidence": result.get("confidence", 0),
                "cost_ms": result.get("cost_ms", 0),
            })
        except Exception as e:
            return _err(f"预览OCR失败: {e}")

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
            from engine.coordinate import get_monitor_dpi_scale

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
                    phys_x = pt.x
                    phys_y = pt.y
                    dpi_scale = get_monitor_dpi_scale(phys_x, phys_y)
                    result["phys_x"] = phys_x
                    result["phys_y"] = phys_y
                    result["logic_x"] = round(phys_x / dpi_scale, 2)
                    result["logic_y"] = round(phys_y / dpi_scale, 2)

                    if mode == "window":
                        try:
                            import ctypes
                            user32 = ctypes.windll.user32
                            class POINT(ctypes.Structure):
                                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                            pt = POINT(phys_x, phys_y)
                            hwnd = user32.WindowFromPoint(pt)
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
            from engine.coordinate import get_monitor_dpi_scale

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
                dpi_scale = get_monitor_dpi_scale(x, y)
                self._pending_region_result = _ok({
                    "phys_rect": [x, y, w, h],
                    "rect": [round(x / dpi_scale, 2), round(y / dpi_scale, 2), round(w / dpi_scale, 2), round(h / dpi_scale, 2)],
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
