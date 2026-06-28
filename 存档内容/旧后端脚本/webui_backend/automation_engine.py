# -*- coding: utf-8 -*-
"""
新自动化调度引擎 — 大脑层
负责流程控制、感知调度、变量管理、并发任务池。
路径1：新引擎直发（SendInput/SetCursorPos，无补偿器）
路径2：旧引擎托管（调用 execute_macro_once）
"""
import os
import re
import time
import threading

from engine.precision import precise_sleep_v5 as precise_sleep
from webui_backend.input_primitives import (
    get_vk, set_cursor_pos, send_click_sendinput,
    send_key_sendinput, send_scroll_sendinput, release_all_modifiers,
    send_unicode_char, InterceptionSession,
)
from webui_backend.automation_compiler import ExecGraph, ExecNode
from webui_backend.plugin_registry import PluginRegistry


_old_engine_module = None
_old_engine_lock = threading.Lock()


def _get_old_engine():
    global _old_engine_module
    if _old_engine_module is not None:
        return _old_engine_module
    with _old_engine_lock:
        if _old_engine_module is not None:
            return _old_engine_module
        import sys
        for name in ("宏执行框架3_2", "macro_executor_v23"):
            if name in sys.modules:
                _old_engine_module = sys.modules[name]
                return _old_engine_module
        raise ImportError("旧引擎模块尚未加载，请先初始化 MacroBridge")

PROFILE_PRESETS = {
    "lite": {"interception_kb": False, "interception_mouse": False, "boost_priority": False, "affinity": False},
    "standard": {"interception_kb": False, "interception_mouse": False, "boost_priority": True, "affinity": False},
    "precision": {"interception_kb": True, "interception_mouse": True, "boost_priority": True, "affinity": True},
}


class ExecContext:
    def __init__(self, graph: ExecGraph, stop_event: threading.Event):
        self.graph = graph
        self.stop_event = stop_event
        self.pause_event = threading.Event()
        self.variables: dict = {}
        self.check_results: dict = {}
        self.task_pool = TaskPool()
        self.monitors: list = []
        self.pending_branches: list = []
        self.last_capture_cache: dict = {}
        self.hwnd_cache: dict = {}
        self.interception_session: InterceptionSession = None
        self._profile = PROFILE_PRESETS.get("standard", PROFILE_PRESETS["lite"])
        self._goto_target = None
        self._ocr_engine = None

        for var_name, var_def in graph.variables.items():
            self.variables[var_name] = var_def.get("init")


class AsyncTask:
    def __init__(self, task_id, thread, stop_event, pause_event, node_id, macro_name):
        self.task_id = task_id
        self.thread = thread
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.node_id = node_id
        self.macro_name = macro_name
        self.status = "running"
        self.start_time = time.perf_counter()


class TaskPool:
    def __init__(self):
        self.tasks: dict = {}
        self._lock = threading.Lock()
        self._seed = 0

    def start(self, node_id, compiled, macro_name, options, stop_event_parent, on_complete=None) -> str:
        with self._lock:
            self._seed += 1
            task_id = f"task_{self._seed}"

        stop_event = threading.Event()
        pause_event = threading.Event()

        def worker():
            _oe = _get_old_engine()
            try:
                _oe.execute_macro_once(compiled, stop_event, pause_event,
                                   macro_name=macro_name, options=options)
                with self._lock:
                    if task_id in self.tasks:
                        self.tasks[task_id].status = "completed"
                if on_complete:
                    on_complete(task_id, "completed")
            except Exception as e:
                print(f"[TaskPool] 异步任务 {task_id} 执行出错: {e}")
                with self._lock:
                    if task_id in self.tasks:
                        self.tasks[task_id].status = "error"
                if on_complete:
                    on_complete(task_id, "error")

        def _propagate_stop():
            while not stop_event_parent.is_set():
                if stop_event.wait(timeout=0.05):
                    break
            stop_event.set()

        t = threading.Thread(target=worker, daemon=True)
        propagate_t = threading.Thread(target=_propagate_stop, daemon=True)
        task = AsyncTask(task_id, t, stop_event, pause_event, node_id, macro_name)
        with self._lock:
            self.tasks[task_id] = task
        propagate_t.start()
        t.start()
        return task_id

    def stop(self, task_id) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
        if task and task.status == "running":
            task.stop_event.set()
            task.status = "interrupted"
            return True
        return False

    def stop_all(self):
        with self._lock:
            task_ids = list(self.tasks.keys())
        for tid in task_ids:
            self.stop(tid)

    def pause(self, task_id) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
        if task and task.status == "running":
            task.pause_event.set()
            return True
        return False

    def resume(self, task_id) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
        if task and task.status == "running":
            task.pause_event.clear()
            return True
        return False

    def get_status(self, task_id) -> str:
        with self._lock:
            task = self.tasks.get(task_id)
        return task.status if task else "unknown"

    def get_completed_or_interrupted(self):
        result = []
        with self._lock:
            for tid, task in self.tasks.items():
                if task.status in ("completed", "interrupted"):
                    result.append(task)
        return result


