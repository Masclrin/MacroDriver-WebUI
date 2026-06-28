import os
import re
import time
import threading
import json

from automation.engine import (
    _resolve_value, _execute_flow, _execute_node, _get_old_engine,
    _collect_flow_descendants, _reset_body_nodes, _cancel_child_scopes,
    _get_pause_event,
)
from automation.compiler import ExecNode
from automation.handlers.variable import _extract_var_name
from automation.engine import ExecContext, BranchContext, Scope

from engine.precision import precise_sleep_v5 as precise_sleep
from engine.precision import set_thread_affinity, clear_thread_affinity

_script_compile_cache = {}
_script_cache_lock = threading.Lock()


def _re_execute_condition_sources(node, ctx):
    data_sources = node.get_data_inputs("cond")
    for src in data_sources:
        src_node_id = src["source_node_id"]
        src_node = ctx.graph.nodes.get(src_node_id)
        if src_node:
            if src_node.type.startswith(("detection/", "utility/condition", "utility/bookmark")):
                branch_ctx = ctx._get_current_branch_ctx()
                executed_set = branch_ctx._executed_nodes if branch_ctx else ctx._executed_nodes
                with ctx._data_lock:
                    executed_set.discard(src_node_id)
                _execute_node(src_node_id, ctx)


def _handle_if_else(node: ExecNode, ctx: ExecContext):
    _re_execute_condition_sources(node, ctx)
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
    body_nodes = _collect_flow_descendants(ctx.graph, node.id, "body")

    for i in range(count):
        if ctx.stop_event.is_set():
            return
        if i > 0:
            _reset_body_nodes(body_nodes, ctx)
        if counter_var:
            ctx.safe_set_variable(_extract_var_name(counter_var), i)
        _execute_flow(node.id, "body", ctx)

    _execute_flow(node.id, "next", ctx)


def _handle_loop_while(node: ExecNode, ctx: ExecContext):
    max_iter = int(_resolve_value(node.params.get("max_iterations", 10000), ctx))
    check_at = node.params.get("check_at", "start")
    body_nodes = _collect_flow_descendants(ctx.graph, node.id, "body")

    for i in range(max_iter):
        if ctx.stop_event.is_set():
            return

        if check_at == "start":
            _re_execute_condition_sources(node, ctx)
            data_sources = node.get_data_inputs("cond")
            conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                          for src in data_sources]
            if not conditions or not all(conditions):
                break

        if i > 0:
            _reset_body_nodes(body_nodes, ctx)
        _execute_flow(node.id, "body", ctx)

        if check_at == "end":
            _re_execute_condition_sources(node, ctx)
            data_sources = node.get_data_inputs("cond")
            conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                          for src in data_sources]
            if not conditions or not all(conditions):
                break

    _execute_flow(node.id, "next", ctx)


def _get_compiled_script(path, oe):
    cache_key = (path, os.path.getmtime(path))
    with _script_cache_lock:
        cached = _script_compile_cache.get(cache_key)
        if cached is not None:
            return cached

    script = oe.load_macro_from_file(path)
    compiled = oe.compile_macro(script)
    compiled = oe.batch_compiled_macro(compiled)

    with _script_cache_lock:
        _script_compile_cache[cache_key] = compiled
    return compiled


def _clear_script_cache():
    with _script_cache_lock:
        _script_compile_cache.clear()


def _handle_call_script_sync(node: ExecNode, ctx: ExecContext):
    path = _resolve_value(node.params.get("path", ""), ctx)
    if not path or not os.path.exists(path):
        print(f"[新引擎] 宏文件不存在: {path}")
        ctx.log_error(f"宏文件不存在: {path}", node_id=node.id, error_type="system")
        ctx.log_warning("宏文件不存在，继续执行后续节点", node_id=node.id)
        _execute_flow(node.id, "next", ctx)
        return

    _oe = _get_old_engine()
    compiled = _get_compiled_script(path, _oe)

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
                precise_sleep(delay, ctx.stop_event, pause_event=_get_pause_event(ctx))
    else:
        _oe.execute_macro_once(compiled, ctx.stop_event, ctx.pause_event, macro_name=os.path.basename(path), options=opts)

    _execute_flow(node.id, "next", ctx)


