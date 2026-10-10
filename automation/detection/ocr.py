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
               cache_strategy="disabled", cache_interval_ms=100):
        # 默认禁用缓存：OCR 单次约 190ms，返回 100ms 前的结果对实时战斗毫无意义，
        # 且 _last_result 跨循环迭代从不失效。
        if cache_key and cache_strategy != "disabled" and last_image is not None:
            if image.shape == last_image.shape:
                if cache_strategy == "frame_diff":
                    diff = np.mean(np.abs(image.astype(float) - last_image.astype(float)))
                    # OCR 没有固定模板，按 ROI 面积做保守缩放（等效 80x80 目标）
                    thr = max(0.02, min(2.0, 16.0 * min(1.0, 6400.0 / max(1, image.shape[0] * image.shape[1]))))
                    if diff < thr:
                        cached = self._last_result.get(cache_key)
                        if cached:
                            # 返回副本：原实现原地改 cached["cost_ms"] 后返回同一 dict，
                            # 调用方若修改结果会污染缓存。
                            out = dict(cached)
                            out["cost_ms"] = 0.1
                            return out
                elif cache_strategy == "time_interval":
                    cached = self._last_result.get(cache_key)
                    if cached:
                        now = time.perf_counter()
                        if (now - cached.get("_timestamp", 0)) * 1000 < cache_interval_ms:
                            out = dict(cached)
                            out["cost_ms"] = 0.1
                            return out

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
            found = full_text.strip() == match_text if match_text else False
        elif match_mode == "regex":
            if match_text:
                try:
                    found = bool(re.search(match_text, full_text))
                except re.error:
                    found = False
            else:
                found = False
        elif match_mode in ("number_gt", "number_lt", "number_eq"):
            numbers = re.findall(r'[\d.]+', full_text)
            if numbers and match_number is not None:
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
            "confidence": float(results[0][2]) if results else 0.0,
            "number": extracted_number,
            "cost_ms": cost_ms,
            "_timestamp": time.perf_counter(),
        }

        if cache_key:
            self._last_result[cache_key] = result

        return result