def _resolve_value(value, ctx: ExecContext):
    if not isinstance(value, str):
        return value
    pattern = re.compile(r'\$\{([^}]+)\}')
    matches = pattern.findall(value)
    if not matches:
        return value
    result = value
    for var_name in matches:
        if var_name in ctx.variables:
            result = result.replace(f"${{{var_name}}}", str(ctx.variables[var_name]))
        else:
            print(f"[新引擎] 警告：变量 '{var_name}' 未定义")
            result = result.replace(f"${{{var_name}}}", "0")
    try:
        if '.' in result or result.replace('-', '').replace('.', '').isdigit():
            return float(result)
    except (ValueError, TypeError):
        pass
    return result


def _get_hwnd(hwnd_var, ctx: ExecContext):
    if not hwnd_var:
        return None
    if hwnd_var in ctx.hwnd_cache:
        return ctx.hwnd_cache[hwnd_var]
    try:
        hwnd = int(hwnd_var)
        ctx.hwnd_cache[hwnd_var] = hwnd
        return hwnd
    except (ValueError, TypeError):
        pass
    var_val = ctx.variables.get(hwnd_var)
    if var_val is not None:
        try:
            hwnd = int(var_val)
            ctx.hwnd_cache[hwnd_var] = hwnd
            return hwnd
        except (ValueError, TypeError):
            pass
    return None


def _execute_flow(node_id: str, port_name: str, ctx: ExecContext):
    if ctx.stop_event.is_set():
        return
    node = ctx.graph.nodes.get(node_id)
    if node is None:
        return
    children = node.get_flow_children(port_name)
    for child_id in children:
        _execute_node(child_id, ctx)
        if ctx.stop_event.is_set():
            return


def _execute_node(node_id: str, ctx: ExecContext):
    current_id = node_id
    max_goto_iterations = 100000

    for _ in range(max_goto_iterations):
        if ctx.stop_event.is_set():
            return

        while ctx.pause_event.is_set() and not ctx.stop_event.is_set():
            time.sleep(0.05)

        if ctx.stop_event.is_set():
            return

        node = ctx.graph.nodes.get(current_id)
        if node is None:
            print(f"[新引擎] 节点不存在: {current_id}")
            return

        handler_name = PluginRegistry.get_node(node.type)
        if handler_name is None:
            print(f"[新引擎] 未知节点类型: {node.type}")
            return

        handler_method_name = handler_name.get("handler")
        handler = NODE_HANDLERS.get(handler_method_name)
        if handler is None:
            print(f"[新引擎] 未注册处理器: {handler_method_name}")
            return

        ctx._goto_target = None
        handler(node, ctx)

        if ctx._goto_target:
            current_id = ctx._goto_target
            ctx._goto_target = None
            continue

        return

    print("[新引擎] 警告: goto 循环超过最大迭代次数")


def _send_key(vk, up, ctx: ExecContext):
    if ctx.interception_session:
        ctx.interception_session.send_key(vk, up)
    else:
        send_key_sendinput(vk, up)


def _send_click(left, up, ctx: ExecContext):
    if ctx.interception_session:
        ctx.interception_session.send_click(left=left, up=up)
    else:
        send_click_sendinput(left=left, up=up)


def _do_click(button, click_type, hold_time, stop_event, ctx: ExecContext = None):
    if button == "middle":
        left = None
    else:
        left = (button == "left")
    if click_type == "press":
        _send_click(left, False, ctx) if ctx else send_click_sendinput(left=left, up=False)
        return
    if click_type == "release":
        _send_click(left, True, ctx) if ctx else send_click_sendinput(left=left, up=True)
        return
    if click_type == "long_press":
        _send_click(left, False, ctx) if ctx else send_click_sendinput(left=left, up=False)
        if hold_time > 0:
            precise_sleep(hold_time / 1000.0, stop_event)
        _send_click(left, True, ctx) if ctx else send_click_sendinput(left=left, up=True)
        return
    if click_type == "dblclick":
        for _ in range(2):
            _send_click(left, False, ctx) if ctx else send_click_sendinput(left=left, up=False)
            precise_sleep(0.01, stop_event)
            _send_click(left, True, ctx) if ctx else send_click_sendinput(left=left, up=True)
            precise_sleep(0.01, stop_event)
        return
    _send_click(left, False, ctx) if ctx else send_click_sendinput(left=left, up=False)
    precise_sleep(0.01, stop_event)
    _send_click(left, True, ctx) if ctx else send_click_sendinput(left=left, up=True)


