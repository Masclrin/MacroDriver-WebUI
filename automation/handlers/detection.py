import re
import os
import time
import threading

import cv2
import numpy as np

from automation.engine import (
    _resolve_value, _get_hwnd, _execute_flow, _do_click, _interpolated_move,
)
from automation.compiler import ExecNode
from automation.handlers.variable import _extract_var_name
from automation.engine import ExecContext
from automation.engine import _get_pause_event

from engine.precision import precise_sleep_v5 as precise_sleep, set_thread_affinity, clear_thread_affinity
from engine.input_sendinput import set_cursor_pos


def _parse_target_color(target_hex):
    if not target_hex or not isinstance(target_hex, str):
        return None
    m = re.match(r'^#([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$', target_hex.strip())
    if not m:
        return None
    r = int(m.group(1), 16)
    g = int(m.group(2), 16)
    b = int(m.group(3), 16)
    return (b, g, r)


def _invalidate_frame(ctx: ExecContext):
    """在"持续等待/轮询检测"的每一轮强制失效共享帧缓存。

    共享帧缓存的本意是：**同一次流程遍历里**的多个检测节点复用一次截图
    （它们看到的是同一瞬间的画面，安全且省 CPU）。

    但一个开了"持续等待"的检测节点，其内部 while 轮询在逻辑上是**不同瞬间**：
    它必须能看到战斗画面的实时变化。若轮询间隔(默认 16ms)小于帧缓存 TTL，
    轮询就会连续命中同一帧，"实时检测"退化成"盯着旧画面"，从而漏掉快速跃迁
    的血条/技能 CD 等状态。所以轮询每轮都显式作废缓存，强制抓新帧。
    """
    try:
        with ctx._data_lock:
            cm = getattr(ctx, "_capture_manager", None)
    except Exception:
        cm = getattr(ctx, "_capture_manager", None)
    if cm is not None:
        try:
            cm.invalidate_frame_cache()
        except Exception:
            pass