def _handle_call_script_async(node: ExecNode, ctx: ExecContext):
    path = _resolve_value(node.params.get("path", ""), ctx)
    if not path or not os.path.exists(path):
        print(f"[新引擎] 宏文件不存在: {path}")
        ctx.log_error(f"宏文件不存在: {path}", node_id=node.id, error_type="system")
        _execute_flow(node.id, "next", ctx)
        return

    _oe = _get_old_engine()
    compiled = _get_compiled_script(path, _oe)

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
        if not hasattr(ctx, 'graph') or ctx.graph is None:
            return
        if not hasattr(ctx, '_branches'):
            return
        try:
            flow_name = "completed" if status == "completed" else "interrupted"
            if hasattr(ctx, '_event_queue') and ctx._event_queue is not None:
                ctx._event_queue.put(("execute_flow", async_node_id, flow_name))
            else:
                _execute_flow(async_node_id, flow_name, ctx)
        except Exception as e:
            print(f"[异步宏] on_task_complete 执行异常: {e}")

    task_id = ctx.task_pool.start(
        node_id=node.id,
        compiled=compiled,
        macro_name=os.path.basename(path),
        options=opts,
        stop_event_parent=ctx.stop_event,
        on_complete=on_task_complete,
        affinity=ctx._get_current_affinity(),
    )

    _execute_flow(node.id, "next", ctx)


def _handle_wait_cond(node: ExecNode, ctx: ExecContext):
    timeout_ms = float(_resolve_value(node.params.get("timeout", 10000), ctx))
    interval_ms = float(_resolve_value(node.params.get("interval", 100), ctx))

    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if ctx.stop_event.is_set():
            return
        _re_execute_condition_sources(node, ctx)
        data_sources = node.get_data_inputs("cond")
        conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                      for src in data_sources]
        if conditions and all(conditions):
            _execute_flow(node.id, "met", ctx)
            return
        precise_sleep(interval_ms / 1000.0, ctx.stop_event, pause_event=_get_pause_event(ctx))

    _execute_flow(node.id, "timeout", ctx)


def _handle_goto(node: ExecNode, ctx: ExecContext):
    target_id = _resolve_value(node.params.get("target_node_id", ""), ctx)
    if target_id:
        ctx._goto_target = target_id
        branch_ctx = ctx._get_current_branch_ctx()
        if branch_ctx:
            branch_ctx._goto_target = target_id
    else:
        print("[新引擎] 跳转节点未指定目标ID")


def _handle_seq_check(node: ExecNode, ctx: ExecContext):
    retry = node.params.get("retry", True)
    max_retries = int(_resolve_value(node.params.get("max_retries", 100), ctx))
    poll_interval = int(_resolve_value(node.params.get("poll_interval_ms", 100), ctx)) / 1000.0
    attempts = 0

    while True:
        if ctx.stop_event.is_set():
            return
        _re_execute_condition_sources(node, ctx)
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
        precise_sleep(poll_interval, ctx.stop_event, pause_event=_get_pause_event(ctx))


def _handle_state_machine(node: ExecNode, ctx: ExecContext):
    states_str = _resolve_value(node.params.get("states", ""), ctx)
    fail_state = _resolve_value(node.params.get("fail_state", ""), ctx)
    poll_interval = int(_resolve_value(node.params.get("poll_interval_ms", 100), ctx)) / 1000.0

    if not states_str:
        _execute_flow(node.id, "done", ctx)
        return

    states = [s.strip() for s in states_str.split("→") if s.strip()]
    current = 0

    while current < len(states):
        if ctx.stop_event.is_set():
            return
        _re_execute_condition_sources(node, ctx)
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
            precise_sleep(poll_interval, ctx.stop_event, pause_event=_get_pause_event(ctx))

    _execute_flow(node.id, "done", ctx)


