from automation.engine import (
    _resolve_value, _get_hwnd, _execute_flow, _do_click, _interpolated_move,
)
from automation.compiler import ExecNode
from automation.engine import ExecContext

from engine.precision import precise_sleep_v5 as precise_sleep
from engine.input_sendinput import set_cursor_pos


def _handle_check_color(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from automation.detection.capture import capture_screen
        from automation.detection.color import check_color
        from engine.coordinate import resolve_region

        mode = params.get("mode", "screen")
        rect = params.get("rect", [0, 0, 10, 10])
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        region = resolve_region(mode, rect, hwnd)
        img = capture_screen(region)

        target_hex = params.get("target_color", "#FF0000")
        r = int(target_hex[1:3], 16)
        g = int(target_hex[3:5], 16)
        b = int(target_hex[5:7], 16)
        target_bgr = (b, g, r)

        result = check_color(
            img, target_bgr,
            int(params.get("tolerance", 10)),
            params.get("check_mode", "contain"),
            params.get("sample_mode", "center"),
            last_image=ctx.last_capture_cache.get(node.id),
            change_threshold=float(params.get("change_threshold", 10)),
        )

        ctx.last_capture_cache[node.id] = img

        if params.get("store_var"):
            ctx.variables[params["store_var"]] = result.get("actual_color", "")

        ctx.check_results[f"{node.id}.result"] = result["found"]
        ctx.check_results[f"{node.id}.color"] = result.get("actual_color", "")

        if result["found"]:
            _execute_flow(node.id, "match", ctx)
        else:
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
        rect = params.get("rect", [0, 0, 100, 30])
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        region = resolve_region(mode, rect, hwnd)
        img = capture_screen(region)

        engine = ctx._ocr_engine
        if engine is None:
            engine = OCREngine()
            ctx._ocr_engine = engine
        match_number = None
        if params.get("match_mode", "contain").startswith("number_"):
            match_number = float(params.get("match_number", 0))

        result = engine.detect(
            img,
            match_text=params.get("match_text", ""),
            match_mode=params.get("match_mode", "contain"),
            match_number=match_number,
            cache_key=node.id,
            last_image=ctx.last_capture_cache.get(node.id),
            cache_strategy=params.get("cache_strategy", "time_interval"),
            cache_interval_ms=int(params.get("cache_interval_ms", 100)),
        )

        ctx.last_capture_cache[node.id] = img

        if params.get("store_var"):
            ctx.variables[params["store_var"]] = result.get("text", "")
        elif not params.get("match_text", "") and result.get("text", ""):
            ctx.variables[node.id + "_ocr_text"] = result.get("text", "")
        if params.get("store_number") and result.get("number") is not None:
            ctx.variables[params["store_number"]] = result["number"]
        elif not params.get("match_text", "") and result.get("number") is not None:
            ctx.variables[node.id + "_ocr_number"] = result["number"]

        ctx.check_results[f"{node.id}.result"] = result["found"]
        ctx.check_results[f"{node.id}.text"] = result.get("text", "")
        ocr_number = result.get("number")
        ctx.check_results[f"{node.id}.number"] = ocr_number if ocr_number is not None else 0

        if result["found"]:
            _execute_flow(node.id, "match", ctx)
        else:
            _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] OCR检测出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        ctx.check_results[f"{node.id}.text"] = ""
        ctx.check_results[f"{node.id}.number"] = 0
        _execute_flow(node.id, "no", ctx)


def _handle_check_image(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        import cv2
        import numpy as np
        from automation.detection.capture import capture_screen
        from engine.coordinate import resolve_region

        mode = params.get("mode", "screen")
        rect = params.get("rect", [0, 0, 0, 0])
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        template_path = params.get("template_path", "")

        if not template_path:
            ctx.check_results[f"{node.id}.result"] = False
            _execute_flow(node.id, "no", ctx)
            return

        if rect == [0, 0, 0, 0]:
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
            region = (0, 0, sw, sh)
        else:
            region = resolve_region(mode, rect, hwnd)

        img = capture_screen(region)
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            print(f"[新引擎] 模板图片未找到: {template_path}")
            ctx.check_results[f"{node.id}.result"] = False
            _execute_flow(node.id, "no", ctx)
            return

        method_map = {
            "tm_ccoeff_normed": cv2.TM_CCOEFF_NORMED,
            "tm_ccorr_normed": cv2.TM_CCORR_NORMED,
            "tm_sqdiff_normed": cv2.TM_SQDIFF_NORMED,
        }
        method = method_map.get(params.get("method", "tm_ccoeff_normed"), cv2.TM_CCOEFF_NORMED)
        threshold = float(params.get("threshold", 0.8))
        multi_match = params.get("multi_match", False)

        result = cv2.matchTemplate(img, template, method)
        match_x_val = 0
        match_y_val = 0
        if multi_match:
            locs = np.where(result >= threshold)
            matches = list(zip(*locs[::-1]))
            found = len(matches) > 0
            if found:
                match_x_val = int(matches[0][0] + template.shape[1] / 2)
                match_y_val = int(matches[0][1] + template.shape[0] / 2)
                if params.get("store_var"):
                    ctx.variables[params["store_var"]] = [
                        {"x": int(x + template.shape[1] / 2), "y": int(y + template.shape[0] / 2)}
                        for y, x in matches[:10]
                    ]
        else:
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            if method == cv2.TM_SQDIFF_NORMED:
                found = min_val <= (1 - threshold)
                match_loc = min_loc
            else:
                found = max_val >= threshold
                match_loc = max_loc
            if found:
                match_x_val = int(match_loc[0] + template.shape[1] / 2)
                match_y_val = int(match_loc[1] + template.shape[0] / 2)
                if params.get("store_var"):
                    ctx.variables[params["store_var"]] = {
                        "x": match_x_val,
                        "y": match_y_val,
                        "confidence": float(max_val),
                    }

        ctx.check_results[f"{node.id}.result"] = found
        ctx.check_results[f"{node.id}.match_x"] = match_x_val
        ctx.check_results[f"{node.id}.match_y"] = match_y_val
        if found:
            _execute_flow(node.id, "match", ctx)
        else:
            _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] 图像匹配出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        ctx.check_results[f"{node.id}.match_x"] = 0
        ctx.check_results[f"{node.id}.match_y"] = 0
        _execute_flow(node.id, "no", ctx)


def _handle_check_screen(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        import cv2
        import numpy as np
        from automation.detection.capture import capture_screen
        from engine.coordinate import resolve_region

        state = params.get("state", "black")
        threshold = int(params.get("threshold", 30))
        region_param = params.get("region", [0, 0, 0, 0])

        if region_param == [0, 0, 0, 0]:
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
            region = (0, 0, sw, sh)
        else:
            region = resolve_region("screen", region_param, None)

        img = capture_screen(region)
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
            last_img = ctx.last_capture_cache.get(node.id)
            ctx.last_capture_cache[node.id] = img
            if last_img is not None:
                diff = float(np.mean(np.abs(img.astype(float) - last_img.astype(float))))
                found = diff < threshold
            else:
                found = False
        else:
            found = False

        ctx.check_results[f"{node.id}.result"] = found
        if found:
            _execute_flow(node.id, "match", ctx)
        else:
            _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] 屏幕状态检测出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        _execute_flow(node.id, "no", ctx)


def register(handlers: dict):
    handlers["_handle_check_color"] = _handle_check_color
    handlers["_handle_check_ocr"] = _handle_check_ocr
    handlers["_handle_check_image"] = _handle_check_image
    handlers["_handle_check_screen"] = _handle_check_screen