def _interpolated_move(phys_x, phys_y, duration_ms, stop_event):
    steps = max(1, min(int(duration_ms / 10), 100))
    step_delay = duration_ms / 1000.0 / steps
    cx, cy = _get_cursor_pos()
    for i in range(1, steps + 1):
        if stop_event.is_set():
            return
        t = i / steps
        x = int(cx + (phys_x - cx) * t)
        y = int(cy + (phys_y - cy) * t)
        set_cursor_pos(x, y)
        if i < steps:
            precise_sleep(step_delay, stop_event)


def _get_cursor_pos():
    import ctypes
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _handle_mouse_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    x = _resolve_value(params.get("x", 0), ctx)
    y = _resolve_value(params.get("y", 0), ctx)
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

    from webui_backend.coordinate_resolver import resolve_coords
    phys_x, phys_y = resolve_coords(mode, float(x), float(y), hwnd)

    move_dur = float(params.get("move_duration", 0))
    if move_dur > 0:
        _interpolated_move(phys_x, phys_y, move_dur, ctx.stop_event)
    else:
        set_cursor_pos(phys_x, phys_y)

    before_delay = float(params.get("before_delay", 0))
    if before_delay > 0:
        precise_sleep(before_delay / 1000.0, ctx.stop_event)

    button = params.get("button", "left")
    click_type = params.get("click_type", "click")
    hold_time = float(params.get("hold_time", 0))
    _do_click(button, click_type, hold_time, ctx.stop_event, ctx)

    after_delay = float(params.get("after_delay", 0))
    if after_delay > 0:
        precise_sleep(after_delay / 1000.0, ctx.stop_event)

    _execute_flow(node.id, "next", ctx)


def _handle_key_action(node: ExecNode, ctx: ExecContext):
    params = node.params
    key = params.get("key", "")
    action = params.get("action", "press")
    vk = get_vk(key)
    delay = float(params.get("delay", 0))

    if action == "press":
        _send_key(vk, False, ctx)
    elif action == "release":
        _send_key(vk, True, ctx)
    elif action == "type":
        _send_key(vk, False, ctx)
        precise_sleep(0.01, ctx.stop_event)
        _send_key(vk, True, ctx)

    if delay > 0:
        precise_sleep(delay / 1000.0, ctx.stop_event)

    _execute_flow(node.id, "next", ctx)


def _handle_mouse_scroll(node: ExecNode, ctx: ExecContext):
    params = node.params
    delta = int(params.get("delta", 120))
    delay = float(params.get("delay", 0))

    send_scroll_sendinput(delta)
    if delay > 0:
        precise_sleep(delay / 1000.0, ctx.stop_event)

    _execute_flow(node.id, "next", ctx)


def _handle_text_input(node: ExecNode, ctx: ExecContext):
    params = node.params
    text = str(_resolve_value(params.get("text", ""), ctx))
    interval = float(params.get("interval", 50))
    before_delay = float(params.get("before_delay", 0))

    if before_delay > 0:
        precise_sleep(before_delay / 1000.0, ctx.stop_event)

    for ch in text:
        if ctx.stop_event.is_set():
            break
        vk = get_vk(ch.lower())
        if vk:
            is_upper = ch.isupper()
            if is_upper:
                _send_key(get_vk("shift"), False, ctx)
            _send_key(vk, False, ctx)
            precise_sleep(0.005, ctx.stop_event)
            _send_key(vk, True, ctx)
            if is_upper:
                _send_key(get_vk("shift"), True, ctx)
        else:
            send_unicode_char(ch)
        if interval > 0:
            precise_sleep(interval / 1000.0, ctx.stop_event)

    _execute_flow(node.id, "next", ctx)


def _handle_wait(node: ExecNode, ctx: ExecContext):
    duration = float(_resolve_value(node.params.get("duration", 1000), ctx))
    precise_sleep(duration / 1000.0, ctx.stop_event)
    _execute_flow(node.id, "next", ctx)


def _handle_if_else(node: ExecNode, ctx: ExecContext):
    data_sources = node.get_data_inputs("cond")
    conditions = []
    for src in data_sources:
        key = f"{src['source_node_id']}.{src['source_port']}"
        conditions.append(ctx.check_results.get(key, False))

    logic = node.params.get("logic", "AND")

    if not conditions:
        result = node.params.get("fallback", "false") == "true"
    elif logic == "AND":
        result = all(conditions)
    elif logic == "OR":
        result = any(conditions)
    elif logic == "NOT":
        result = not conditions[0] if conditions else True
    else:
        result = False

    ctx.check_results[f"{node.id}.result"] = result

    if result:
        _execute_flow(node.id, "true", ctx)
    else:
        _execute_flow(node.id, "false", ctx)