def _parse_affinity_config(param_val):
    if not param_val:
        return None
    if isinstance(param_val, dict):
        return param_val
    try:
        return json.loads(param_val)
    except (json.JSONDecodeError, TypeError):
        return None


def _handle_fork(node: ExecNode, ctx: ExecContext):
    branch_count = int(node.params.get("branch_count", 2))
    max_branches = 8
    branch_ports = ["branch" + str(i + 1) for i in range(max_branches)]

    active_branches = []
    for i, port_name in enumerate(branch_ports):
        children = node.get_flow_children(port_name)
        if children:
            affinity_key = f"branch_affinity_{i + 1}"
            affinity_raw = node.params.get(affinity_key, "")
            affinity_config = _parse_affinity_config(affinity_raw)
            branch_id = f"{node.id}_branch{i + 1}"
            active_branches.append({
                "port_name": port_name,
                "branch_id": branch_id,
                "children": children,
                "affinity_config": affinity_config,
                "index": i,
            })

    if not active_branches:
        return

    scope_id = f"{node.id}_scope"
    parent_branch_id = ctx._get_branch_id()

    scope = Scope(
        scope_id=scope_id,
        fork_node_id=node.id,
        parent_branch_id=parent_branch_id,
    )
    ctx._scopes[scope_id] = scope

    if parent_branch_id:
        parent_bctx = ctx._branches.get(parent_branch_id)
        if parent_bctx:
            parent_bctx.child_scope_ids.append(scope_id)

    for branch_info in active_branches:
        branch_id = branch_info["branch_id"]
        affinity_config = branch_info["affinity_config"]
        scope.branch_ids.append(branch_id)

        branch_ctx = BranchContext(
            branch_id=branch_id,
            parent_ctx=ctx,
            fork_node_id=node.id,
            affinity_config=affinity_config,
            parent_branch_id=parent_branch_id,
            scope_id=scope_id,
        )
        ctx._branches[branch_id] = branch_ctx

        core_index = None
        if affinity_config and affinity_config.get("enabled"):
            core_index = affinity_config.get("core", -1)
            if core_index == -1:
                core_index = 4 + branch_info["index"]

        def branch_worker(bid, bctx, port_name, core_idx):
            if core_idx is not None:
                try:
                    with ctx._data_lock:
                        for owner, ocore in ctx._affinity_tracker.items():
                            if ocore == core_idx and owner != bid:
                                print(f"[Fork] 警告: 分支 {bid} 绑核到核心 {core_idx}，与 {owner} 冲突! 建议使用不同核心。")
                        ctx._affinity_tracker[bid] = core_idx
                    set_thread_affinity(core_idx)
                    bctx._current_affinity = core_idx
                except Exception:
                    pass
            try:
                ctx._set_branch_id(bid)
                ctx._set_current_affinity(core_idx)
                _execute_flow(node.id, port_name, ctx)
                bctx.set_status("completed")
            except Exception as e:
                print(f"[Fork] 分支 {bid} 执行异常: {e}")
                bctx.set_status("error")
                ctx.log_error(f"分支 {bid} 执行异常: {e}", node_id=node.id, error_type="runtime")
            finally:
                try:
                    clear_thread_affinity()
                except Exception:
                    pass

        t = threading.Thread(
            target=branch_worker,
            args=(branch_id, branch_ctx, branch_info["port_name"], core_index),
            daemon=True,
        )
        branch_ctx.thread = t
        t.start()

    _execute_flow(node.id, "next", ctx)

    done_children = node.get_flow_children("done")
    if done_children and active_branches:
        def wait_all_branches_done():
            while not ctx.stop_event.is_set():
                if ctx.pause_event and ctx.pause_event.is_set():
                    ctx.pause_event.wait(timeout=0.1)
                    continue
                all_done = True
                for bi in active_branches:
                    bctx = ctx._branches.get(bi["branch_id"])
                    if bctx and bctx.status == "running":
                        all_done = False
                        break
                if all_done:
                    break
                ctx.stop_event.wait(timeout=0.1)
            if not ctx.stop_event.is_set():
                _execute_flow(node.id, "done", ctx)

        wait_t = threading.Thread(target=wait_all_branches_done, daemon=True)
        wait_t.start()


