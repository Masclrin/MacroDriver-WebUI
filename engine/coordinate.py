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
    if mode == "screen":
        dpi_scale = get_monitor_dpi_scale(int(x * get_dpi_scale()), int(y * get_dpi_scale()))
        result = int(x * dpi_scale), int(y * dpi_scale)
        return result
    elif mode == "window":
        if hwnd:
            cx, cy = get_window_client_origin(hwnd)
            dpi_scale = get_monitor_dpi_scale(cx, cy)
            result = int(cx + x * dpi_scale), int(cy + y * dpi_scale)
            return result
        _logger.warning("window 模式缺少 hwnd，将 fallback 为 screen 模式")
        dpi_scale = get_monitor_dpi_scale(int(x * get_dpi_scale()), int(y * get_dpi_scale()))
        result = int(x * dpi_scale), int(y * dpi_scale)
        return result
    elif mode == "relative":
        if hwnd:
            cx, cy, cw, ch = get_window_client_rect(hwnd)
            result = int(cx + x * cw), int(cy + y * ch)
            return result
        _logger.warning("relative 模式缺少 hwnd，将 fallback 为 1920x1080 默认尺寸")
        result = int(x * 1920), int(y * 1080)
        return result
    return int(x), int(y)


def resolve_region(mode, rect, hwnd=None):
    if mode == "screen":
        approx_x = int(rect[0] * get_dpi_scale())
        approx_y = int(rect[1] * get_dpi_scale())
        dpi_scale = get_monitor_dpi_scale(approx_x, approx_y)
        result = (int(rect[0] * dpi_scale), int(rect[1] * dpi_scale),
                int(rect[2] * dpi_scale), int(rect[3] * dpi_scale))
        return result
    elif mode == "window":
        if hwnd:
            cx, cy = get_window_client_origin(hwnd)
            dpi_scale = get_monitor_dpi_scale(cx, cy)
            result = (int(cx + rect[0] * dpi_scale), int(cy + rect[1] * dpi_scale),
                    int(rect[2] * dpi_scale), int(rect[3] * dpi_scale))
            return result
        _logger.warning("window 模式缺少 hwnd，将 fallback 为 screen 模式")
        approx_x = int(rect[0] * get_dpi_scale())
        approx_y = int(rect[1] * get_dpi_scale())
        dpi_scale = get_monitor_dpi_scale(approx_x, approx_y)
        result = (int(rect[0] * dpi_scale), int(rect[1] * dpi_scale),
                int(rect[2] * dpi_scale), int(rect[3] * dpi_scale))
        return result
    elif mode == "relative":
        if hwnd:
            cx, cy, cw, ch = get_window_client_rect(hwnd)
            result = (int(cx + rect[0] * cw), int(cy + rect[1] * ch),
                    int(rect[2] * cw), int(rect[3] * ch))
            return result
        _logger.warning("relative 模式缺少 hwnd，将 fallback 为 1920x1080 默认尺寸")
        result = (int(rect[0] * 1920), int(rect[1] * 1080),
                int(rect[2] * 1920), int(rect[3] * 1080))
        return result
    result = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
    return result
