# -*- coding: utf-8 -*-
"""
OCR 检测模块 — RapidOCR 封装 + 可配置缓存策略
"""
import time
import re
import numpy as np


class OCREngine:
    def __init__(self):
        self._rapidocr = None
        self._last_result = {}

    def _get_rapidocr(self):
        if self._rapidocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._rapidocr = RapidOCR()
            except ImportError:
                raise RuntimeError("RapidOCR 未安装，请运行: pip install rapidocr_onnxruntime")
        return self._rapidocr

    def detect(self, image, match_text="", match_mode="contain",
               match_number=None, cache_key=None, last_image=None,
               cache_strategy="time_interval", cache_interval_ms=100):
        if cache_key and cache_strategy != "disabled" and last_image is not None:
            if image.shape == last_image.shape:
                if cache_strategy == "frame_diff":
                    diff = np.mean(np.abs(image.astype(float) - last_image.astype(float)))
                    if diff < 2.0:
                        cached = self._last_result.get(cache_key)
                        if cached:
                            cached["cost_ms"] = 0.1
                            return cached
                elif cache_strategy == "time_interval":
                    cached = self._last_result.get(cache_key)
                    if cached:
                        now = time.perf_counter()
                        if (now - cached.get("_timestamp", 0)) * 1000 < cache_interval_ms:
                            cached["cost_ms"] = 0.1
                            return cached

        engine = self._get_rapidocr()
        start = time.perf_counter()
        results, _ = engine(image)
        cost_ms = (time.perf_counter() - start) * 1000

        full_text = ""
        if results:
            full_text = " ".join(item[1] for item in results)

        found = False
        extracted_number = None

        if match_mode == "contain":
            found = match_text in full_text if match_text else False
        elif match_mode == "exact":
            found = full_text.strip() == match_text
        elif match_mode == "regex":
            found = bool(re.search(match_text, full_text))
        elif match_mode in ("number_gt", "number_lt", "number_eq"):
            numbers = re.findall(r'[\d.]+', full_text)
            if numbers:
                try:
                    extracted_number = float(numbers[0])
                    if match_mode == "number_gt":
                        found = extracted_number > match_number
                    elif match_mode == "number_lt":
                        found = extracted_number < match_number
                    elif match_mode == "number_eq":
                        found = abs(extracted_number - match_number) < 0.01
                except ValueError:
                    pass

        result = {
            "found": found,
            "text": full_text,
            "confidence": results[0][2] if results else 0.0,
            "number": extracted_number,
            "cost_ms": cost_ms,
            "_timestamp": time.perf_counter(),
        }

        if cache_key:
            self._last_result[cache_key] = result

        return result