def _resolve_join_targets(join_node, graph, ctx):
    targets = set()
    visited = set()
    target_fork_node_id = join_node.params.get("target_fork_node_id", "")
    if target_fork_node_id:
        scope = ctx._scopes.get(f"{target_fork_node_id}_scope")
        if scope:
            targets.update(scope.branch_ids)
            for child_scope_id in scope.child_scope_ids:
                child_scope = ctx._scopes.get(child_scope_id)
                if child_scope:
                    targets.update(child_scope.branch_ids)
        return targets

    max_branches = 8
    branch_ports = ["branch" + str(i + 1) for i in range(max_branches)]
    for port_name in branch_ports:
        sources = join_node.get_flow_inputs(port_name)
        if not sources:
            continue
        for src in sources:
            upstream_node_id = src["source_node_id"]
            _trace_upstream_branches(upstream_node_id, graph, ctx, targets, visited)

    return targets


def _trace_upstream_branches(node_id, graph, ctx, targets, visited):
    if node_id in visited:
        return
    visited.add(node_id)

    node = graph.nodes.get(node_id)
    if not node:
        return

    if node.type in ("control/fork", "control/race"):
        scope = ctx._scopes.get(f"{node.id}_scope")
        if scope:
            targets.update(scope.branch_ids)
            for child_scope_id in scope.child_scope_ids:
                child_scope = ctx._scopes.get(child_scope_id)
                if child_scope:
                    targets.update(child_scope.branch_ids)
        return

    for port_name, sources in node.flow_inputs.items():
        for src in sources:
            _trace_upstream_branches(src["source_node_id"], graph, ctx, targets, visited)


def _cancel_join_targets(ctx, arrived_branches, expected_branches):
    to_cancel = expected_branches - arrived_branches
    for branch_id in to_cancel:
        bctx = ctx._branches.get(branch_id)
        if bctx and bctx.status == "running":
            bctx.cancel()
        _cancel_child_scopes(branch_id, ctx)



