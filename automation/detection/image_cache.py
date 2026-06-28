# -*- coding: utf-8 -*-
import os
import threading
import cv2
import numpy as np

_template_cache = {}
_mtime_cache = {}
_cache_lock = threading.Lock()


def load_template(path: str) -> np.ndarray | None:
    if not path:
        return None
    abs_path = os.path.abspath(path)
    with _cache_lock:
        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            return _template_cache.pop(abs_path, None)

        cached = _template_cache.get(abs_path)
        if cached is not None and _mtime_cache.get(abs_path) == current_mtime:
            return cached

    img = cv2.imread(abs_path, cv2.IMREAD_COLOR)
    if img is not None:
        with _cache_lock:
            _template_cache[abs_path] = img
            _mtime_cache[abs_path] = current_mtime
    return img


def clear_cache():
    with _cache_lock:
        _template_cache.clear()
        _mtime_cache.clear()
