# -*- coding: utf-8 -*-
"""
坐标解析器 — 处理 screen/window/relative 三种坐标模式及 DPI 缩放
"""
import ctypes
import logging

_logger = logging.getLogger(__name__)


def get_dpi_scale():
    """获取系统主显示器DPI缩放"""
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        return dpi / 96.0
    except Exception:
        return 1.0


def get_monitor_dpi_scale(monitor_left=0, monitor_top=0):
    try:
        import ctypes
        from ctypes import wintypes, POINTER, byref

        MONITOR_DEFAULTTONEAREST = 2
        MDT_EFFECTIVE_DPI = 0
        pt = wintypes.POINT(monitor_left, monitor_top)
        hMonitor = ctypes.windll.user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)

        if not hMonitor:
            return get_dpi_scale()

        dpiX = wintypes.UINT()
        dpiY = wintypes.UINT()

        try:
            shcore = ctypes.windll.shcore
            if shcore:
                shcore.GetDpiForMonitor.argtypes = [wintypes.HANDLE, wintypes.UINT, POINTER(wintypes.UINT), POINTER(wintypes.UINT)]
                shcore.GetDpiForMonitor.restype = ctypes.c_long
                hr = shcore.GetDpiForMonitor(hMonitor, MDT_EFFECTIVE_DPI, byref(dpiX), byref(dpiY))
                if hr == 0 and dpiX.value > 0:
                    result = dpiX.value / 96.0
                    return result
        except Exception as e:

            return get_dpi_scale()
    except Exception as e:
        return get_dpi_scale()


def get_window_client_origin(hwnd):
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
    return pt.x, pt.y


def get_window_client_rect(hwnd):
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
    return pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top


def resolve_coords(mode, x, y, hwnd=None):
    try:
        x = float(x)
        y = float(y)
    except (ValueError, TypeError):
        return (0, 0)
    if mode == "screen":
        return (int(x), int(y))
    elif mode == "window":
        if hwnd:
            cx, cy = get_window_client_origin(hwnd)
            result = int(cx + x), int(cy + y)
            return result
        _logger.warning("window 模式缺少 hwnd，将 fallback 为 screen 模式")
        result = int(x), int(y)
        return result
    elif mode == "relative":
        if hwnd:
            cx, cy, cw, ch = get_window_client_rect(hwnd)
            result = int(cx + x * cw), int(cy + y * ch)
            return result
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        if sw <= 0 or sh <= 0:
            sw, sh = 1920, 1080
        _logger.warning("relative 模式缺少 hwnd，将 fallback 为屏幕尺寸 %dx%d", sw, sh)
        result = int(x * sw), int(y * sh)
        return result
    return int(x), int(y)


def resolve_region(mode, rect, hwnd=None):
    try:
        r = [float(v) for v in rect]
    except (ValueError, TypeError):
        r = [0, 0, 0, 0]
    if mode == "screen":
        return (int(r[0]), int(r[1]), int(r[2]), int(r[3]))
    elif mode == "window":
        if hwnd:
            cx, cy = get_window_client_origin(hwnd)
            result = (int(cx + r[0]), int(cy + r[1]),
                    int(r[2]), int(r[3]))
            return result
        _logger.warning("window 模式缺少 hwnd，将 fallback 为 screen 模式")
        result = (int(r[0]), int(r[1]), int(r[2]), int(r[3]))
        return result
    elif mode == "relative":
        if hwnd:
            cx, cy, cw, ch = get_window_client_rect(hwnd)
            result = (int(cx + r[0] * cw), int(cy + r[1] * ch),
                    int(r[2] * cw), int(r[3] * ch))
            return result
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        if sw <= 0 or sh <= 0:
            sw, sh = 1920, 1080
        _logger.warning("relative 模式缺少 hwnd，将 fallback 为屏幕尺寸 %dx%d", sw, sh)
        result = (int(r[0] * sw), int(r[1] * sh),
                int(r[2] * sw), int(r[3] * sh))
        return result
    result = (int(r[0]), int(r[1]), int(r[2]), int(r[3]))
    return result


def enum_monitor_rects():
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                     ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    monitors = []

    def _callback(hmon, hdc, lprect, lparam):
        rect = lprect.contents
        monitors.append((rect.left, rect.top, rect.right, rect.bottom))
        return True

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(RECT), ctypes.c_long
    )
    ctypes.windll.user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_callback), 0)
    return monitors


def mss_index_to_dxgi_output(mss_monitor_index):
    try:
        import mss
        sct = mss.mss()
        if mss_monitor_index < 0 or mss_monitor_index >= len(sct.monitors) - 1:
            return 0
        target = sct.monitors[mss_monitor_index + 1]
        target_left = target["left"]
        target_top = target["top"]

        win_monitors = enum_monitor_rects()
        for dxgi_idx, (left, top, right, bottom) in enumerate(win_monitors):
            if left == target_left and top == target_top:
                return dxgi_idx

        _logger.warning("mss显示器%d未匹配到DXGI output，使用索引0", mss_monitor_index)
        return 0
    except Exception as e:
        _logger.warning("mss_index_to_dxgi_output 失败: %s", e)
        return 0