def _handle_join(node: ExecNode, ctx: ExecContext):
    wait_mode = node.params.get("wait_mode", "all")
    timeout_ms = float(_resolve_value(node.params.get("timeout_ms", 30000), ctx))
    cancel_others_raw = node.params.get("cancel_others", False)
    cancel_others = cancel_others_raw if isinstance(cancel_others_raw, bool) else str(cancel_others_raw).lower() == "true"

    max_branches = 8
    branch_ports = ["branch" + str(i + 1) for i in range(max_branches)]

    connected_ports = set()
    for port_name in branch_ports:
        if node.get_flow_inputs(port_name):
            connected_ports.add(port_name)

    if not connected_ports:
        _execute_flow(node.id, "done", ctx)
        return

    expected_branches = _resolve_join_targets(node, ctx.graph, ctx)

    required_branches = set()
    if wait_mode == "all":
        required_branches = set(expected_branches)
    elif wait_mode == "any":
        required_branches = set()
    elif wait_mode == "custom":
        for port_name in connected_ports:
            idx = branch_ports.index(port_name) + 1
            required_key = f"branch_required_{idx}"
            req_val = node.params.get(required_key, True)
            req_bool = req_val if isinstance(req_val, bool) else str(req_val).lower() != "false"
            if req_bool:
                for bid in expected_branches:
                    if bid.endswith(f"_branch{idx}"):
                        required_branches.add(bid)
        if not required_branches:
            required_branches = set()

    current_branch_id = ctx._get_branch_id()
    arrived_branch = current_branch_id

    join_key = node.id
    with ctx._data_lock:
        if join_key not in ctx._join_events:
            ctx._join_events[join_key] = threading.Event()
            ctx._join_arrivals[join_key] = set()
            ctx._join_done_flag[join_key] = False
        elif ctx._join_events[join_key].is_set():
            ctx._join_events[join_key].clear()
            ctx._join_arrivals[join_key].clear()
            ctx._join_done_flag[join_key] = False

        if arrived_branch:
            bctx = ctx._branches.get(arrived_branch)
            if bctx and bctx.status != "cancelled":
                ctx._join_arrivals[join_key].add(arrived_branch)
            elif not bctx:
                ctx._join_arrivals[join_key].add(arrived_branch)

    join_event = ctx._join_events[join_key]

    def check_condition(arrivals_snapshot):
        if wait_mode == "all":
            return expected_branches.issubset(arrivals_snapshot) if expected_branches else len(arrivals_snapshot) > 0
        elif wait_mode == "any":
            return len(arrivals_snapshot) > 0
        elif wait_mode == "custom":
            if required_branches:
                return required_branches.issubset(arrivals_snapshot)
            return len(arrivals_snapshot) > 0
        return False

    with ctx._data_lock:
        arrivals_snapshot = set(ctx._join_arrivals[join_key])
        if check_condition(arrivals_snapshot) and not ctx._join_done_flag.get(join_key, False):
            ctx._join_done_flag[join_key] = True
            should_execute = True
        else:
            should_execute = False

    if should_execute:
        if cancel_others:
            _cancel_join_targets(ctx, arrivals_snapshot, expected_branches)
        join_event.set()
        _execute_flow(node.id, "done", ctx)
        return

    deadline = time.time() + timeout_ms / 1000.0 if timeout_ms > 0 else None
    while not join_event.is_set() and not ctx.stop_event.is_set():
        with ctx._data_lock:
            for bid in list(expected_branches):
                bctx = ctx._branches.get(bid)
                if bctx and bctx.status in ("completed", "error") and bid not in ctx._join_arrivals[join_key]:
                    ctx._join_arrivals[join_key].add(bid)
            arrivals_snapshot = set(ctx._join_arrivals[join_key])
            if check_condition(arrivals_snapshot) and not ctx._join_done_flag.get(join_key, False):
                ctx._join_done_flag[join_key] = True
                should_execute = True
                break

        if deadline and time.time() >= deadline:
            with ctx._data_lock:
                if not ctx._join_done_flag.get(join_key, False):
                    ctx._join_done_flag[join_key] = True
                    should_execute = True
            break

        join_event.wait(timeout=0.05)

    if should_execute:
        with ctx._data_lock:
            arrivals_snapshot = set(ctx._join_arrivals[join_key])
        if cancel_others:
            _cancel_join_targets(ctx, arrivals_snapshot, expected_branches)
        join_event.set()
        _execute_flow(node.id, "done", ctx)


def _handle_race_win(node: ExecNode, ctx: ExecContext):
    branch_id = ctx._get_branch_id()
    branch_ctx = ctx._branches.get(branch_id) if branch_id else None

    if branch_ctx and branch_ctx.scope_id:
        scope = ctx._scopes.get(branch_ctx.scope_id)
        if scope:
            with ctx._data_lock:
                if scope.winner_branch_id is None:
                    scope.winner_branch_id = branch_id
                    race_event = ctx._race_events.get(scope.scope_id)
                    if race_event:
                        race_event.set()

            for bid in scope.branch_ids:
                if bid != branch_id:
                    bctx = ctx._branches.get(bid)
                    if bctx and bctx.status == "running":
                        bctx.cancel()
                    _cancel_child_scopes(bid, ctx)

    ctx.check_results[f"{node.id}.winner_branch"] = branch_id or ""
    _execute_flow(node.id, "next", ctx)


