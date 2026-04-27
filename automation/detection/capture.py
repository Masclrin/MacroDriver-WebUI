# -*- coding: utf-8 -*-
"""
截图模块 — mss 封装，返回 BGR numpy 数组
"""
import numpy as np

_mss_instance = None


def _get_mss():
    global _mss_instance
    if _mss_instance is None:
        import mss
        _mss_instance = mss.mss()
    return _mss_instance


def capture_screen(region=None):
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
