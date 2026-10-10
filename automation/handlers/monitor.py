import time
import threading
import datetime

from automation.engine import (
    _get_hwnd, _execute_flow, _resolve_value,
)
from automation.compiler import ExecNode
from automation.engine import ExecContext
from automation.handlers.variable import _extract_var_name
from automation.handlers.detection import _parse_target_color, _invalidate_frame

from engine.precision import precise_sleep_v5 as precise_sleep, set_thread_affinity, clear_thread_affinity


def _monitor_check_color(node, ctx):
    try:
        from automation.detection.capture import capture_screen
        from automation.detection.color import check_color
        from engine.coordinate import resolve_region

        params = node.params
        mode = params.get("mode", "screen")
        rect = _resolve_value(params.get("rect", [0, 0, 10, 10]), ctx)
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        region = resolve_region(mode, rect, hwnd)
        img = capture_screen(region, ctx=ctx)

        target_hex = _resolve_value(params.get("target_color", "#FF0000"), ctx)
        parsed_color = _parse_target_color(target_hex)
        if parsed_color is None:
            return False, True
        _sample_mode_compat = {"average": "mean", "corner": "center"}
        sample_mode = _sample_mode_compat.get(params.get("sample_mode", "center"), params.get("sample_mode", "center"))
        result = check_color(img, parsed_color, int(_resolve_value(params.get("tolerance", 10), ctx)),
                             params.get("check_mode", "contain"), sample_mode,
                             last_image=ctx.safe_get_cache(node.id),
                             change_threshold=float(_resolve_value(params.get("change_threshold", 10), ctx)),
                             area_ratio_threshold=float(_resolve_value(params.get("area_ratio_threshold", 0.5), ctx)))
        ctx.safe_set_cache(node.id, img)
        return result["found"], False
    except Exception as e:
        ctx.log_error(f"颜色监视检测出错: {e}", node_id=node.id, error_type="detection")
        return False, True


def _monitor_check_ocr(node, ctx):
    try:
        from automation.detection.capture import capture_screen
        from automation.detection.ocr import OCREngine
        from engine.coordinate import resolve_region

        params = node.params
        mode = params.get("mode", "screen")
        rect = _resolve_value(params.get("rect", [0, 0, 100, 30]), ctx)
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        region = resolve_region(mode, rect, hwnd)
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
        return result["found"], False
    except Exception as e:
        ctx.log_error(f"OCR监视检测出错: {e}", node_id=node.id, error_type="detection")
        return False, True


def _apply_on_trigger(on_trigger, target_task, ctx):
    if on_trigger == "stop_all":
        ctx.stop_event.set()
        ctx.task_pool.stop_all()
    elif on_trigger in ("stop_task", "pause_task", "resume_task"):
        if target_task:
            try:
                task_id = int(target_task)
            except (ValueError, TypeError):
                task_id = None
            if task_id is not None:
                sub_ctx = ctx._sub_script_contexts.get(task_id)
                if sub_ctx:
                    if on_trigger == "stop_task":
                        sub_ctx.stop_event.set()
                    elif on_trigger == "pause_task":
                        sub_ctx._pause_reasons.add("monitor")
                        sub_ctx.pause_event.set()
                    elif on_trigger == "resume_task":
                        sub_ctx._pause_reasons.discard("monitor")
                        if not sub_ctx._pause_reasons:
                            sub_ctx.pause_event.clear()
            if on_trigger == "stop_task":
                ctx.task_pool.stop(target_task)
            elif on_trigger == "pause_task":
                ctx.task_pool.pause(target_task)
            elif on_trigger == "resume_task":
                ctx.task_pool.resume(target_task)