def _handle_race(node: ExecNode, ctx: ExecContext):
    max_branches = 8
    branch_ports = ["branch" + str(i + 1) for i in range(max_branches)]
    cancel_on_first_raw = node.params.get("cancel_on_first", True)
    cancel_on_first = cancel_on_first_raw if isinstance(cancel_on_first_raw, bool) else str(cancel_on_first_raw).lower() == "true"
    timeout_ms = float(_resolve_value(node.params.get("timeout_ms", 0), ctx))

    active_branches = []
    for i, port_name in enumerate(branch_ports):
        children = node.get_flow_children(port_name)
        if children:
            affinity_key = f"branch_affinity_{i + 1}"
            affinity_raw = node.params.get(affinity_key, "")
            affinity_config = _parse_affinity_config(affinity_raw)
            branch_id = f"{node.id}_race_branch{i + 1}"
            active_branches.append({
                "port_name": port_name,
                "branch_id": branch_id,
                "children": children,
                "affinity_config": affinity_config,
                "index": i,
            })

    if not active_branches:
        return

    scope_id = f"{node.id}_scope"
    parent_branch_id = ctx._get_branch_id()

    scope = Scope(
        scope_id=scope_id,
        fork_node_id=node.id,
        parent_branch_id=parent_branch_id,
    )
    ctx._scopes[scope_id] = scope

    if parent_branch_id:
        parent_bctx = ctx._branches.get(parent_branch_id)
        if parent_bctx:
            parent_bctx.child_scope_ids.append(scope_id)

    race_event = threading.Event()
    winner_branch = [None]
    race_lock = threading.Lock()
    ctx._race_events[scope_id] = race_event

    for branch_info in active_branches:
        branch_id = branch_info["branch_id"]
        affinity_config = branch_info["affinity_config"]
        scope.branch_ids.append(branch_id)

        branch_ctx = BranchContext(
            branch_id=branch_id,
            parent_ctx=ctx,
            fork_node_id=node.id,
            affinity_config=affinity_config,
            parent_branch_id=parent_branch_id,
            scope_id=scope_id,
        )
        ctx._branches[branch_id] = branch_ctx

        core_index = None
        if affinity_config and affinity_config.get("enabled"):
            core_index = affinity_config.get("core", -1)
            if core_index == -1:
                core_index = 4 + branch_info["index"]

        def race_worker(bid, bctx, port_name, core_idx):
            if core_idx is not None:
                try:
                    with ctx._data_lock:
                        for owner, ocore in ctx._affinity_tracker.items():
                            if ocore == core_idx and owner != bid:
                                print(f"[Race] 警告: 分支 {bid} 绑核到核心 {core_idx}，与 {owner} 冲突! 建议使用不同核心。")
                        ctx._affinity_tracker[bid] = core_idx
                    set_thread_affinity(core_idx)
                    bctx._current_affinity = core_idx
                except Exception:
                    pass
            try:
                ctx._set_branch_id(bid)
                ctx._set_current_affinity(core_idx)
                _execute_flow(node.id, port_name, ctx)
                bctx.set_status("completed")
            except Exception as e:
                print(f"[Race] 分支 {bid} 执行异常: {e}")
                bctx.set_status("error")
            finally:
                try:
                    clear_thread_affinity()
                except Exception:
                    pass
                scope_obj = ctx._scopes.get(scope_id)
                if scope_obj and scope_obj.winner_branch_id is None and bctx.status == "completed":
                    with race_lock:
                        if winner_branch[0] is None:
                            winner_branch[0] = bid
                            scope_obj.winner_branch_id = bid
                            race_event.set()
                    if cancel_on_first:
                        for other_bid in scope_obj.branch_ids:
                            if other_bid != bid:
                                other_bctx = ctx._branches.get(other_bid)
                                if other_bctx and other_bctx.status == "running":
                                    other_bctx.cancel()

        t = threading.Thread(
            target=race_worker,
            args=(branch_id, branch_ctx, branch_info["port_name"], core_index),
            daemon=True,
        )
        branch_ctx.thread = t
        t.start()

    deadline = time.time() + timeout_ms / 1000.0 if timeout_ms > 0 else None
    while not race_event.is_set() and not ctx.stop_event.is_set():
        if deadline and time.time() >= deadline:
            break
        race_event.wait(timeout=0.05)

    if cancel_on_first and winner_branch[0]:
        scope_obj = ctx._scopes.get(scope_id)
        if scope_obj:
            for bid in scope_obj.branch_ids:
                if bid != winner_branch[0]:
                    bctx = ctx._branches.get(bid)
                    if bctx and bctx.status == "running":
                        bctx.cancel()
                    _cancel_child_scopes(bid, ctx)
    elif winner_branch[0] is None:
        scope_obj = ctx._scopes.get(scope_id)
        if scope_obj:
            for bid in scope_obj.branch_ids:
                bctx = ctx._branches.get(bid)
                if bctx and bctx.status == "running":
                    bctx.cancel()
                _cancel_child_scopes(bid, ctx)


