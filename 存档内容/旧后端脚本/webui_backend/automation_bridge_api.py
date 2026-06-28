# -*- coding: utf-8 -*-
"""
JS Bridge API — 前端与后端的通信接口
"""
import json
import os
import threading
import time

from webui_backend.automation_compiler import parse_graph, serialize_graph
from webui_backend.automation_engine import execute_graph
from webui_backend.plugin_registry import PluginRegistry, register_builtin_nodes


def _ok(data=None):
    return {"ok": True, "data": data, "error": None}


def _err(msg):
    return {"ok": False, "data": None, "error": str(msg)}


class AutomationApiMixin:
    _automation_stop_event = None
    _automation_thread = None
    _automation_graph = None

    def _init_automation(self):
        register_builtin_nodes()

    def get_node_definitions(self):
        payload = PluginRegistry.get_frontend_payload()
        return _ok(payload)

    def run_automation(self, graph_json):
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
        if self._automation_stop_event:
            self._automation_stop_event.set()
            if self._automation_thread and self._automation_thread.is_alive():
                self._automation_thread.join(timeout=3.0)
            return _ok({"status": "stopped"})
        return _ok({"status": "idle"})

    def pause_automation(self, task_id=None):
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if task_id and ctx:
                ctx.task_pool.pause(task_id)
            elif ctx:
                ctx.pause_event.set()
            return _ok({"status": "paused"})
        return _err("无运行中的自动化任务")

    def resume_automation(self, task_id=None):
        if self._automation_graph:
            ctx = getattr(self._automation_graph, '_exec_ctx', None)
            if task_id and ctx:
                ctx.task_pool.resume(task_id)
            elif ctx:
                ctx.pause_event.clear()
            return _ok({"status": "resumed"})
        return _err("无运行中的自动化任务")

    def preview_color(self, mode="screen", rect=None, hwnd_var=""):
        try:
            from webui_backend.detection.capture import capture_screen
            from webui_backend.detection.color import check_color
            from webui_backend.coordinate_resolver import resolve_region

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
        try:
            from webui_backend.detection.capture import capture_screen
            from webui_backend.detection.ocr import OCREngine
            from webui_backend.coordinate_resolver import resolve_region

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
            from webui_backend.coordinate_resolver import get_dpi_scale
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

    def pick_coordinate(self, mode="screen"):
        try:
            from threading import Event
            from pynput import mouse
            from webui_backend.coordinate_resolver import get_dpi_scale

            done = Event()
            result = {}

            def on_click(x, y, button, pressed):
                if button == mouse.Button.left and pressed:
                    dpi_scale = get_dpi_scale()
                    result["phys_x"] = int(x)
                    result["phys_y"] = int(y)
                    result["logic_x"] = round(x / dpi_scale, 2)
                    result["logic_y"] = round(y / dpi_scale, 2)
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
            from webui_backend.coordinate_resolver import get_dpi_scale

            done = Event()
            start = {"x": None, "y": None}
            end = {"x": None, "y": None}

            def on_click(x, y, button, pressed):
                if button != mouse.Button.left:
                    return
                if pressed:
                    start["x"] = int(x)
                    start["y"] = int(y)
                else:
                    end["x"] = int(x)
                    end["y"] = int(y)
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
                dpi_scale = get_dpi_scale()
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

    def list_auto_scripts(self):
        try:
            scripts = []
            script_dir = os.path.join(os.getcwd(), "自动化脚本")
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
            macro_dir = os.path.join(os.getcwd(), "宏")
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