def _handle_monitor_node(node: ExecNode, ctx: ExecContext):
    params = node.params
    trigger_event = threading.Event()
    trigger_signal = threading.Event()
    flow_done = threading.Event()
    interval = float(_resolve_value(params.get("interval", 100), ctx)) / 1000.0
    timeout_ms = float(_resolve_value(params.get("timeout", 0), ctx))
    trigger_mode = params.get("trigger_mode", "appear")
    on_trigger = params.get("on_trigger", "branch")
    target_task = _resolve_value(params.get("target_task", ""), ctx)
    auto_stop = params.get("auto_stop", True)
    recheck_delay_ms = float(_resolve_value(params.get("recheck_delay_ms", 500), ctx))
    max_triggers = int(_resolve_value(params.get("max_triggers", 0), ctx))
    auto_close_after_ms = float(_resolve_value(params.get("auto_close_after_ms", 0), ctx))
    node_type = node.type
    prev_found = None
    triggered_count = 0
    _timed_out = [False]
    _pending_trigger = [False]

    branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
    branch_stop = branch_ctx.stop_event if branch_ctx else None

    def poll_loop():
        nonlocal prev_found, triggered_count
        last_check = 0.0
        start_time = time.perf_counter()
        while not trigger_event.is_set() and not ctx.stop_event.is_set():
            if branch_stop and branch_stop.is_set():
                break
            # 暂停期间不再截图/识别。
            # 设计文档曾把"监视器不响应暂停"记为有意设计，但本项目的使用场景要求
            # 尽量少占游戏 CPU：暂停时仍以 interval 频率跑 OCR（单次约 190ms）
            # 会白白吃掉一个核心。检测类节点都传了 pause_event，这里对齐。
            if ctx.pause_event.is_set() or (branch_ctx is not None and branch_ctx.pause_event.is_set()):
                ctx.stop_event.wait(timeout=0.05)
                continue
            now = time.perf_counter()
            if now - last_check < interval:
                ctx.stop_event.wait(timeout=0.001)
                continue
            last_check = now
            # 监视器是"实时盯屏"的：每次实际检测都强制取新帧，
            # 避免共享帧缓存在高频 interval 下连续命中同一帧而漏掉瞬时状态变化。
            _invalidate_frame(ctx)

            try:
                found = False
                is_error = False
                if "monitor_color" in node_type:
                    found, is_error = _monitor_check_color(node, ctx)
                elif "monitor_ocr" in node_type:
                    found, is_error = _monitor_check_ocr(node, ctx)
                elif "monitor_timer" in node_type:
                    found = True

                if is_error:
                    prev_found = None
                else:
                    should_trigger = False
                    initial_check = params.get("initial_check", "baseline")
                    if trigger_mode == "appear":
                        should_trigger = found
                    elif trigger_mode == "absent":
                        should_trigger = not found
                    elif trigger_mode == "disappear":
                        if prev_found is not None:
                            should_trigger = prev_found and not found
                        elif initial_check == "trigger":
                            should_trigger = not found
                            prev_found = True
                    elif trigger_mode == "change":
                        if prev_found is not None:
                            should_trigger = prev_found != found
                        elif initial_check == "trigger":
                            should_trigger = found
                            prev_found = not found
                    if not should_trigger:
                        prev_found = found

                    if should_trigger:
                        triggered_count += 1
                        _pending_trigger[0] = True
                        if max_triggers > 0 and triggered_count >= max_triggers:
                            trigger_event.set()
                            break
                        if auto_stop:
                            trigger_event.set()
                            break
                        trigger_signal.set()
                        while not flow_done.wait(timeout=0.1):
                            if trigger_event.is_set() or ctx.stop_event.is_set():
                                break
                        flow_done.clear()
                        _pending_trigger[0] = False
                        if recheck_delay_ms > 0:
                            precise_sleep(recheck_delay_ms / 1000.0, ctx.stop_event)
            except Exception as e:
                print(f"[监视器] 检测出错: {e}")

            if timeout_ms > 0 and (time.perf_counter() - start_time) * 1000 > timeout_ms:
                _timed_out[0] = True
                trigger_event.set()
                break

            if auto_close_after_ms > 0 and (time.perf_counter() - start_time) * 1000 > auto_close_after_ms:
                trigger_event.set()
                break

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()

    while not ctx.stop_event.is_set() and not (branch_stop and branch_stop.is_set()):
        if auto_stop:
            trigger_event.wait(timeout=0.005)
            if trigger_event.is_set():
                break
        else:
            trigger_signal.wait(timeout=0.005)
            if trigger_signal.is_set():
                trigger_signal.clear()
                if on_trigger != "branch":
                    _apply_on_trigger(on_trigger, target_task, ctx)
                _execute_flow(node.id, "trigger", ctx)
                flow_done.set()
                if trigger_event.is_set():
                    break
                continue
            if trigger_event.is_set():
                break

    if not ctx.stop_event.is_set() and not (branch_stop and branch_stop.is_set()):
        if _timed_out[0]:
            _execute_flow(node.id, "timeout", ctx)
        elif _pending_trigger[0]:
            if on_trigger != "branch":
                _apply_on_trigger(on_trigger, target_task, ctx)
            _execute_flow(node.id, "trigger", ctx)