def _resolve_target_branch(target_branch, ctx: ExecContext):
    if not target_branch or target_branch == "all_others":
        return "all_others"
    if target_branch.startswith("${"):
        var_name = target_branch[2:-1]
        resolved = ctx.safe_get_variable(var_name, target_branch)
        return str(resolved)
    return target_branch


def _handle_stop_branch(node: ExecNode, ctx: ExecContext):
    target_branch = _resolve_target_branch(node.params.get("target_branch", "all_others"), ctx)
    current_branch_id = ctx._get_branch_id() or ""

    if target_branch == "all_others":
        for bid, bctx in ctx._branches.items():
            if bid != current_branch_id and bctx.status == "running":
                bctx.cancel()
    else:
        bctx = ctx._branches.get(target_branch)
        if bctx and bctx.status == "running":
            bctx.cancel()

    _execute_flow(node.id, "next", ctx)


def _handle_pause_branch(node: ExecNode, ctx: ExecContext):
    target_branch = _resolve_target_branch(node.params.get("target_branch", "all_others"), ctx)
    current_branch_id = ctx._get_branch_id() or ""

    if target_branch == "all_others":
        for bid, bctx in ctx._branches.items():
            if bid != current_branch_id and bctx.status == "running":
                bctx.pause_event.set()
    else:
        bctx = ctx._branches.get(target_branch)
        if bctx and bctx.status == "running":
            bctx.pause_event.set()

    _execute_flow(node.id, "next", ctx)


def _handle_resume_branch(node: ExecNode, ctx: ExecContext):
    target_branch = _resolve_target_branch(node.params.get("target_branch", "all_others"), ctx)
    current_branch_id = ctx._get_branch_id() or ""

    if target_branch == "all_others":
        for bid, bctx in ctx._branches.items():
            if bid != current_branch_id and bctx.status == "running":
                bctx.pause_event.clear()
    else:
        bctx = ctx._branches.get(target_branch)
        if bctx and bctx.status == "running":
            bctx.pause_event.clear()

    _execute_flow(node.id, "next", ctx)


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
    handlers["_handle_fork"] = _handle_fork
    handlers["_handle_join"] = _handle_join
    handlers["_handle_race"] = _handle_race
    handlers["_handle_race_win"] = _handle_race_win
    handlers["_handle_stop_branch"] = _handle_stop_branch
    handlers["_handle_pause_branch"] = _handle_pause_branch
    handlers["_handle_resume_branch"] = _handle_resume_branch
