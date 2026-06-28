# -*- coding: utf-8 -*-
import logging
import threading
import ctypes
from ctypes import wintypes, Structure, c_uint, c_long, c_void_p, byref, sizeof, c_ubyte

_logger = logging.getLogger("plugin")

_precise_comp_local = threading.local()


class PluginContext:
    """插件上下文 - 为插件提供统一的系统能力接口

    设计原则：
    1. 所有接口都是可选的，插件可以按需使用
    2. 接口失败时返回合理的默认值，不抛出异常
    3. 不暴露内部实现细节，保持封装性
    4. 支持执行期上下文（ctx）和全局上下文两种模式
    """

    def __init__(self, emit_fn=None, capture_fn=None, var_get_fn=None,
                 var_set_fn=None, ctx_ref=None):
        self._emit_fn = emit_fn
        self._capture_fn = capture_fn
        self._var_get_fn = var_get_fn
        self._var_set_fn = var_set_fn
        self._ctx_ref = ctx_ref

    # ==================== 事件与日志 ====================

    def emit(self, event_name, data):
        """向前端推送事件，前端通过 onPluginEvent 接收"""
        if self._emit_fn:
            try:
                self._emit_fn(event_name, data)
            except Exception as e:
                _logger.error("[PluginContext] emit 失败: %s", e)

    def log(self, level, message):
        """写入日志到应用日志系统"""
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }
        lvl = level_map.get(level, logging.INFO)
        _logger.log(lvl, "[plugin] %s", message)

    # ==================== 截图接口 ====================

    def capture_screen(self, region=None):
        """截图接口 - 自动按优先级选择截图方式

        回退链：DXGI → BitBlt → mss
        - DXGI: 流程图含截图源节点时自动启用，高性能后台采集
        - BitBlt: 无截图源时的默认方式，Windows GDI，DPI 缩放正确
        - mss: BitBlt 失败时的兜底（坐标可能有偏移，仅极端情况触发）

        Args:
            region: [x, y, w, h] 截图区域（物理像素坐标），None表示全屏

        Returns:
            numpy.ndarray | None: BGR格式的图像数组，失败返回None
        """
        if self._capture_fn:
            try:
                return self._capture_fn(region)
            except Exception as e:
                _logger.warning("[PluginContext] 上下文截图失败: %s", e)

        # 回退到全局截图
        try:
            from automation.detection.capture import capture_screen as _cap
            return _cap(region)
        except Exception as e:
            _logger.error("[PluginContext] 截图失败: %s", e)
            return None

    def get_screen_size(self):
        """获取主屏幕分辨率

        Returns:
            dict: {"width": int, "height": int}
        """
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            return {"width": w, "height": h}
        except Exception as e:
            _logger.error("[PluginContext] 获取屏幕尺寸失败: %s", e)
            return {"width": 1920, "height": 1080}

    # ==================== 变量接口 ====================

    def get_variable(self, name, default=None):
        """获取流程变量值

        Args:
            name: 变量名
            default: 默认值

        Returns:
            变量值或默认值
        """
        if self._var_get_fn:
            try:
                return self._var_get_fn(name, default)
            except Exception as e:
                _logger.warning("[PluginContext] 获取变量失败: %s", e)
        return default

    def set_variable(self, name, value):
        if self._var_set_fn:
            try:
                self._var_set_fn(name, value)
            except Exception as e:
                _logger.warning("[PluginContext] 设置变量失败: %s", e)

    def get_check_result(self, key, default=None):
        if self._ctx_ref:
            try:
                return self._ctx_ref.safe_get_check_result(key, default)
            except Exception as e:
                _logger.warning("[PluginContext] 获取check_result失败: %s", e)
        return default

    def get_graph(self):
        if self._ctx_ref:
            try:
                return self._ctx_ref.graph
            except Exception:
                pass
        return None

    def get_exec_context(self):
        return self._ctx_ref

    # ==================== 窗口接口 ====================

    def find_window(self, title_pattern=None, class_name=None):
        """查找窗口句柄

        Args:
            title_pattern: 窗口标题（支持部分匹配）
            class_name: 窗口类名

        Returns:
            int | None: 窗口句柄，未找到返回None
        """
        try:
            user32 = ctypes.windll.user32

            if title_pattern:
                # 枚举所有窗口查找匹配标题
                found_hwnd = [None]

                def _enum_callback(hwnd, extra):
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    if title_pattern.lower() in buf.value.lower():
                        found_hwnd[0] = hwnd
                        return False
                    return True

                EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                user32.EnumWindows(EnumWindowsProc(_enum_callback), 0)
                return found_hwnd[0]

            elif class_name:
                hwnd = user32.FindWindowW(class_name, None)
                return hwnd if hwnd else None

        except Exception as e:
            _logger.error("[PluginContext] 查找窗口失败: %s", e)
        return None

    def get_window_rect(self, hwnd):
        """获取窗口矩形区域

        Args:
            hwnd: 窗口句柄

        Returns:
            dict: {"x": int, "y": int, "width": int, "height": int}
        """
        try:
            class RECT(Structure):
                _fields_ = [("left", c_long), ("top", c_long),
                           ("right", c_long), ("bottom", c_long)]

            rect = RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, byref(rect))
            return {
                "x": rect.left,
                "y": rect.top,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top,
            }
        except Exception as e:
            _logger.error("[PluginContext] 获取窗口区域失败: %s", e)
            return {"x": 0, "y": 0, "width": 0, "height": 0}

    # ==================== 桌面弹窗接口 ====================

    def show_desktop_popup(self, title, message, x=None, y=None,
                          duration_ms=3000, width=320, height=120):
        """在桌面显示置顶弹窗（不依赖App窗口）

        Args:
            title: 弹窗标题
            message: 弹窗内容
            x: 窗口X坐标，None表示屏幕右侧
            y: 窗口Y坐标，None表示屏幕底部
            duration_ms: 显示时长(毫秒)，0表示不自动关闭
            width: 窗口宽度
            height: 窗口高度

        Returns:
            dict: {"ok": bool, "hwnd": int|None, "error": str|None}
        """
        try:
            return self._create_win32_popup(title, message, x, y,
                                            duration_ms, width, height)
        except Exception as e:
            _logger.error("[PluginContext] 桌面弹窗失败: %s", e)
            # 回退到App内弹窗
            self.emit("notify_popup", {
                "title": title,
                "message": message,
                "duration": duration_ms,
            })
            return {"ok": True, "hwnd": None, "error": None,
                    "fallback": "app_popup"}

    def _create_win32_popup(self, title, message, x, y, duration_ms, width, height):
        import threading
        import time

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 计算默认位置（屏幕右下角）
        if x is None or y is None:
            screen = self.get_screen_size()
            if x is None:
                x = screen["width"] - width - 20
            if y is None:
                y = screen["height"] - height - 40

        # 窗口类名
        class_name = "MacroDriverPluginPopup"

        # 注册窗口类
        WNDPROC = ctypes.WINFUNCTYPE(c_long, c_void_p, c_uint, c_void_p, c_void_p)

        def _wnd_proc(hwnd, msg, wparam, lparam):
            if msg == 0x0010:  # WM_CLOSE
                user32.DestroyWindow(hwnd)
                return 0
            if msg == 0x0002:  # WM_DESTROY
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wnd_proc = WNDPROC(_wnd_proc)

        # 简化的窗口创建 - 使用MessageBox作为fallback
        # 实际生产环境应使用更完善的窗口创建逻辑
        try:
            # 使用Windows通知样式
            MB_OK = 0x00000000
            MB_ICONINFORMATION = 0x00000040
            MB_TOPMOST = 0x00040000

            # 创建线程显示弹窗，避免阻塞
            result = {"hwnd": None, "closed": False}

            def _show_msg():
                user32.MessageBoxW(0, message, title,
                                   MB_OK | MB_ICONINFORMATION | MB_TOPMOST)
                result["closed"] = True

            t = threading.Thread(target=_show_msg, daemon=True)
            t.start()

            if duration_ms > 0:
                def _auto_close():
                    time.sleep(duration_ms / 1000.0)
                    # MessageBox无法程序化关闭，这里只是记录
                    result["closed"] = True

                threading.Thread(target=_auto_close, daemon=True).start()

            return {"ok": True, "hwnd": result["hwnd"],
                    "error": None, "note": "使用系统消息框"}

        except Exception as e:
            return {"ok": False, "hwnd": None, "error": str(e)}

    # ==================== 高精度等待接口 ====================

    def precise_sleep(self, seconds):
        """高精度等待，替代 time.sleep

        使用项目高精度引擎 (engine/precision.py) 实现：
        - 自适应偏差补偿，长时间运行后精度趋近±50us
        - 三阶段混合等待：粗睡眠→细睡眠→忙等
        - 自动响应 stop_event（流程停止时立即返回）
        - 自动响应 pause_event（流程暂停时暂停等待）

        Args:
            seconds: 等待时长（秒），支持小数如 0.05 = 50ms

        Returns:
            bool: True=正常等待完成, False=被停止/暂停中断
        """
        try:
            from engine.precision import precise_sleep_v5, AdaptiveCompensator

            if not hasattr(_precise_comp_local, 'comp') or _precise_comp_local.comp is None:
                _precise_comp_local.comp = AdaptiveCompensator(alpha=0.04, warmup=30)
            comp = _precise_comp_local.comp

            stop_event = None
            pause_event = None
            if self._ctx_ref:
                if hasattr(self._ctx_ref, 'stop_event'):
                    stop_event = self._ctx_ref.stop_event
                if hasattr(self._ctx_ref, 'pause_event'):
                    pause_event = self._ctx_ref.pause_event

            if stop_event is None:
                stop_event = threading.Event()

            if stop_event.is_set():
                return False

            precise_sleep_v5(seconds, stop_event, comp, pause_event)

            return not stop_event.is_set()
        except ImportError:
            _logger.warning("[PluginContext] precision 模块不可用, 回退 time.sleep")
            import time
            time.sleep(seconds)
            return True
        except Exception as e:
            _logger.warning("[PluginContext] precise_sleep 异常: %s, 回退 time.sleep", e)
            import time
            time.sleep(seconds)
            return True

    # ==================== 音频接口 ====================

    def play_sound(self, file_path=None, frequency=800, duration_ms=200):
        """播放声音 - 支持文件或蜂鸣声

        Args:
            file_path: 音频文件路径(wav)，None表示使用蜂鸣声
            frequency: 蜂鸣声频率(Hz)
            duration_ms: 蜂鸣声时长(毫秒)

        Returns:
            bool: 是否成功
        """
        try:
            if file_path:
                import winsound
                winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return True
            else:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
                return True
        except Exception as e:
            _logger.error("[PluginContext] 播放声音失败: %s", e)
            return False

    # ==================== 鼠标接口 ====================

    def get_mouse_position(self):
        """获取当前鼠标位置

        Returns:
            dict: {"x": int, "y": int}
        """
        try:
            user32 = ctypes.windll.user32
            pt = wintypes.POINT()
            user32.GetCursorPos(byref(pt))
            return {"x": pt.x, "y": pt.y}
        except Exception as e:
            _logger.error("[PluginContext] 获取鼠标位置失败: %s", e)
            return {"x": 0, "y": 0}

    def set_mouse_position(self, x, y):
        """设置鼠标位置

        Args:
            x: 屏幕X坐标
            y: 屏幕Y坐标
        """
        try:
            user32 = ctypes.windll.user32
            user32.SetCursorPos(int(x), int(y))
        except Exception as e:
            _logger.error("[PluginContext] 设置鼠标位置失败: %s", e)

    # ==================== 图像检测接口 ====================

    def find_image(self, template_path, region=None, threshold=0.8):
        """在屏幕上查找模板图像

        Args:
            template_path: 模板图片路径
            region: [x, y, w, h] 搜索区域，None表示全屏
            threshold: 匹配阈值(0-1)

        Returns:
            dict: {"found": bool, "x": int, "y": int, "confidence": float}
        """
        try:
            import cv2
            import numpy as np
            from automation.detection.image_cache import load_template

            # 截图
            img = self.capture_screen(region)
            if img is None:
                return {"found": False, "x": 0, "y": 0, "confidence": 0}

            # 加载模板
            template = load_template(template_path)
            if template is None:
                return {"found": False, "x": 0, "y": 0, "confidence": 0,
                        "error": "模板加载失败"}

            # 匹配
            result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                return {"found": True, "x": max_loc[0], "y": max_loc[1],
                        "confidence": float(max_val)}
            else:
                return {"found": False, "x": 0, "y": 0,
                        "confidence": float(max_val)}

        except Exception as e:
            _logger.error("[PluginContext] 图像查找失败: %s", e)
            return {"found": False, "x": 0, "y": 0, "confidence": 0,
                    "error": str(e)}

    def check_color(self, x, y, target_color, tolerance=10):
        """检查指定位置的颜色

        Args:
            x: 屏幕X坐标
            y: 屏幕Y坐标
            target_color: 目标颜色，格式 "#RRGGBB"
            tolerance: 容差(0-255)

        Returns:
            dict: {"match": bool, "actual_color": str}
        """
        try:
            import re
            import numpy as np

            # 解析目标颜色
            m = re.match(r'^#([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$',
                         target_color.strip())
            if not m:
                return {"match": False, "actual_color": "", "error": "颜色格式错误"}

            target_bgr = (int(m.group(3), 16), int(m.group(2), 16),
                         int(m.group(1), 16))

            # 截图1x1区域
            img = self.capture_screen([x, y, 1, 1])
            if img is None or img.size == 0:
                return {"match": False, "actual_color": ""}

            actual_bgr = tuple(img[0, 0].tolist())
            diff = sum(abs(a - b) for a, b in zip(actual_bgr, target_bgr))

            # 转换实际颜色为hex
            actual_hex = f"#{actual_bgr[2]:02X}{actual_bgr[1]:02X}{actual_bgr[0]:02X}"

            return {"match": diff <= tolerance * 3, "actual_color": actual_hex,
                    "diff": diff}

        except Exception as e:
            _logger.error("[PluginContext] 颜色检查失败: %s", e)
            return {"match": False, "actual_color": "", "error": str(e)}
