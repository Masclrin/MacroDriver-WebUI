# -*- coding: utf-8 -*-
"""
坐标解析器 — 处理 screen/window/relative 三种坐标模式及 DPI 缩放
"""
import ctypes


def get_dpi_scale():
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        return dpi / 96.0
    except Exception:
        return 1.0


def get_window_client_origin(hwnd):
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                     ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    rect = RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
    point = ctypes.Structure()
    point._fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = type('POINT', (ctypes.Structure,), {"_fields_": [("x", ctypes.c_long), ("y", ctypes.c_long)]})()
    pt.x = rect.left
    pt.y = rect.top
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def get_window_client_rect(hwnd):
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                     ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    rect = RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = type('POINT', (ctypes.Structure,), {"_fields_": [("x", ctypes.c_long), ("y", ctypes.c_long)]})()
    pt.x = rect.left
    pt.y = rect.top
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top


def resolve_coords(mode, x, y, hwnd=None):
    dpi_scale = get_dpi_scale()
    if mode == "screen":
        return int(x * dpi_scale), int(y * dpi_scale)
    elif mode == "window":
        if hwnd:
            cx, cy = get_window_client_origin(hwnd)
            return int(cx + x * dpi_scale), int(cy + y * dpi_scale)
        return int(x * dpi_scale), int(y * dpi_scale)
    elif mode == "relative":
        if hwnd:
            cx, cy, cw, ch = get_window_client_rect(hwnd)
            return int(cx + x * cw * dpi_scale), int(cy + y * ch * dpi_scale)
        return int(x * 1920 * dpi_scale), int(y * 1080 * dpi_scale)
    return int(x), int(y)


def resolve_region(mode, rect, hwnd=None):
    dpi_scale = get_dpi_scale()
    if mode == "screen":
        return (int(rect[0] * dpi_scale), int(rect[1] * dpi_scale),
                int(rect[2] * dpi_scale), int(rect[3] * dpi_scale))
    elif mode == "window":
        if hwnd:
            cx, cy = get_window_client_origin(hwnd)
            return (int(cx + rect[0] * dpi_scale), int(cy + rect[1] * dpi_scale),
                    int(rect[2] * dpi_scale), int(rect[3] * dpi_scale))
        return (int(rect[0] * dpi_scale), int(rect[1] * dpi_scale),
                int(rect[2] * dpi_scale), int(rect[3] * dpi_scale))
    elif mode == "relative":
        if hwnd:
            cx, cy, cw, ch = get_window_client_rect(hwnd)
            return (int(cx + rect[0] * cw * dpi_scale), int(cy + rect[1] * ch * dpi_scale),
                    int(rect[2] * cw * dpi_scale), int(rect[3] * ch * dpi_scale))
        return (int(rect[0] * 1920 * dpi_scale), int(rect[1] * 1080 * dpi_scale),
                int(rect[2] * 1920 * dpi_scale), int(rect[3] * 1080 * dpi_scale))
    return (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