def _handle_monitor_time(node: ExecNode, ctx: ExecContext):
    params = node.params
    target_hour = int(_resolve_value(params.get("hour", 8), ctx))
    target_minute = int(_resolve_value(params.get("minute", 0), ctx))
    target_second = int(_resolve_value(params.get("second", 0), ctx))
    next_day = params.get("next_day", False)
    check_interval = float(_resolve_value(params.get("check_interval", 500), ctx)) / 1000.0
    timeout_ms = float(_resolve_value(params.get("timeout", 0), ctx))
    on_trigger = params.get("on_trigger", "branch")
    target_task = _resolve_value(params.get("target_task", ""), ctx)
    auto_stop = params.get("auto_stop", True)
    recheck_delay_ms = float(_resolve_value(params.get("recheck_delay_ms", 500), ctx))
    max_triggers = int(_resolve_value(params.get("max_triggers", 0), ctx))
    auto_close_after_ms = float(_resolve_value(params.get("auto_close_after_ms", 0), ctx))
    _timed_out = [False]
    _trigger_count = [0]

    branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
    branch_stop = branch_ctx.stop_event if branch_ctx else None

    now = datetime.datetime.now()
    target = now.replace(hour=target_hour, minute=target_minute, second=target_second, microsecond=0)

    if target <= now:
        if next_day:
            target += datetime.timedelta(days=1)
        else:
            _trigger_count[0] += 1
            if on_trigger != "branch":
                _apply_on_trigger(on_trigger, target_task, ctx)
            _execute_flow(node.id, "trigger", ctx)

            if auto_stop or (max_triggers > 0 and _trigger_count[0] >= max_triggers):
                return

            if not auto_stop and not ctx.stop_event.is_set():
                now2 = datetime.datetime.now()
                next_target = now2.replace(hour=target_hour, minute=target_minute, second=target_second, microsecond=0)
                if next_target <= now2:
                    next_target += datetime.timedelta(days=1)
                target = next_target

    trigger_event = threading.Event()
    start_time = time.perf_counter()

    def wait_loop():
        while not trigger_event.is_set() and not ctx.stop_event.is_set():
            if branch_stop and branch_stop.is_set():
                break
            now = datetime.datetime.now()
            if now >= target:
                trigger_event.set()
                return
            if timeout_ms > 0 and (time.perf_counter() - start_time) * 1000 > timeout_ms:
                _timed_out[0] = True
                trigger_event.set()
                return
            remaining = (target - now).total_seconds()
            sleep_time = min(check_interval, remaining)
            if sleep_time > 0:
                ctx.stop_event.wait(timeout=sleep_time)

    wait_thread = threading.Thread(target=wait_loop, daemon=True)
    wait_thread.start()

    while not trigger_event.is_set() and not ctx.stop_event.is_set():
        if branch_stop and branch_stop.is_set():
            break
        trigger_event.wait(timeout=0.005)

    if not ctx.stop_event.is_set() and not (branch_stop and branch_stop.is_set()):
        if _timed_out[0]:
            _execute_flow(node.id, "timeout", ctx)
        else:
            _trigger_count[0] += 1
            if on_trigger != "branch":
                _apply_on_trigger(on_trigger, target_task, ctx)
            if not ctx.stop_event.is_set():
                _execute_flow(node.id, "trigger", ctx)

            if auto_stop or (max_triggers > 0 and _trigger_count[0] >= max_triggers):
                return

            if not auto_stop and not ctx.stop_event.is_set():
                loop_start = time.perf_counter()
                while not ctx.stop_event.is_set() and not (branch_stop and branch_stop.is_set()):
                    if recheck_delay_ms > 0:
                        ctx.stop_event.wait(timeout=recheck_delay_ms / 1000.0)
                    if ctx.stop_event.is_set() or (branch_stop and branch_stop.is_set()):
                        break
                    now = datetime.datetime.now()
                    next_target = now.replace(hour=target_hour, minute=target_minute, second=target_second, microsecond=0)
                    if next_target <= now:
                        next_target += datetime.timedelta(days=1)
                    target = next_target
                    trigger_event.clear()
                    _timed_out[0] = False

                    wait_thread = threading.Thread(target=wait_loop, daemon=True)
                    wait_thread.start()

                    while not trigger_event.is_set() and not ctx.stop_event.is_set():
                        if branch_stop and branch_stop.is_set():
                            break
                        trigger_event.wait(timeout=0.005)

                    if ctx.stop_event.is_set() or (branch_stop and branch_stop.is_set()):
                        break

                    if _timed_out[0]:
                        _execute_flow(node.id, "timeout", ctx)
                        break

                    _trigger_count[0] += 1
                    if max_triggers > 0 and _trigger_count[0] >= max_triggers:
                        if on_trigger != "branch":
                            _apply_on_trigger(on_trigger, target_task, ctx)
                        if not ctx.stop_event.is_set():
                            _execute_flow(node.id, "trigger", ctx)
                        break

                    if auto_close_after_ms > 0 and (time.perf_counter() - loop_start) * 1000 > auto_close_after_ms:
                        break

                    if on_trigger != "branch":
                        _apply_on_trigger(on_trigger, target_task, ctx)
                    if not ctx.stop_event.is_set():
                        _execute_flow(node.id, "trigger", ctx)


def register(handlers: dict):
    handlers["_handle_monitor_node"] = _handle_monitor_node
    handlers["_handle_monitor_time"] = _handle_monitor_time