def _handle_loop_count(node: ExecNode, ctx: ExecContext):
    count = int(_resolve_value(node.params.get("count", 1), ctx))
    counter_var = node.params.get("counter_var", "")

    for i in range(count):
        if ctx.stop_event.is_set():
            return
        if counter_var:
            ctx.variables[counter_var] = i
        _execute_flow(node.id, "body", ctx)

    _execute_flow(node.id, "next", ctx)


def _handle_loop_while(node: ExecNode, ctx: ExecContext):
    max_iter = int(node.params.get("max_iterations", 10000))
    check_at = node.params.get("check_at", "start")

    for i in range(max_iter):
        if ctx.stop_event.is_set():
            return

        if check_at == "start":
            data_sources = node.get_data_inputs("cond")
            conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                          for src in data_sources]
            if not conditions or not all(conditions):
                break

        _execute_flow(node.id, "body", ctx)

        if check_at == "end":
            data_sources = node.get_data_inputs("cond")
            conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                          for src in data_sources]
            if not conditions or not all(conditions):
                break

    _execute_flow(node.id, "next", ctx)


def _handle_call_script_sync(node: ExecNode, ctx: ExecContext):
    path = node.params.get("path", "")
    if not path or not os.path.exists(path):
        print(f"[新引擎] 宏文件不存在: {path}")
        _execute_flow(node.id, "next", ctx)
        return

    _oe = _get_old_engine()
    script = _oe.load_macro_from_file(path)
    compiled = _oe.compile_macro(script)
    compiled = _oe.batch_compiled_macro(compiled)

    opts = {
        "speed_factor": float(node.params.get("speed_factor", 1.0)),
        "timeline_mode": node.params.get("timeline_mode", "absolute"),
        "random_delay": node.params.get("random_delay", False),
        "auto_release_modifiers": False,
    }

    if len(compiled) <= 2:
        for func, delay, _, _, _ in compiled:
            if ctx.stop_event.is_set():
                break
            if func:
                try:
                    func()
                except Exception as e:
                    print(f"[新引擎] 同步闭包执行出错: {e}")
            if delay > 0:
                precise_sleep(delay, ctx.stop_event)
    else:
        _oe.execute_macro_once(compiled, ctx.stop_event, ctx.pause_event, macro_name=os.path.basename(path), options=opts)

    _execute_flow(node.id, "next", ctx)


def _handle_call_script_async(node: ExecNode, ctx: ExecContext):
    path = node.params.get("path", "")
    if not path or not os.path.exists(path):
        print(f"[新引擎] 宏文件不存在: {path}")
        _execute_flow(node.id, "next", ctx)
        return

    _oe = _get_old_engine()
    script = _oe.load_macro_from_file(path)
    compiled = _oe.compile_macro(script)
    compiled = _oe.batch_compiled_macro(compiled)

    opts = {
        "speed_factor": float(node.params.get("speed_factor", 1.0)),
        "timeline_mode": node.params.get("timeline_mode", "absolute"),
        "random_delay": node.params.get("random_delay", False),
        "auto_release_modifiers": False,
    }

    async_node_id = node.id

    def on_task_complete(task_id, status):
        if ctx.stop_event.is_set():
            return
        if status == "completed":
            _execute_flow(async_node_id, "completed", ctx)
        else:
            _execute_flow(async_node_id, "interrupted", ctx)

    task_id = ctx.task_pool.start(
        node_id=node.id,
        compiled=compiled,
        macro_name=os.path.basename(path),
        options=opts,
        stop_event_parent=ctx.stop_event,
        on_complete=on_task_complete,
    )

    _execute_flow(node.id, "next", ctx)


def _handle_check_color(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from webui_backend.detection.capture import capture_screen
        from webui_backend.detection.color import check_color
        from webui_backend.coordinate_resolver import resolve_region

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

        if result["found"]:
            _execute_flow(node.id, "match", ctx)
        else:
            _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] 颜色检测出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        _execute_flow(node.id, "no", ctx)


def _handle_check_ocr(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from webui_backend.detection.capture import capture_screen
        from webui_backend.detection.ocr import OCREngine
        from webui_backend.coordinate_resolver import resolve_region

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

        if result["found"]:
            _execute_flow(node.id, "match", ctx)
        else:
            _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] OCR检测出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        _execute_flow(node.id, "no", ctx)


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


def _monitor_check_color(node, ctx):
    try:
        from webui_backend.detection.capture import capture_screen
        from webui_backend.detection.color import check_color
        from webui_backend.coordinate_resolver import resolve_region

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
        ctx.last_capture_cache[node.id] = img
        return result["found"]
    except Exception:
        return False


