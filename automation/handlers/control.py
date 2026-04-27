import os
import time
import threading

from automation.engine import (
    _resolve_value, _execute_flow, _get_old_engine,
)
from automation.compiler import ExecNode
from automation.engine import ExecContext

from engine.precision import precise_sleep_v5 as precise_sleep


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


def _handle_wait_cond(node: ExecNode, ctx: ExecContext):
    timeout_ms = float(node.params.get("timeout", 10000))
    interval_ms = float(node.params.get("interval", 100))

    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if ctx.stop_event.is_set():
            return
        data_sources = node.get_data_inputs("cond")
        conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                      for src in data_sources]
        if conditions and all(conditions):
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
        data_sources = node.get_data_inputs("cond")
        conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                      for src in data_sources]
        if conditions and all(conditions):
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
        data_sources = node.get_data_inputs("cond")
        conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                      for src in data_sources]
        cond_val = all(conditions) if conditions else None
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


def register(handlers: dict):
    handlers["_handle_if_else"] = _handle_if_else
    handlers["_handle_loop_count"] = _handle_loop_count
    handlers["_handle_loop_while"] = _handle_loop_while
    handlers["_handle_call_script_sync"] = _handle_call_script_sync
    handlers["_handle_call_script_async"] = _handle_call_script_async
    handlers["_handle_wait_cond"] = _handle_wait_cond
    handlers["_handle_goto"] = _handle_goto
    handlers["_handle_seq_check"] = _handle_seq_check
    handlers["_handle_state_machine"] = _handle_state_machine
