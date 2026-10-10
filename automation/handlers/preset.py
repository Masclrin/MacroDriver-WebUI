from automation.engine import (
    _resolve_value, _get_hwnd, _execute_flow, _do_click, _interpolated_move,
)
from automation.compiler import ExecNode
from automation.engine import ExecContext

from engine.input_sendinput import set_cursor_pos


def _handle_preset_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    x = _resolve_value(params.get("x", 0), ctx)
    y = _resolve_value(params.get("y", 0), ctx)
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

    from engine.coordinate import resolve_coords
    phys_x, phys_y = resolve_coords(mode, float(x), float(y), hwnd)

    move_dur = float(params.get("move_duration", 150))
    if move_dur > 0:
        _interpolated_move(phys_x, phys_y, move_dur, ctx.stop_event)
    else:
        set_cursor_pos(phys_x, phys_y)

    button = params.get("button", "left")
    _do_click(button, "click", 0, ctx.stop_event, ctx)
    _execute_flow(node.id, "next", ctx)


def _handle_preset_find_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        import cv2
        import numpy as np
        from automation.detection.capture import capture_screen
        from engine.coordinate import resolve_region, resolve_coords

        mode = params.get("mode", "screen")
        rect = params.get("rect", [0, 0, 0, 0])
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        template_path = params.get("template_path", "")

        if not template_path:
            _execute_flow(node.id, "not_found", ctx)
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
            _execute_flow(node.id, "not_found", ctx)
            return

        result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        threshold = float(params.get("threshold", 0.8))

        if max_val >= threshold:
            click_x = int(max_loc[0] + template.shape[1] / 2)
            click_y = int(max_loc[1] + template.shape[0] / 2)
            phys_x = region[0] + click_x
            phys_y = region[1] + click_y
            set_cursor_pos(phys_x, phys_y)
            button = params.get("button", "left")
            _do_click(button, "click", 0, ctx.stop_event, ctx)
            _execute_flow(node.id, "found", ctx)
        else:
            _execute_flow(node.id, "not_found", ctx)
    except Exception as e:
        print(f"[新引擎] 找图点击出错: {e}")
        _execute_flow(node.id, "not_found", ctx)


def _handle_preset_read_text(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        import re
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
        result = engine.detect(img)
        full_text = result.get("text", "")

        read_mode = params.get("read_mode", "all")
        if read_mode == "number":
            nums = re.findall(r'[\d.]+', full_text)
            value = nums[0] if nums else ""
        elif read_mode == "text":
            value = re.sub(r'[\d.]+', '', full_text).strip()
        else:
            value = full_text

        store_var = params.get("store_var", "")
        if store_var:
            ctx.variables[store_var] = value

        _execute_flow(node.id, "next", ctx)
    except Exception as e:
        print(f"[新引擎] 读取数字文本出错: {e}")
        _execute_flow(node.id, "next", ctx)


def register(handlers: dict):
    handlers["_handle_preset_click"] = _handle_preset_click
    handlers["_handle_preset_find_click"] = _handle_preset_find_click
    handlers["_handle_preset_read_text"] = _handle_preset_read_text