def _monitor_check_ocr(node, ctx):
    try:
        from webui_backend.detection.capture import capture_screen
        from webui_backend.detection.ocr import OCREngine
        from webui_backend.coordinate_resolver import resolve_region

        params = node.params
        mode = params.get("mode", "screen")
        rect = params.get("rect", [0, 0, 100, 30])
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        region = resolve_region(mode, rect, hwnd)
        img = capture_screen(region)

        engine = OCREngine()
        match_number = None
        if params.get("match_mode", "contain").startswith("number_"):
            match_number = float(params.get("match_number", 0))
        result = engine.detect(img, match_text=params.get("match_text", ""),
                               match_mode=params.get("match_mode", "contain"),
                               match_number=match_number)
        if params.get("store_var"):
            ctx.variables[params["store_var"]] = result.get("text", "")
        elif not params.get("match_text", "") and result.get("text", ""):
            ctx.variables[node.id + "_ocr_text"] = result.get("text", "")
        if params.get("store_number") and result.get("number") is not None:
            ctx.variables[params["store_number"]] = result["number"]
        elif not params.get("match_text", "") and result.get("number") is not None:
            ctx.variables[node.id + "_ocr_number"] = result["number"]
        return result["found"]
    except Exception:
        return False


def _handle_var_set(node: ExecNode, ctx: ExecContext):
    name = node.params.get("name", "")
    value = _resolve_value(node.params.get("value", ""), ctx)
    var_type = node.params.get("var_type", "string")

    if var_type == "number":
        try:
            value = float(value)
        except (ValueError, TypeError):
            value = 0.0
    elif var_type == "boolean":
        value = bool(value)

    if name:
        ctx.variables[name] = value
    _execute_flow(node.id, "next", ctx)


def _handle_var_math(node: ExecNode, ctx: ExecContext):
    op = node.params.get("op", "add")
    _MATH_OP_ALIASES = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod"}
    op = _MATH_OP_ALIASES.get(op, op)
    a = float(_resolve_value(node.params.get("a", "0"), ctx))
    b = float(_resolve_value(node.params.get("b", "0"), ctx))
    store_var = node.params.get("store_var", "")

    ops = {
        "add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b,
        "div": lambda: a / b if b != 0 else 0, "mod": lambda: a % b if b != 0 else 0,
        "min": lambda: min(a, b), "max": lambda: max(a, b),
        "abs": lambda: abs(a), "round": lambda: round(a, int(b)),
    }
    result = ops.get(op, lambda: 0)()

    if store_var:
        ctx.variables[store_var] = result
    _execute_flow(node.id, "next", ctx)


def _handle_var_compare(node: ExecNode, ctx: ExecContext):
    op = node.params.get("op", "gt")
    _COMPARE_OP_ALIASES = {">": "gt", "<": "lt", ">=": "ge", "<=": "le", "==": "eq", "!=": "ne"}
    op = _COMPARE_OP_ALIASES.get(op, op)
    a = _resolve_value(node.params.get("a", "0"), ctx)
    b = _resolve_value(node.params.get("b", "0"), ctx)

    try:
        a_num = float(a)
        b_num = float(b)
    except (ValueError, TypeError):
        a_num, b_num = str(a), str(b)

    ops = {
        "eq": lambda: a_num == b_num, "ne": lambda: a_num != b_num,
        "gt": lambda: a_num > b_num, "lt": lambda: a_num < b_num,
        "ge": lambda: a_num >= b_num, "le": lambda: a_num <= b_num,
    }
    result = ops.get(op, lambda: False)()

    ctx.check_results[f"{node.id}.result"] = result
    _execute_flow(node.id, "next", ctx)


def _handle_var_string(node: ExecNode, ctx: ExecContext):
    op = node.params.get("op", "concat")
    a = str(_resolve_value(node.params.get("a", ""), ctx))
    b = str(_resolve_value(node.params.get("b", ""), ctx))
    store_var = node.params.get("store_var", "")

    if op == "concat":
        result = a + b
    elif op == "substr":
        try:
            parts = b.split(",")
            start = int(parts[0]) if len(parts) > 0 else 0
            length = int(parts[1]) if len(parts) > 1 else len(a)
            result = a[start:start + length]
        except (ValueError, IndexError):
            result = a
    elif op == "replace":
        result = a.replace(b, "")
    elif op == "split":
        parts = a.split(b) if b else [a]
        result = parts[0] if parts else ""
    elif op == "regex_extract":
        import re
        match = re.search(b, a)
        result = match.group(0) if match else ""
    else:
        result = a

    if store_var:
        ctx.variables[store_var] = result
    _execute_flow(node.id, "next", ctx)


def _handle_var_convert(node: ExecNode, ctx: ExecContext):
    to_type = node.params.get("to_type", "number")
    input_var = node.params.get("input_var", "")
    store_var = node.params.get("store_var", "")

    value = ctx.variables.get(input_var, "")

    if to_type == "number":
        try:
            result = float(value)
        except (ValueError, TypeError):
            result = 0.0
    elif to_type == "string":
        result = str(value)
    elif to_type == "boolean":
        result = bool(value)
    else:
        result = value

    if store_var:
        ctx.variables[store_var] = result
    _execute_flow(node.id, "next", ctx)


