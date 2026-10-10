import time
import threading

from automation.engine import (
    _get_hwnd, _execute_flow,
)
from automation.compiler import ExecNode
from automation.engine import ExecContext

from engine.precision import precise_sleep_v5 as precise_sleep


def _monitor_check_color(node, ctx):
    try:
        from automation.detection.capture import capture_screen
        from automation.detection.color import check_color
        from engine.coordinate import resolve_region

        params = node.params
        mode = params.get("mode", "screen")
        rect = params.get("rect", [0, 0, 10, 10])
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        region = resolve_region(mode, rect, hwnd)
        img = capture_screen(region)

        target_hex = params.get("target_color", "#FF0000")
        r = int(target_hex[1:3], 16)
        g = int(target_hex[3:5], 16)
        b = int(target_hex[5:7], 16)
        result = check_color(img, (b, g, r), int(params.get("tolerance", 10)),
                             params.get("check_mode", "contain"), params.get("sample_mode", "center"),
                             last_image=ctx.last_capture_cache.get(node.id),
                             change_threshold=float(params.get("change_threshold", 10)))
        ctx.safe_set_cache(node.id, img)
        return result["found"]
    except Exception:
        return False


def _monitor_check_ocr(node, ctx):
    try:
        from automation.detection.capture import capture_screen
        from automation.detection.ocr import OCREngine
        from engine.coordinate import resolve_region

        params = node.params
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
        result = engine.detect(img, match_text=params.get("match_text", ""),
                               match_mode=params.get("match_mode", "contain"),
                               match_number=match_number)
        if params.get("store_var"):
            ctx.safe_set_variable(params["store_var"], result.get("text", ""))
        elif not params.get("match_text", "") and result.get("text", ""):
            ctx.safe_set_variable(node.id + "_ocr_text", result.get("text", ""))
        if params.get("store_number") and result.get("number") is not None:
            ctx.safe_set_variable(params["store_number"], result["number"])
        elif not params.get("match_text", "") and result.get("number") is not None:
            ctx.safe_set_variable(node.id + "_ocr_number", result["number"])
        return result["found"]
    except Exception:
        return False


def _apply_on_trigger(on_trigger, target_task, ctx):
    if on_trigger == "stop_all":
        ctx.stop_event.set()
        ctx.task_pool.stop_all()
    elif on_trigger == "stop_task":
        if target_task:
            ctx.task_pool.stop(target_task)
    elif on_trigger == "pause_task":
        if target_task:
            ctx.task_pool.pause(target_task)


def _handle_monitor_node(node: ExecNode, ctx: ExecContext):
    trigger_event = threading.Event()
    interval = float(node.params.get("interval", 100)) / 1000.0
    timeout_ms = float(node.params.get("timeout", 0))
    trigger_mode = node.params.get("trigger_mode", "appear")
    on_trigger = node.params.get("on_trigger", "branch")
    target_task = node.params.get("target_task", "")
    repeat_count = int(node.params.get("repeat_count", 0))
    node_type = node.type
    prev_found = None
    triggered_count = 0
    _timed_out = [False]

    def poll_loop():
        nonlocal prev_found, triggered_count
        last_check = 0.0
        start_time = time.perf_counter()
        while not trigger_event.is_set() and not ctx.stop_event.is_set():
            now = time.perf_counter()
            if now - last_check < interval:
                time.sleep(0.001)
                continue
            last_check = now

            try:
                found = False
                if "monitor_color" in node_type:
                    found = _monitor_check_color(node, ctx)
                elif "monitor_ocr" in node_type:
                    found = _monitor_check_ocr(node, ctx)
                elif "monitor_timer" in node_type:
                    found = True

                should_trigger = False
                if trigger_mode == "appear":
                    should_trigger = found
                elif trigger_mode == "disappear":
                    if prev_found is not None:
                        should_trigger = prev_found and not found
                elif trigger_mode == "change":
                    if prev_found is not None:
                        should_trigger = prev_found != found
                prev_found = found

                if should_trigger:
                    triggered_count += 1
                    if repeat_count > 0 and triggered_count >= repeat_count:
                        trigger_event.set()
                        break
                    if on_trigger != "branch":
                        _apply_on_trigger(on_trigger, target_task, ctx)
                        trigger_event.set()
                        break
                    trigger_event.set()
                    break
            except Exception as e:
                print(f"[监视器] 检测出错: {e}")

            if timeout_ms > 0 and (time.perf_counter() - start_time) * 1000 > timeout_ms:
                _timed_out[0] = True
                trigger_event.set()
                break

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()

    while not trigger_event.is_set() and not ctx.stop_event.is_set():
        trigger_event.wait(timeout=0.005)

    if not ctx.stop_event.is_set():
        if _timed_out[0]:
            _execute_flow(node.id, "timeout", ctx)
        else:
            _execute_flow(node.id, "trigger", ctx)


def register(handlers: dict):
    handlers["_handle_monitor_node"] = _handle_monitor_node