def _handle_capture_source(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from automation.detection.capture_manager import CaptureManager

        enabled = params.get("enabled", True)
        monitor_index = int(_resolve_value(params.get("monitor_index", 0), ctx))

        if enabled:
            fps = int(_resolve_value(params.get("fps", 60), ctx))

            with ctx._data_lock:
                if ctx._capture_manager is None:
                    ctx._capture_manager = CaptureManager(ctx)
                cm = ctx._capture_manager

            if cm.config_changed(fps, monitor_index):
                cm.stop_dxgi(output_idx=monitor_index)

            if not cm.is_dxgi_running(output_idx=monitor_index):
                success = cm.start_dxgi(fps=fps, output_idx=monitor_index)
                if not success:
                    ctx.log_error("DXGI 后台截图启动失败，已回退到 BitBlt", node_id=node.id)
        else:
            with ctx._data_lock:
                if ctx._capture_manager is not None:
                    ctx._capture_manager.stop_dxgi(output_idx=monitor_index)
    except Exception as e:
        print(f"[新引擎] 截图源节点出错: {e}")
        ctx.log_error(f"截图源节点出错: {e}", node_id=node.id, error_type="system")

    _execute_flow(node.id, "next", ctx)


def _handle_check_color(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from automation.detection.capture import capture_screen
        from automation.detection.color import check_color
        from engine.coordinate import resolve_region

        mode = params.get("mode", "screen")
        rect = _resolve_value(params.get("rect", [0, 0, 10, 10]), ctx)
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        region = resolve_region(mode, rect, hwnd)

        target_hex = _resolve_value(params.get("target_color", "#FF0000"), ctx)
        target_bgr = _parse_target_color(target_hex)
        if target_bgr is None:
            ctx.log_error(f"颜色值格式无效: '{target_hex}'，需要 #RRGGBB 格式", node_id=node.id, error_type="system")
            ctx.check_results[f"{node.id}.result"] = False
            ctx.check_results[f"{node.id}.color"] = ""
            _execute_flow(node.id, "no", ctx)
            return

        check_mode = params.get("check_mode", "contain")
        area_ratio_threshold = float(_resolve_value(params.get("area_ratio_threshold", 0.5), ctx))

        wait = params.get("wait", False)
        interval_ms = int(_resolve_value(params.get("wait_interval_ms", 16), ctx))
        timeout_ms = int(_resolve_value(params.get("wait_timeout_ms", 5000), ctx))

        def _do_check():
            img = capture_screen(region, ctx=ctx)
            result = check_color(
                img, target_bgr,
                int(_resolve_value(params.get("tolerance", 10), ctx)),
                check_mode,
                params.get("sample_mode", "center"),
                last_image=ctx.safe_get_cache(node.id),
                change_threshold=float(_resolve_value(params.get("change_threshold", 10), ctx)),
                area_ratio_threshold=area_ratio_threshold,
            )
            ctx.safe_set_cache(node.id, img)
            return result

        if not wait:
            result = _do_check()
            if params.get("store_var"):
                ctx.safe_set_variable(_extract_var_name(params["store_var"]), result.get("actual_color", ""))
            ctx.check_results[f"{node.id}.result"] = result["found"]
            ctx.check_results[f"{node.id}.color"] = result.get("actual_color", "")
            if result["found"]:
                _execute_flow(node.id, "match", ctx)
            else:
                _execute_flow(node.id, "no", ctx)
            return

        start_time = time.perf_counter()
        while not ctx.stop_event.is_set():
            _invalidate_frame(ctx)
            result = _do_check()
            if result["found"]:
                if params.get("store_var"):
                    ctx.safe_set_variable(_extract_var_name(params["store_var"]), result.get("actual_color", ""))
                ctx.check_results[f"{node.id}.result"] = True
                ctx.check_results[f"{node.id}.color"] = result.get("actual_color", "")
                _execute_flow(node.id, "match", ctx)
                return
            if timeout_ms > 0 and (time.perf_counter() - start_time) * 1000 > timeout_ms:
                ctx.check_results[f"{node.id}.result"] = False
                ctx.check_results[f"{node.id}.color"] = ""
                _execute_flow(node.id, "no", ctx)
                return
            precise_sleep(interval_ms / 1000.0, ctx.stop_event, pause_event=_get_pause_event(ctx))

        ctx.check_results[f"{node.id}.result"] = False
        ctx.check_results[f"{node.id}.color"] = ""
        _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] 颜色检测出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        ctx.check_results[f"{node.id}.color"] = ""
        _execute_flow(node.id, "no", ctx)


def _handle_check_ocr(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from automation.detection.capture import capture_screen
        from automation.detection.ocr import OCREngine
        from engine.coordinate import resolve_region

        mode = params.get("mode", "screen")
        rect = _resolve_value(params.get("rect", [0, 0, 100, 30]), ctx)
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        region = resolve_region(mode, rect, hwnd)

        wait = params.get("wait", False)
        interval_ms = int(_resolve_value(params.get("wait_interval_ms", 16), ctx))
        timeout_ms = int(_resolve_value(params.get("wait_timeout_ms", 5000), ctx))

        def _do_check():
            img = capture_screen(region, ctx=ctx)
            with ctx._data_lock:
                engine = ctx._ocr_engine
            if engine is None:
                engine = OCREngine()
                with ctx._data_lock:
                    if ctx._ocr_engine is None:
                        ctx._ocr_engine = engine
                    else:
                        engine = ctx._ocr_engine
            match_number = None
            if params.get("match_mode", "contain").startswith("number_"):
                match_number = float(_resolve_value(params.get("match_number", 0), ctx))

            detect_args = dict(
                match_text=_resolve_value(params.get("match_text", ""), ctx),
                match_mode=params.get("match_mode", "contain"),
                match_number=match_number,
                cache_key=node.id,
                last_image=ctx.safe_get_cache(node.id),
                cache_strategy=params.get("cache_strategy", "disabled"),
                cache_interval_ms=int(_resolve_value(params.get("cache_interval_ms", 100), ctx)),
            )

            ocr_core = ctx._ocr_affinity_core
            if ocr_core >= 0:
                result_holder = {}
                error_holder = {}

                def _run_ocr():
                    try:
                        set_thread_affinity(ocr_core)
                        result_holder["data"] = engine.detect(img, **detect_args)
                    except Exception as e:
                        error_holder["error"] = e
                    finally:
                        clear_thread_affinity()

                t = threading.Thread(target=_run_ocr, daemon=True)
                t.start()
                t.join(timeout=30)
                if error_holder:
                    raise error_holder["error"]
                result = result_holder.get("data")
                if result is None:
                    raise RuntimeError("OCR thread returned no result")
            else:
                result = engine.detect(img, **detect_args)

            ctx.safe_set_cache(node.id, img)
            return result

        def _store_result(result):
            if params.get("store_var"):
                ctx.safe_set_variable(_extract_var_name(params["store_var"]), result.get("text", ""))
            elif not params.get("match_text", "") and result.get("text", ""):
                ctx.safe_set_variable(node.id + "_ocr_text", result.get("text", ""))
            if params.get("store_number") and result.get("number") is not None:
                ctx.safe_set_variable(_extract_var_name(params["store_number"]), result["number"])
            elif not params.get("match_text", "") and result.get("number") is not None:
                ctx.safe_set_variable(node.id + "_ocr_number", result["number"])
            ctx.check_results[f"{node.id}.result"] = result["found"]
            ctx.check_results[f"{node.id}.text"] = result.get("text", "")
            ocr_number = result.get("number")
            ctx.check_results[f"{node.id}.number"] = ocr_number if ocr_number is not None else 0

        if not wait:
            result = _do_check()
            _store_result(result)
            if result["found"]:
                _execute_flow(node.id, "match", ctx)
            else:
                _execute_flow(node.id, "no", ctx)
            return

        start_time = time.perf_counter()
        while not ctx.stop_event.is_set():
            _invalidate_frame(ctx)
            result = _do_check()
            if result["found"]:
                _store_result(result)
                _execute_flow(node.id, "match", ctx)
                return
            if timeout_ms > 0 and (time.perf_counter() - start_time) * 1000 > timeout_ms:
                _store_result(result)
                _execute_flow(node.id, "no", ctx)
                return
            precise_sleep(interval_ms / 1000.0, ctx.stop_event, pause_event=_get_pause_event(ctx))

        ctx.check_results[f"{node.id}.result"] = False
        ctx.check_results[f"{node.id}.text"] = ""
        ctx.check_results[f"{node.id}.number"] = 0
        _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] OCR检测出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        ctx.check_results[f"{node.id}.text"] = ""
        ctx.check_results[f"{node.id}.number"] = 0
        _execute_flow(node.id, "no", ctx)


def _match_template_pyramid(img, template, threshold, method, max_levels=2):
    if max_levels <= 0:
        result = cv2.matchTemplate(img, template, method)
        return result, img, template

    img_pyr = [img]
    tpl_pyr = [template]
    for _ in range(max_levels):
        img_pyr.append(cv2.pyrDown(img_pyr[-1]))
        tpl_pyr.append(cv2.pyrDown(tpl_pyr[-1]))

    smallest_img = img_pyr[-1]
    smallest_tpl = tpl_pyr[-1]

    if smallest_img.shape[0] < smallest_tpl.shape[0] or smallest_img.shape[1] < smallest_tpl.shape[1]:
        result = cv2.matchTemplate(img, template, method)
        return result, img, template

    coarse_result = cv2.matchTemplate(smallest_img, smallest_tpl, method)

    if method == cv2.TM_SQDIFF_NORMED:
        _, min_val, _, min_loc = cv2.minMaxLoc(coarse_result)
        if min_val > (1 - threshold):
            return None, img, template
        best_loc = min_loc
    else:
        _, max_val, _, max_loc = cv2.minMaxLoc(coarse_result)
        if max_val < threshold:
            return None, img, template
        best_loc = max_loc

    scale = 2 ** max_levels
    coarse_x = best_loc[0] * scale
    coarse_y = best_loc[1] * scale

    th, tw = template.shape[:2]
    margin_x = max(tw // 2, 32)
    margin_y = max(th // 2, 32)

    roi_x1 = max(0, coarse_x - margin_x)
    roi_y1 = max(0, coarse_y - margin_y)
    roi_x2 = min(img.shape[1], coarse_x + tw + margin_x)
    roi_y2 = min(img.shape[0], coarse_y + th + margin_y)

    roi = img[roi_y1:roi_y2, roi_x1:roi_x2]

    if roi.shape[0] < template.shape[0] or roi.shape[1] < template.shape[1]:
        result = cv2.matchTemplate(img, template, method)
        return result, img, template

    fine_result = cv2.matchTemplate(roi, template, method)
    return fine_result, roi, template, (roi_x1, roi_y1)


def _frame_diff_threshold(img_shape, template_shape=None):
    """按 ROI 面积自适应的帧差阈值。

    原先硬编码 diff < 2.0（整区域平均绝对差）。在「大区域 + 小目标」场景下
    这会**永久误判为画面未变化**，从而一直返回陈旧缓存里的 found=False：

        500x300 区域中出现 40x40 的技能图标（像素差约 60）：
        diff ≈ (40*40)/(500*300) * 60 ≈ 0.64 < 2.0  →  命中"无变化"

    修正方式：把阈值按「目标面积 / 区域面积」缩放，目标占比越小阈值越低。
    同时用下限 0.02 防止纯噪声被当作"有变化"而彻底失去缓存意义。
    """
    h, w = img_shape[:2]
    area = max(1, int(h) * int(w))
    if template_shape is None:
        return 2.0
    th, tw = template_shape[:2]
    tarea = max(1, int(th) * int(tw))
    ratio = min(1.0, tarea / float(area))
    return max(0.02, min(2.0, 16.0 * ratio))


def do_image_match(img, template_path, threshold=0.8, method=cv2.TM_CCOEFF_NORMED,
                   pyramid_levels=2, ctx=None,
                   cache_strategy=None, cache_interval_ms=100, cache_key=None):
    from automation.detection.image_cache import load_template

    template = load_template(template_path)
    if template is None:
        return {"found": False, "match_x": 0, "match_y": 0, "confidence": 0.0}

    if cache_strategy and cache_key and ctx:
        last_img = ctx.safe_get_cache(cache_key)
        if cache_strategy != "disabled" and last_img is not None:
                if img.shape == last_img.shape:
                    if cache_strategy == "frame_diff":
                        diff = np.mean(np.abs(img.astype(float) - last_img.astype(float)))
                        if diff < _frame_diff_threshold(img.shape, template.shape):
                            with ctx._image_match_cache_lock:
                                cached = ctx._image_match_cache.get(cache_key)
                        if cached:
                            return dict(cached)
                elif cache_strategy == "time_interval":
                    with ctx._image_match_cache_lock:
                        cached = ctx._image_match_cache.get(cache_key)
                    if cached:
                        now = time.perf_counter()
                        if (now - cached.get("_timestamp", 0)) * 1000 < cache_interval_ms:
                            return cached
        ctx.safe_set_cache(cache_key, img)

    use_pyramid = (
        pyramid_levels > 0
        and img.shape[0] * img.shape[1] > 500 * 500
        and template.shape[0] * template.shape[1] > 50 * 50
    )

    if use_pyramid:
        pyr_result = _match_template_pyramid(img, template, threshold, method, max_levels=pyramid_levels)
        if pyr_result[0] is None:
            result_data = {"found": False, "match_x": 0, "match_y": 0, "confidence": 0.0}
            if cache_strategy and cache_key and ctx and cache_strategy != "disabled":
                result_data["_timestamp"] = time.perf_counter()
                with ctx._image_match_cache_lock:
                    ctx._image_match_cache[cache_key] = result_data
            return result_data

        fine_result = pyr_result[0]
        roi_offset = pyr_result[3] if len(pyr_result) > 3 else (0, 0)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(fine_result)
        if method == cv2.TM_SQDIFF_NORMED:
            found = min_val <= (1 - threshold)
            match_loc = min_loc
            confidence = 1.0 - min_val
        else:
            found = max_val >= threshold
            match_loc = max_loc
            confidence = max_val

        match_x_val = 0
        match_y_val = 0
        if found:
            match_x_val = int(match_loc[0] + template.shape[1] / 2 + roi_offset[0])
            match_y_val = int(match_loc[1] + template.shape[0] / 2 + roi_offset[1])

        result_data = {"found": found, "match_x": match_x_val, "match_y": match_y_val, "confidence": float(confidence)}
        if cache_strategy and cache_key and ctx and cache_strategy != "disabled":
            result_data["_timestamp"] = time.perf_counter()
            with ctx._image_match_cache_lock:
                ctx._image_match_cache[cache_key] = result_data
        return result_data

    result = cv2.matchTemplate(img, template, method)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    if method == cv2.TM_SQDIFF_NORMED:
        found = min_val <= (1 - threshold)
        match_loc = min_loc
        confidence = 1.0 - min_val
    else:
        found = max_val >= threshold
        match_loc = max_loc
        confidence = max_val

    match_x_val = 0
    match_y_val = 0
    if found:
        match_x_val = int(match_loc[0] + template.shape[1] / 2)
        match_y_val = int(match_loc[1] + template.shape[0] / 2)

    result_data = {"found": found, "match_x": match_x_val, "match_y": match_y_val, "confidence": float(confidence)}
    if cache_strategy and cache_key and ctx and cache_strategy != "disabled":
        result_data["_timestamp"] = time.perf_counter()
        with ctx._image_match_cache_lock:
            ctx._image_match_cache[cache_key] = result_data
    return result_data


def _handle_check_image(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from automation.detection.capture import capture_screen
        from automation.detection.image_cache import load_template
        from engine.coordinate import resolve_region

        mode = params.get("mode", "screen")
        rect = _resolve_value(params.get("rect", [0, 0, 0, 0]), ctx)
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        template_path = _resolve_value(params.get("template_path", ""), ctx)

        if not template_path:
            ctx.check_results[f"{node.id}.result"] = False
            _execute_flow(node.id, "no", ctx)
            return

        if all(float(v) == 0 for v in rect):
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
            region = (0, 0, sw, sh)
        else:
            region = resolve_region(mode, rect, hwnd)

        method_map = {
            "tm_ccoeff_normed": cv2.TM_CCOEFF_NORMED,
            "tm_ccorr_normed": cv2.TM_CCORR_NORMED,
            "tm_sqdiff_normed": cv2.TM_SQDIFF_NORMED,
        }
        method = method_map.get(params.get("method", "tm_ccoeff_normed"), cv2.TM_CCOEFF_NORMED)
        threshold = float(_resolve_value(params.get("threshold", 0.8), ctx))
        multi_match = params.get("multi_match", False)
        pyramid_levels = int(_resolve_value(params.get("pyramid_levels", 2), ctx))

        wait = params.get("wait", False)
        interval_ms = int(_resolve_value(params.get("wait_interval_ms", 16), ctx))
        timeout_ms = int(_resolve_value(params.get("wait_timeout_ms", 5000), ctx))

        cache_key = node.id
        cache_strat = params.get("cache_strategy", "disabled")
        cache_interval = int(_resolve_value(params.get("cache_interval_ms", 100), ctx))

        def _cache_and_return(result):
            if cache_strat != "disabled":
                result["_timestamp"] = time.perf_counter()
                with ctx._image_match_cache_lock:
                    ctx._image_match_cache[cache_key] = result
            return result

        def _do_check_image():
            all_matches = None
            template = load_template(template_path)
            if template is None:
                return {"found": False, "match_x": 0, "match_y": 0, "confidence": 0.0}

            # 缓存判定移到截图之前：命中时连最贵的那一步也省掉。
            # （原实现先花 13.7ms 全屏截图，再判定缓存并丢弃刚截的图）
            if cache_strat == "time_interval" and cache_interval > 0:
                with ctx._image_match_cache_lock:
                    cached = ctx._image_match_cache.get(cache_key)
                if cached:
                    now = time.perf_counter()
                    if (now - cached.get("_timestamp", 0)) * 1000 < cache_interval:
                        return dict(cached)

            img = capture_screen(region, ctx=ctx)
            if img is None:
                return {"found": False, "match_x": 0, "match_y": 0, "confidence": 0.0}
            last_img = ctx.safe_get_cache(cache_key)

            if cache_strat != "disabled" and last_img is not None:
                if img.shape == last_img.shape:
                    if cache_strat == "frame_diff":
                        diff = np.mean(np.abs(img.astype(float) - last_img.astype(float)))
                        if diff < _frame_diff_threshold(img.shape, template.shape):
                            with ctx._image_match_cache_lock:
                                cached = ctx._image_match_cache.get(cache_key)
                            if cached:
                                return dict(cached)

            ctx.safe_set_cache(cache_key, img)

            use_pyramid = (
                pyramid_levels > 0
                and img.shape[0] * img.shape[1] > 500 * 500
                and template.shape[0] * template.shape[1] > 50 * 50
            )

            if use_pyramid:
                pyr_result = _match_template_pyramid(img, template, threshold, method, max_levels=pyramid_levels)
                if pyr_result[0] is None:
                    return _cache_and_return({"found": False, "match_x": 0, "match_y": 0, "confidence": 0.0})

                fine_result = pyr_result[0]
                roi_offset = pyr_result[3] if len(pyr_result) > 3 else (0, 0)

                if multi_match:
                    if method == cv2.TM_SQDIFF_NORMED:
                        locs = np.where(fine_result <= (1 - threshold))
                    else:
                        locs = np.where(fine_result >= threshold)
                    matches = list(zip(*locs[::-1]))
                    found = len(matches) > 0
                    match_x_val = 0
                    match_y_val = 0
                    confidence = 0.0
                    if found:
                        match_x_val = int(matches[0][0] + template.shape[1] / 2 + roi_offset[0])
                        match_y_val = int(matches[0][1] + template.shape[0] / 2 + roi_offset[1])
                        if method == cv2.TM_SQDIFF_NORMED:
                            confidence = 1.0 - float(fine_result[matches[0][1], matches[0][0]])
                        else:
                            confidence = float(fine_result[matches[0][1], matches[0][0]])
                        all_matches = [
                            {"x": int(x + template.shape[1] / 2 + roi_offset[0]), "y": int(y + template.shape[0] / 2 + roi_offset[1])}
                            for x, y in matches[:10]
                        ]
                else:
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(fine_result)
                    if method == cv2.TM_SQDIFF_NORMED:
                        found = min_val <= (1 - threshold)
                        match_loc = min_loc
                        confidence = 1.0 - min_val
                    else:
                        found = max_val >= threshold
                        match_loc = max_loc
                        confidence = max_val
                    match_x_val = 0
                    match_y_val = 0
                    if found:
                        match_x_val = int(match_loc[0] + template.shape[1] / 2 + roi_offset[0])
                        match_y_val = int(match_loc[1] + template.shape[0] / 2 + roi_offset[1])
                        if params.get("store_var"):
                            ctx.safe_set_variable(_extract_var_name(params["store_var"]), {
                                "x": match_x_val,
                                "y": match_y_val,
                                "confidence": float(confidence),
                            })
                    else:
                        confidence = 0.0

                return _cache_and_return({"found": found, "match_x": match_x_val, "match_y": match_y_val, "confidence": float(confidence),
                        "all_matches": all_matches if multi_match else None})

            result = cv2.matchTemplate(img, template, method)
            match_x_val = 0
            match_y_val = 0
            confidence = 0.0

            if multi_match:
                if method == cv2.TM_SQDIFF_NORMED:
                    locs = np.where(result <= (1 - threshold))
                else:
                    locs = np.where(result >= threshold)
                matches = list(zip(*locs[::-1]))
                found = len(matches) > 0
                if found:
                    match_x_val = int(matches[0][0] + template.shape[1] / 2)
                    match_y_val = int(matches[0][1] + template.shape[0] / 2)
                    if method == cv2.TM_SQDIFF_NORMED:
                        confidence = 1.0 - float(result[matches[0][1], matches[0][0]])
                    else:
                        confidence = float(result[matches[0][1], matches[0][0]])
                    all_matches = [
                        {"x": int(x + template.shape[1] / 2), "y": int(y + template.shape[0] / 2)}
                        for x, y in matches[:10]
                    ]
            else:
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                if method == cv2.TM_SQDIFF_NORMED:
                    found = min_val <= (1 - threshold)
                    match_loc = min_loc
                    confidence = 1.0 - min_val
                else:
                    found = max_val >= threshold
                    match_loc = max_loc
                    confidence = max_val
                if found:
                    match_x_val = int(match_loc[0] + template.shape[1] / 2)
                    match_y_val = int(match_loc[1] + template.shape[0] / 2)
                    if params.get("store_var"):
                        ctx.safe_set_variable(_extract_var_name(params["store_var"]), {
                            "x": match_x_val,
                            "y": match_y_val,
                            "confidence": float(confidence),
                        })
                else:
                    confidence = 0.0

            return _cache_and_return({"found": found, "match_x": match_x_val, "match_y": match_y_val, "confidence": float(confidence),
                    "all_matches": all_matches if multi_match else None})

        if not wait:
            check_result = _do_check_image()
            ctx.check_results[f"{node.id}.result"] = check_result["found"]
            ctx.check_results[f"{node.id}.match_x"] = check_result["match_x"]
            ctx.check_results[f"{node.id}.match_y"] = check_result["match_y"]
            ctx.check_results[f"{node.id}.confidence"] = check_result["confidence"]
            if params.get("store_var"):
                if check_result.get("all_matches") is not None:
                    ctx.safe_set_variable(_extract_var_name(params["store_var"]), check_result["all_matches"])
                elif check_result["found"]:
                    ctx.safe_set_variable(_extract_var_name(params["store_var"]), {
                        "x": check_result["match_x"],
                        "y": check_result["match_y"],
                        "confidence": check_result["confidence"]
                    })
            if check_result["found"]:
                _execute_flow(node.id, "match", ctx)
            else:
                _execute_flow(node.id, "no", ctx)
            return

        start_time = time.perf_counter()
        while not ctx.stop_event.is_set():
            _invalidate_frame(ctx)
            check_result = _do_check_image()
            if check_result["found"]:
                ctx.check_results[f"{node.id}.result"] = True
                ctx.check_results[f"{node.id}.match_x"] = check_result["match_x"]
                ctx.check_results[f"{node.id}.match_y"] = check_result["match_y"]
                ctx.check_results[f"{node.id}.confidence"] = check_result["confidence"]
                if params.get("store_var"):
                    if check_result.get("all_matches") is not None:
                        ctx.safe_set_variable(_extract_var_name(params["store_var"]), check_result["all_matches"])
                    else:
                        ctx.safe_set_variable(_extract_var_name(params["store_var"]), {
                            "x": check_result["match_x"],
                            "y": check_result["match_y"],
                            "confidence": check_result["confidence"]
                        })
                _execute_flow(node.id, "match", ctx)
                return
            if timeout_ms > 0 and (time.perf_counter() - start_time) * 1000 > timeout_ms:
                ctx.check_results[f"{node.id}.result"] = False
                ctx.check_results[f"{node.id}.match_x"] = 0
                ctx.check_results[f"{node.id}.match_y"] = 0
                ctx.check_results[f"{node.id}.confidence"] = 0.0
                _execute_flow(node.id, "no", ctx)
                return
            precise_sleep(interval_ms / 1000.0, ctx.stop_event, pause_event=_get_pause_event(ctx))

        ctx.check_results[f"{node.id}.result"] = False
        ctx.check_results[f"{node.id}.match_x"] = 0
        ctx.check_results[f"{node.id}.match_y"] = 0
        ctx.check_results[f"{node.id}.confidence"] = 0.0
        _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] 图像匹配出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        ctx.check_results[f"{node.id}.match_x"] = 0
        ctx.check_results[f"{node.id}.match_y"] = 0
        ctx.check_results[f"{node.id}.confidence"] = 0.0
        _execute_flow(node.id, "no", ctx)


def _handle_check_screen(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from automation.detection.capture import capture_screen
        from engine.coordinate import resolve_region

        state = params.get("state", "black")
        threshold = float(_resolve_value(params.get("threshold", 30), ctx))
        frozen_duration_ms = float(_resolve_value(params.get("frozen_duration_ms", 200), ctx))
        region_param = _resolve_value(params.get("region", [0, 0, 0, 0]), ctx)

        mode = params.get("mode", "screen")
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

        if all(float(v) == 0 for v in region_param):
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
            region = (0, 0, sw, sh)
        else:
            region = resolve_region(mode, region_param, hwnd)

        wait = params.get("wait", False)
        interval_ms = int(_resolve_value(params.get("wait_interval_ms", 16), ctx))
        timeout_ms = int(_resolve_value(params.get("wait_timeout_ms", 5000), ctx))

        def _do_check_screen():
            img = capture_screen(region, ctx=ctx)
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            mean_brightness = float(np.mean(gray))

            if state == "black":
                found = mean_brightness < threshold
            elif state == "bright":
                found = mean_brightness > (255 - threshold)
            elif state == "frozen":
                last_img = ctx.safe_get_cache(node.id)
                ctx.safe_set_cache(node.id, img)
                if last_img is not None:
                    if len(img.shape) == 3:
                        gray_cur = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    else:
                        gray_cur = img
                    if len(last_img.shape) == 3:
                        gray_last = cv2.cvtColor(last_img, cv2.COLOR_BGR2GRAY)
                    else:
                        gray_last = last_img
                    diff = float(np.mean(np.abs(gray_cur.astype(float) - gray_last.astype(float))))
                    found = diff < threshold
                else:
                    found = False
            else:
                found = False
            return found

        if not wait:
            if state == "frozen":
                frozen_start = time.perf_counter()
                frozen_seconds = frozen_duration_ms / 1000.0
                frozen_ok = True
                prev_img = capture_screen(region, ctx=ctx)
                while not ctx.stop_event.is_set():
                    precise_sleep(0.02, ctx.stop_event, pause_event=_get_pause_event(ctx))
                    cur_img = capture_screen(region, ctx=ctx)
                    if len(prev_img.shape) == 3:
                        gray_prev = cv2.cvtColor(prev_img, cv2.COLOR_BGR2GRAY)
                    else:
                        gray_prev = prev_img
                    if len(cur_img.shape) == 3:
                        gray_cur = cv2.cvtColor(cur_img, cv2.COLOR_BGR2GRAY)
                    else:
                        gray_cur = cur_img
                    diff = float(np.mean(np.abs(gray_cur.astype(float) - gray_prev.astype(float))))
                    if diff >= threshold:
                        frozen_ok = False
                        break
                    prev_img = cur_img
                    if (time.perf_counter() - frozen_start) >= frozen_seconds:
                        break
                found = frozen_ok
            else:
                found = _do_check_screen()
            ctx.check_results[f"{node.id}.result"] = found
            if found:
                _execute_flow(node.id, "match", ctx)
            else:
                _execute_flow(node.id, "no", ctx)
            return

        start_time = time.perf_counter()
        while not ctx.stop_event.is_set():
            _invalidate_frame(ctx)
            found = _do_check_screen()
            if found:
                ctx.check_results[f"{node.id}.result"] = True
                _execute_flow(node.id, "match", ctx)
                return
            if timeout_ms > 0 and (time.perf_counter() - start_time) * 1000 > timeout_ms:
                ctx.check_results[f"{node.id}.result"] = False
                _execute_flow(node.id, "no", ctx)
                return
            precise_sleep(interval_ms / 1000.0, ctx.stop_event, pause_event=_get_pause_event(ctx))

        ctx.check_results[f"{node.id}.result"] = False
        _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] 屏幕状态检测出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        _execute_flow(node.id, "no", ctx)


def _load_digit_templates(root_folder):
    result = {}
    try:
        for font_dir in os.listdir(root_folder):
            font_path = os.path.join(root_folder, font_dir)
            if not os.path.isdir(font_path):
                continue
            font_templates = {}
            for digit in range(10):
                img_path = os.path.join(font_path, f"{digit}.png")
                if os.path.exists(img_path):
                    template = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        font_templates[digit] = template
            if font_templates:
                result[font_dir] = font_templates
    except Exception:
        pass
    return result


def _binarize_image(gray, method="otsu"):
    if method == "adaptive_gaussian":
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 5
        )
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _hamming_match(roi, template_bin):
    if roi.shape != template_bin.shape:
        roi_resized = cv2.resize(roi, (template_bin.shape[1], template_bin.shape[0]),
                                 interpolation=cv2.INTER_NEAREST)
    else:
        roi_resized = roi
    roi_bin = (roi_resized > 127).astype(np.uint8)
    total_pixels = roi_bin.size
    if total_pixels == 0:
        return 0.0
    diff = np.count_nonzero(roi_bin != template_bin)
    return 1.0 - diff / total_pixels


def _handle_check_digits(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from automation.detection.capture import capture_screen
        from engine.coordinate import resolve_region

        mode = params.get("mode", "screen")
        rect = _resolve_value(params.get("rect", [0, 0, 0, 0]), ctx)
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        template_folder = _resolve_value(params.get("template_folder", ""), ctx)

        if not template_folder or not os.path.isdir(template_folder):
            ctx.check_results[f"{node.id}.digit_value"] = -1
            ctx.check_results[f"{node.id}.match_conf"] = 0.0
            _execute_flow(node.id, "fail", ctx)
            return

        template_sets_raw = str(_resolve_value(params.get("template_sets", ""), ctx))
        selected_sets = [s.strip() for s in template_sets_raw.split(',') if s.strip()] if template_sets_raw else []
        match_method = params.get("match_method", "auto")
        binary_method = params.get("binary_method", "otsu")
        threshold = float(_resolve_value(params.get("threshold", 0.8), ctx))
        split_method = params.get("split_method", "contour")
        split_width = int(_resolve_value(params.get("split_width", 0), ctx))
        compare_op = params.get("compare_op", "none")
        compare_value = float(_resolve_value(params.get("compare_value", 0), ctx))
        store_var = params.get("store_var", "")
        wait = params.get("wait", False)
        interval_ms = int(_resolve_value(params.get("wait_interval_ms", 50), ctx))
        timeout_ms = int(_resolve_value(params.get("wait_timeout_ms", 5000), ctx))

        if all(float(v) == 0 for v in rect):
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
            region = (0, 0, sw, sh)
        else:
            region = resolve_region(mode, rect, hwnd)

        cache_key = f"digits_{abs(hash(template_folder))}"
        with ctx._data_lock:
            templates = ctx._digit_template_cache.get(cache_key)
        if not templates:
            templates = _load_digit_templates(template_folder)
            with ctx._data_lock:
                ctx._digit_template_cache[cache_key] = templates

        if not templates:
            ctx.log_error("数字匹配: 模板文件夹中未找到有效的 0-9.png 数字模板", node_id=node.id, error_type="param")
            ctx.check_results[f"{node.id}.digit_value"] = -1
            ctx.check_results[f"{node.id}.match_conf"] = 0.0
            _execute_flow(node.id, "fail", ctx)
            return

        if selected_sets:
            filtered = {}
            for name in selected_sets:
                if name in templates:
                    filtered[name] = templates[name]
            if filtered:
                templates = filtered

        first_template = None
        for ft in templates.values():
            for tpl in ft.values():
                first_template = tpl
                break
            if first_template is not None:
                break

        templates_bin = {}
        for name, ft in templates.items():
            templates_bin[name] = {}
            for digit_val, tpl in ft.items():
                templates_bin[name][digit_val] = (tpl > 127).astype(np.uint8)

        tpl_h, tpl_w = (first_template.shape[0], first_template.shape[1]) if first_template is not None else (0, 0)

        def _do_check():
            img = capture_screen(region, ctx=ctx)
            if img is None:
                return None, 0.0
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            binary = _binarize_image(gray, binary_method)

            if np.mean(binary > 127) > 0.5:
                binary = 255 - binary

            rois = []
            if split_method == "fixed_width":
                w = split_width if split_width > 0 else max(1, binary.shape[1] // 5)
                h = binary.shape[0]
                num_segments = binary.shape[1] // w
                for i in range(num_segments):
                    roi = binary[:, i * w:(i + 1) * w]
                    rois.append(roi)
            elif split_method == "projection":
                min_char_width = split_width if split_width > 0 else 2
                proj = np.sum(binary > 127, axis=0)
                max_proj = np.max(proj) if proj.size > 0 else 1
                gap_threshold = max_proj * 0.1
                in_char = False
                start = 0
                for col in range(binary.shape[1]):
                    if proj[col] > gap_threshold:
                        if not in_char:
                            start = col
                            in_char = True
                    else:
                        if in_char:
                            end = col
                            if end - start >= min_char_width:
                                roi = binary[:, start:end]
                                rois.append(roi)
                            in_char = False
                if in_char:
                    end = binary.shape[1]
                    if end - start >= min_char_width:
                        roi = binary[:, start:end]
                        rois.append(roi)
            else:
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                valid_contours = []
                for c in contours:
                    xc, yc, wc, hc = cv2.boundingRect(c)
                    if wc > 1 and hc > 3:
                        valid_contours.append(c)
                valid_contours.sort(key=lambda c: cv2.boundingRect(c)[0])
                for c in valid_contours:
                    xc, yc, wc, hc = cv2.boundingRect(c)
                    roi = binary[yc:yc + hc, xc:xc + wc]
                    rois.append(roi)

            if not rois:
                return None, 0.0

            use_hamming = False
            if match_method == "hamming":
                use_hamming = True
            elif match_method == "auto":
                if first_template is not None:
                    all_same_size = all(
                        roi.shape[0] == tpl_h and roi.shape[1] == tpl_w
                        for roi in rois
                    )
                    use_hamming = all_same_size

            digit_str = ""
            total_conf = 0.0
            for roi in rois:
                if roi.shape[0] < 2 or roi.shape[1] < 1:
                    continue
                best_digit = -1
                best_score = 0.0

                if use_hamming:
                    for name, ft_bin in templates_bin.items():
                        for digit_val, tpl_bin in ft_bin.items():
                            score = _hamming_match(roi, tpl_bin)
                            if score > best_score:
                                best_score = score
                                best_digit = digit_val
                else:
                    for name, ft in templates.items():
                        for digit_val, template in ft.items():
                            if template.shape[0] > roi.shape[0] or template.shape[1] > roi.shape[1]:
                                roi_resized = cv2.resize(roi, (template.shape[1], template.shape[0]),
                                                         interpolation=cv2.INTER_NEAREST)
                            else:
                                roi_resized = roi
                            try:
                                result = cv2.matchTemplate(roi_resized, template, cv2.TM_CCOEFF_NORMED)
                                _, max_val, _, _ = cv2.minMaxLoc(result)
                                if max_val > best_score:
                                    best_score = max_val
                                    best_digit = digit_val
                            except Exception:
                                continue

                if best_score >= threshold and best_digit >= 0:
                    digit_str += str(best_digit)
                    total_conf += best_score
                else:
                    return None, 0.0

            avg_conf = total_conf / len(digit_str) if digit_str else 0.0
            return digit_str, avg_conf

        def _check_compare(digit_str_val):
            if compare_op == "none":
                return True
            try:
                digit_val = int(digit_str_val)
            except (ValueError, TypeError):
                return False
            cv = compare_value
            if compare_op == "eq":
                return digit_val == cv
            elif compare_op == "ne":
                return digit_val != cv
            elif compare_op == "gt":
                return digit_val > cv
            elif compare_op == "gte":
                return digit_val >= cv
            elif compare_op == "lt":
                return digit_val < cv
            elif compare_op == "lte":
                return digit_val <= cv
            return True

        if not wait:
            digit_str, avg_conf = _do_check()
            if digit_str is not None and _check_compare(digit_str):
                val = int(digit_str)
                ctx.check_results[f"{node.id}.digit_value"] = val
                ctx.check_results[f"{node.id}.match_conf"] = avg_conf
                if store_var:
                    ctx.safe_set_variable(_extract_var_name(store_var), val)
                _execute_flow(node.id, "pass", ctx)
            else:
                ctx.check_results[f"{node.id}.digit_value"] = -1
                ctx.check_results[f"{node.id}.match_conf"] = 0.0
                _execute_flow(node.id, "fail", ctx)
            return

        start_time = time.perf_counter()
        while not ctx.stop_event.is_set():
            _invalidate_frame(ctx)
            digit_str, avg_conf = _do_check()
            if digit_str is not None and _check_compare(digit_str):
                val = int(digit_str)
                ctx.check_results[f"{node.id}.digit_value"] = val
                ctx.check_results[f"{node.id}.match_conf"] = avg_conf
                if store_var:
                    ctx.safe_set_variable(_extract_var_name(store_var), val)
                _execute_flow(node.id, "pass", ctx)
                return
            if timeout_ms > 0 and (time.perf_counter() - start_time) * 1000 > timeout_ms:
                ctx.check_results[f"{node.id}.digit_value"] = -1
                ctx.check_results[f"{node.id}.match_conf"] = 0.0
                _execute_flow(node.id, "fail", ctx)
                return
            precise_sleep(interval_ms / 1000.0, ctx.stop_event, pause_event=_get_pause_event(ctx))

        ctx.check_results[f"{node.id}.digit_value"] = -1
        ctx.check_results[f"{node.id}.match_conf"] = 0.0
        _execute_flow(node.id, "fail", ctx)
    except Exception as e:
        print(f"[新引擎] 数字匹配出错: {e}")
        ctx.check_results[f"{node.id}.digit_value"] = -1
        ctx.check_results[f"{node.id}.match_conf"] = 0.0
        _execute_flow(node.id, "fail", ctx)


def register(handlers: dict):
    handlers["_handle_capture_source"] = _handle_capture_source
    handlers["_handle_check_color"] = _handle_check_color
    handlers["_handle_check_ocr"] = _handle_check_ocr
    handlers["_handle_check_image"] = _handle_check_image
    handlers["_handle_check_screen"] = _handle_check_screen
    handlers["_handle_check_digits"] = _handle_check_digits
