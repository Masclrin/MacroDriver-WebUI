# -*- coding: utf-8 -*-
import ctypes
import ctypes.wintypes
import logging
import threading

import numpy as np

_logger = logging.getLogger("capture")

_mss_local = threading.local()


def _get_mss():
    if not hasattr(_mss_local, 'instance') or _mss_local.instance is None:
        import mss
        _mss_local.instance = mss.mss()
    return _mss_local.instance


def _reset_mss():
    try:
        old = getattr(_mss_local, 'instance', None)
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
    except Exception:
        pass
    _mss_local.instance = None


def _capture_mss(region=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            sct = _get_mss()
            if region is None:
                monitor = sct.monitors[1]
            else:
                monitor = {
                    "left": int(region[0]),
                    "top": int(region[1]),
                    "width": int(region[2]),
                    "height": int(region[3]),
                }
            sct_img = sct.grab(monitor)
            img = np.array(sct_img)[:, :, :3]
            return img
        except Exception as e:
            _logger.warning("[截图] MSS 第%d次失败: %s", attempt + 1, e)
            _reset_mss()
            if attempt < max_retries - 1:
                import time
                time.sleep(0.1 * (attempt + 1))
            else:
                raise


def _capture_bitblt(region=None):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    if region is not None:
        left, top, w, h = int(region[0]), int(region[1]), int(region[2]), int(region[3])
    else:
        left, top = 0, 0
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)

    if w <= 0 or h <= 0 or left < -10000 or top < -10000:
        _logger.warning("[截图] BitBlt 区域无效 (%s), 回退 mss (坐标可能有偏移)", region)
        return _capture_mss(region)

    hdc = user32.GetDC(0)
    if not hdc:
        _logger.warning("[截图] BitBlt GetDC 失败, 回退 mss (坐标可能有偏移)")
        return _capture_mss(region)

    hdc_mem = None
    hbitmap = None
    old_bmp = None
    try:
        hdc_mem = gdi32.CreateCompatibleDC(hdc)
        if not hdc_mem:
            _logger.warning("[截图] BitBlt CreateCompatibleDC 失败, 回退 mss (坐标可能有偏移)")
            return _capture_mss(region)

        from ctypes import Structure, c_uint, c_long, sizeof, byref, c_ubyte, c_void_p, POINTER

        class BITMAPINFOHEADER(Structure):
            _fields_ = [
                ("biSize", c_uint),
                ("biWidth", c_long),
                ("biHeight", c_long),
                ("biPlanes", ctypes.wintypes.WORD),
                ("biBitCount", ctypes.wintypes.WORD),
                ("biCompression", c_uint),
                ("biSizeImage", c_uint),
                ("biXPelsPerMeter", c_long),
                ("biYPelsPerMeter", c_long),
                ("biClrUsed", c_uint),
                ("biClrImportant", c_uint),
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
            _logger.warning("[截图] BitBlt CreateDIBSection 失败, 回退 mss (坐标可能有偏移)")
            return _capture_mss(region)

        old_bmp = gdi32.SelectObject(hdc_mem, hbitmap)

        gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc, left, top, 0x00CC0020)

        scan_lines = gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, None, byref(bi), 0)
        if scan_lines == 0:
            _logger.warning("[截图] BitBlt GetDIBits 查询失败, 回退 mss (坐标可能有偏移)")
            return _capture_mss(region)

        buf_size = w * h * 4
        pixel_buf = (c_ubyte * buf_size)()
        result = gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, pixel_buf, byref(bi), 0)
        if result == 0:
            _logger.warning("[截图] BitBlt GetDIBits 读取失败, 回退 mss (坐标可能有偏移)")
            return _capture_mss(region)

        frame = np.frombuffer(pixel_buf, dtype=np.uint8).reshape((h, w, 4))
        return frame[:, :, :3].copy()
    except Exception as e:
        _logger.warning("[截图] BitBlt 异常: %s, 回退 mss (坐标可能有偏移)", e)
        return _capture_mss(region)
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


_capture_method_reported = {}


def capture_screen(region=None, ctx=None):
    if ctx is not None and hasattr(ctx, '_capture_manager'):
        with ctx._data_lock:
            cm = ctx._capture_manager
        if cm is not None:
            result, method = cm.capture(region)
            ctx_id = id(ctx)
            prev = _capture_method_reported.get(ctx_id)
            if prev != method:
                _logger.info("[截图] %s", method)
                _capture_method_reported[ctx_id] = method
            return result
    result = _capture_bitblt(region)
    ctx_id = id(ctx) if ctx is not None else 0
    prev = _capture_method_reported.get(ctx_id)
    method = "BitBlt/MSS (无截图源节点)"
    if prev != method:
        _logger.info("[截图] %s", method)
        _capture_method_reported[ctx_id] = method
    return result