def _handle_mouse_move(node: ExecNode, ctx: ExecContext):
    params = node.params
    x = _resolve_value(params.get("x", 0), ctx)
    y = _resolve_value(params.get("y", 0), ctx)
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

    from webui_backend.coordinate_resolver import resolve_coords
    phys_x, phys_y = resolve_coords(mode, float(x), float(y), hwnd)

    duration = float(params.get("duration", 200))
    easing = params.get("easing", "ease_in_out")

    if duration > 0:
        steps = max(1, min(int(duration / 10), 100))
        step_delay = duration / 1000.0 / steps
        cx, cy = _get_cursor_pos()
        for i in range(1, steps + 1):
            if ctx.stop_event.is_set():
                return
            t = i / steps
            if easing == "ease_in":
                t = t * t
            elif easing == "ease_out":
                t = 1 - (1 - t) * (1 - t)
            elif easing == "ease_in_out":
                t = t * t * (3 - 2 * t)
            mx = int(cx + (phys_x - cx) * t)
            my = int(cy + (phys_y - cy) * t)
            set_cursor_pos(mx, my)
            if i < steps:
                precise_sleep(step_delay, ctx.stop_event)
    else:
        set_cursor_pos(phys_x, phys_y)

    _execute_flow(node.id, "next", ctx)


def _handle_mouse_move_rel(node: ExecNode, ctx: ExecContext):
    params = node.params
    dx = float(_resolve_value(params.get("dx", 0), ctx))
    dy = float(_resolve_value(params.get("dy", 0), ctx))
    duration = float(params.get("duration", 200))

    cx, cy = _get_cursor_pos()
    target_x = cx + int(dx)
    target_y = cy + int(dy)

    if duration > 0:
        _interpolated_move(target_x, target_y, duration, ctx.stop_event)
    else:
        set_cursor_pos(target_x, target_y)

    _execute_flow(node.id, "next", ctx)


def _handle_check_image(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        import cv2
        import numpy as np
        from webui_backend.detection.capture import capture_screen
        from webui_backend.coordinate_resolver import resolve_region

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
        if multi_match:
            locs = np.where(result >= threshold)
            matches = list(zip(*locs[::-1]))
            found = len(matches) > 0
            if found and params.get("store_var"):
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
            if found and params.get("store_var"):
                ctx.variables[params["store_var"]] = {
                    "x": int(match_loc[0] + template.shape[1] / 2),
                    "y": int(match_loc[1] + template.shape[0] / 2),
                    "confidence": float(max_val),
                }

        ctx.check_results[f"{node.id}.result"] = found
        if found:
            _execute_flow(node.id, "match", ctx)
        else:
            _execute_flow(node.id, "no", ctx)
    except Exception as e:
        print(f"[新引擎] 图像匹配出错: {e}")
        ctx.check_results[f"{node.id}.result"] = False
        _execute_flow(node.id, "no", ctx)


def _handle_check_screen(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        import cv2
        import numpy as np
        from webui_backend.detection.capture import capture_screen
        from webui_backend.coordinate_resolver import resolve_region

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


def _handle_wait_cond(node: ExecNode, ctx: ExecContext):
    timeout_ms = float(node.params.get("timeout", 10000))
    interval_ms = float(node.params.get("interval", 100))

    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if ctx.stop_event.is_set():
            return
        cond_val = ctx.check_results.get(f"{node.id}.cond", None)
        if cond_val is True:
            _execute_flow(node.id, "met", ctx)
            return
        precise_sleep(interval_ms / 1000.0, ctx.stop_event)

    _execute_flow(node.id, "timeout", ctx)


def _handle_goto(node: ExecNode, ctx: ExecContext):
    target_id = node.params.get("target_node_id", "")
    if target_id:
        ctx._goto_target = target_id
    else:
        print("[新引擎] 跳转节点未指定目标ID")


def _handle_seq_check(node: ExecNode, ctx: ExecContext):
    retry = node.params.get("retry", True)
    max_retries = int(node.params.get("max_retries", 100))
    attempts = 0

    while True:
        if ctx.stop_event.is_set():
            return
        cond_val = ctx.check_results.get(f"{node.id}.cond", None)
        if cond_val is True:
            _execute_flow(node.id, "pass", ctx)
            return
        attempts += 1
        if not retry or attempts >= max_retries:
            _execute_flow(node.id, "fail", ctx)
            return
        precise_sleep(0.1, ctx.stop_event)


def _handle_state_machine(node: ExecNode, ctx: ExecContext):
    states_str = node.params.get("states", "")
    fail_state = node.params.get("fail_state", "")

    if not states_str:
        _execute_flow(node.id, "done", ctx)
        return

    states = [s.strip() for s in states_str.split("→") if s.strip()]
    current = 0

    while current < len(states):
        if ctx.stop_event.is_set():
            return
        cond_val = ctx.check_results.get(f"{node.id}.cond", None)
        if cond_val is True:
            current += 1
        elif cond_val is False and fail_state:
            fail_idx = None
            for i, s in enumerate(states):
                if s.strip() == fail_state:
                    fail_idx = i
                    break
            if fail_idx is not None:
                current = fail_idx
            else:
                current += 1
        else:
            precise_sleep(0.1, ctx.stop_event)

    _execute_flow(node.id, "done", ctx)


def _handle_preset_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    x = _resolve_value(params.get("x", 0), ctx)
    y = _resolve_value(params.get("y", 0), ctx)
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

    from webui_backend.coordinate_resolver import resolve_coords
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
        from webui_backend.detection.capture import capture_screen
        from webui_backend.coordinate_resolver import resolve_region, resolve_coords

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
            phys_x, phys_y = resolve_coords(mode, click_x, click_y, hwnd)
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
        from webui_backend.detection.capture import capture_screen
        from webui_backend.detection.ocr import OCREngine
        from webui_backend.coordinate_resolver import resolve_region

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


def _handle_const_number(node: ExecNode, ctx: ExecContext):
    ctx.variables[node.id + "_out"] = node.params.get("value", 0)


def _handle_const_string(node: ExecNode, ctx: ExecContext):
    ctx.variables[node.id + "_out"] = node.params.get("value", "")


def _handle_const_bool(node: ExecNode, ctx: ExecContext):
    ctx.variables[node.id + "_out"] = bool(node.params.get("value", True))


def _handle_math_op(node: ExecNode, ctx: ExecContext):
    import math
    a = float(_resolve_value(node.params.get("a", 0), ctx))
    b = float(_resolve_value(node.params.get("b", 0), ctx))
    op = node.params.get("op", "add")
    ops = {
        "add": lambda: a + b,
        "sub": lambda: a - b,
        "mul": lambda: a * b,
        "div": lambda: a / b if b != 0 else 0,
        "mod": lambda: a % b if b != 0 else 0,
        "pow": lambda: a ** b,
        "min": lambda: min(a, b),
        "max": lambda: max(a, b),
    }
    ctx.variables[node.id + "_out"] = ops.get(op, lambda: 0)()


def _handle_math_func(node: ExecNode, ctx: ExecContext):
    import math
    x = float(_resolve_value(node.params.get("x", 0), ctx))
    func = node.params.get("func", "abs")
    funcs = {
        "abs": lambda: abs(x),
        "round": lambda: round(x),
        "floor": lambda: math.floor(x),
        "ceil": lambda: math.ceil(x),
        "sqrt": lambda: math.sqrt(x) if x >= 0 else 0,
        "sin": lambda: math.sin(x),
        "cos": lambda: math.cos(x),
        "log": lambda: math.log(x) if x > 0 else 0,
        "negate": lambda: -x,
    }
    ctx.variables[node.id + "_out"] = funcs.get(func, lambda: 0)()


def _handle_logic_op(node: ExecNode, ctx: ExecContext):
    a = bool(_resolve_value(node.params.get("a", True), ctx))
    b = bool(_resolve_value(node.params.get("b", True), ctx))
    op = node.params.get("op", "and")
    ops = {
        "and": lambda: a and b,
        "or": lambda: a or b,
        "xor": lambda: a != b,
        "not": lambda: not a,
        "nand": lambda: not (a and b),
        "nor": lambda: not (a or b),
    }
    ctx.variables[node.id + "_out"] = ops.get(op, lambda: False)()


def _handle_compare(node: ExecNode, ctx: ExecContext):
    a = float(_resolve_value(node.params.get("a", 0), ctx))
    b = float(_resolve_value(node.params.get("b", 0), ctx))
    op = node.params.get("op", "gt")
    ops = {
        "eq": lambda: a == b,
        "ne": lambda: a != b,
        "gt": lambda: a > b,
        "lt": lambda: a < b,
        "ge": lambda: a >= b,
        "le": lambda: a <= b,
    }
    ctx.variables[node.id + "_out"] = ops.get(op, lambda: False)()


def _handle_string_op(node: ExecNode, ctx: ExecContext):
    s = str(_resolve_value(node.params.get("input_str", ""), ctx))
    op = node.params.get("op", "concat")
    pa = node.params.get("param_a", "")
    pb = node.params.get("param_b", "")
    pc = node.params.get("param_c", "")
    if op == "concat":
        result = s + pa
    elif op == "replace":
        result = s.replace(pa, pb)
    elif op == "upper":
        result = s.upper()
    elif op == "lower":
        result = s.lower()
    elif op == "trim":
        result = s.strip()
    elif op == "substring":
        try:
            start = int(pb) if pb else 0
            end = int(pc) if pc else len(s)
            result = s[start:end]
        except (ValueError, IndexError):
            result = s
    elif op == "split_index":
        try:
            parts = s.split(pa) if pa else [s]
            idx = int(pb) if pb else 0
            result = parts[idx] if 0 <= idx < len(parts) else ""
        except (ValueError, IndexError):
            result = s
    else:
        result = s
    ctx.variables[node.id + "_out"] = result


def _handle_condition(node: ExecNode, ctx: ExecContext):
    cond_var = node.params.get("cond_var", "")
    if cond_var:
        cond = bool(ctx.variables.get(cond_var, False))
    else:
        cond = bool(ctx.variables.get(node.id + "_cond", False))
    if cond:
        result = _resolve_value(node.params.get("true_val", ""), ctx)
    else:
        result = _resolve_value(node.params.get("false_val", ""), ctx)
    ctx.variables[node.id + "_out"] = result


def _handle_utility_delay(node: ExecNode, ctx: ExecContext):
    ms = float(node.params.get("ms", 1000))
    precise_sleep(ms / 1000.0, ctx.stop_event)
    _execute_flow(node.id, "next", ctx)


NODE_HANDLERS = {
    "_handle_mouse_click": _handle_mouse_click,
    "_handle_key_action": _handle_key_action,
    "_handle_mouse_scroll": _handle_mouse_scroll,
    "_handle_text_input": _handle_text_input,
    "_handle_wait": _handle_wait,
    "_handle_if_else": _handle_if_else,
    "_handle_loop_count": _handle_loop_count,
    "_handle_loop_while": _handle_loop_while,
    "_handle_call_script_sync": _handle_call_script_sync,
    "_handle_call_script_async": _handle_call_script_async,
    "_handle_check_color": _handle_check_color,
    "_handle_check_ocr": _handle_check_ocr,
    "_handle_monitor_node": _handle_monitor_node,
    "_handle_var_set": _handle_var_set,
    "_handle_var_math": _handle_var_math,
    "_handle_var_compare": _handle_var_compare,
    "_handle_var_string": _handle_var_string,
    "_handle_var_convert": _handle_var_convert,
    "_handle_mouse_move": _handle_mouse_move,
    "_handle_mouse_move_rel": _handle_mouse_move_rel,
    "_handle_check_image": _handle_check_image,
    "_handle_check_screen": _handle_check_screen,
    "_handle_wait_cond": _handle_wait_cond,
    "_handle_goto": _handle_goto,
    "_handle_seq_check": _handle_seq_check,
    "_handle_state_machine": _handle_state_machine,
    "_handle_preset_click": _handle_preset_click,
    "_handle_preset_find_click": _handle_preset_find_click,
    "_handle_preset_read_text": _handle_preset_read_text,
    "_handle_const_number": _handle_const_number,
    "_handle_const_string": _handle_const_string,
    "_handle_const_bool": _handle_const_bool,
    "_handle_math_op": _handle_math_op,
    "_handle_math_func": _handle_math_func,
    "_handle_logic_op": _handle_logic_op,
    "_handle_compare": _handle_compare,
    "_handle_string_op": _handle_string_op,
    "_handle_condition": _handle_condition,
    "_handle_utility_delay": _handle_utility_delay,
}


def execute_graph(graph: ExecGraph, stop_event: threading.Event):
    ctx = ExecContext(graph, stop_event)
    graph._exec_ctx = ctx

    profile_name = graph.settings.get("execution_profile", "standard")
    profile = PROFILE_PRESETS.get(profile_name, PROFILE_PRESETS["standard"])
    ctx._profile = profile

    if profile.get("interception_kb") or profile.get("interception_mouse"):
        try:
            ctx.interception_session = InterceptionSession(
                use_keyboard=bool(profile.get("interception_kb", False)),
                use_mouse=bool(profile.get("interception_mouse", False)),
            )
        except Exception as e:
            print(f"[新引擎] InterceptionSession 初始化失败，回退 SendInput: {e}")
            ctx.interception_session = None

    if not graph.entry_node_id:
        print("[新引擎] 错误：未找到入口节点")
        return

    monitor_ids = getattr(graph, 'monitor_entry_ids', [])
    monitor_threads = []
    for mid in monitor_ids:
        if mid == graph.entry_node_id:
            continue
        if ctx.stop_event.is_set():
            break
        t = threading.Thread(target=_execute_node, args=(mid, ctx), daemon=True)
        monitor_threads.append(t)
        t.start()

    try:
        _execute_node(graph.entry_node_id, ctx)
    finally:
        release_all_modifiers()
        ctx.task_pool.stop_all()
        for mt in monitor_threads:
            mt.join(timeout=1.0)
