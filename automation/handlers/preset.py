from automation.engine import (
    _resolve_value, _get_hwnd, _execute_flow, _do_click, _interpolated_move,
)
from automation.compiler import ExecNode
from automation.engine import ExecContext
from automation.handlers.variable import _extract_var_name

from engine.input_sendinput import set_cursor_pos

import os
import json
import threading


def _handle_preset_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    x = _resolve_value(params.get("x", 960), ctx)
    y = _resolve_value(params.get("y", 540), ctx)
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

    from engine.coordinate import resolve_coords
    phys_x, phys_y = resolve_coords(mode, float(x), float(y), hwnd)

    branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
    pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event

    move_dur = float(_resolve_value(params.get("move_duration", 150), ctx))
    if move_dur > 0:
        _interpolated_move(phys_x, phys_y, move_dur, ctx.stop_event, pause_event=pause_event)
    else:
        set_cursor_pos(phys_x, phys_y)

    button = params.get("button", "left")
    _do_click(button, "click", 0, ctx.stop_event, ctx, pause_event=pause_event)
    _execute_flow(node.id, "next", ctx)


def _handle_preset_find_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        from automation.detection.capture import capture_screen
        from automation.handlers.detection import do_image_match
        from engine.coordinate import resolve_region

        mode = params.get("mode", "screen")
        rect = _resolve_value(params.get("rect", [0, 0, 0, 0]), ctx)
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        template_path = _resolve_value(params.get("template_path", ""), ctx)

        if not template_path:
            ctx.log_error("找图点击: 模板图片路径为空", node_id=node.id, error_type="param")
            _execute_flow(node.id, "not_found", ctx)
            return

        if all(float(v) == 0 for v in rect):
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
            region = (0, 0, sw, sh)
        else:
            region = resolve_region(mode, rect, hwnd)

        img = capture_screen(region, ctx=ctx)
        threshold = float(_resolve_value(params.get("threshold", 0.8), ctx))

        match_result = do_image_match(img, template_path, threshold=threshold, ctx=ctx)

        store_var = _resolve_value(params.get("store_var", ""), ctx) if params.get("store_var") else ""
        if store_var:
            ctx.safe_set_variable(_extract_var_name(store_var), match_result["found"])

        if match_result["found"]:
            click_x = region[0] + match_result["match_x"]
            click_y = region[1] + match_result["match_y"]
            set_cursor_pos(click_x, click_y)
            button = params.get("button", "left")
            branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
            pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event
            _do_click(button, "click", 0, ctx.stop_event, ctx, pause_event=pause_event)
            _execute_flow(node.id, "found", ctx)
        else:
            _execute_flow(node.id, "not_found", ctx)
    except Exception as e:
        print(f"[新引擎] 找图点击出错: {e}")
        ctx.log_error(f"找图点击运行时错误: {e}", node_id=node.id, error_type="runtime")
        ctx.stop_event.set()


def _handle_preset_read_text(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        import re
        from automation.detection.capture import capture_screen
        from automation.detection.ocr import OCREngine
        from engine.coordinate import resolve_region

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
        result = engine.detect(img)
        full_text = result.get("text", "")

        read_mode = params.get("read_mode", "all")
        if read_mode == "number":
            nums = re.findall(r'-?\d+\.?\d*', full_text)
            value = nums[0] if nums else ""
        elif read_mode == "text":
            value = re.sub(r'-?\d+\.?\d*', '', full_text).strip()
        else:
            value = full_text

        store_var = params.get("store_var", "")
        if store_var:
            ctx.safe_set_variable(_extract_var_name(store_var), value)

        store_number = params.get("store_number", "")
        if store_number and read_mode == "number":
            try:
                num_value = float(value) if value else 0.0
            except (ValueError, TypeError):
                num_value = 0.0
            ctx.safe_set_variable(_extract_var_name(store_number), num_value)

        ctx.check_results[f"{node.id}.text"] = value
        _execute_flow(node.id, "next", ctx)
    except Exception as e:
        print(f"[新引擎] 读取数字文本出错: {e}")
        ctx.check_results[f"{node.id}.text"] = ""
        ctx.log_error(f"读取数字文本出错: {e}", node_id=node.id, error_type="runtime")
        ctx.stop_event.set()


def register(handlers: dict):
    handlers["_handle_preset_click"] = _handle_preset_click
    handlers["_handle_preset_find_click"] = _handle_preset_find_click
    handlers["_handle_preset_read_text"] = _handle_preset_read_text
    handlers["_handle_preset_sub_script"] = _handle_preset_sub_script


class SubScriptVariableProxy:
    def __init__(self, parent_ctx: ExecContext):
        self._parent_ctx = parent_ctx
        self._local = {}

    def _prefixed(self, key):
        return f"sub.{key}"

    def __getitem__(self, key):
        prefixed = self._prefixed(key)
        val = self._parent_ctx.safe_get_variable(prefixed)
        if val is not None:
            return val
        if key in self._local:
            return self._local[key]
        val = self._parent_ctx.safe_get_variable(key)
        if val is not None:
            return val
        raise KeyError(key)

    def __setitem__(self, key, value):
        prefixed = self._prefixed(key)
        self._parent_ctx.safe_set_variable(prefixed, value)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        prefixed = self._prefixed(key)
        if self._parent_ctx.safe_get_variable(prefixed) is not None:
            return True
        if key in self._local:
            return True
        return self._parent_ctx.safe_get_variable(key) is not None

    def __iter__(self):
        seen = set()
        for k in self._local:
            if k not in seen:
                seen.add(k)
                yield k
        with self._parent_ctx._data_lock:
            for k in self._parent_ctx.variables:
                if k.startswith("sub."):
                    short = k[4:]
                    if short not in seen:
                        seen.add(short)
                        yield short

    def __len__(self):
        return len(list(self.__iter__()))

    def keys(self):
        return self.__iter__()

    def items(self):
        for k in self.keys():
            yield k, self[k]

    def values(self):
        for k in self.keys():
            yield self[k]


_MAX_NESTING_DEPTH = 10


def _handle_preset_sub_script(node: ExecNode, ctx: ExecContext):
    params = node.params
    script_path = _resolve_value(params.get("script_path", ""), ctx)

    if not script_path:
        ctx.log_error("执行子脚本: 脚本路径为空", node_id=node.id, error_type="param")
        _execute_flow(node.id, "fail", ctx)
        return

    if not os.path.exists(script_path):
        ctx.log_error(f"执行子脚本: 脚本文件不存在: {script_path}", node_id=node.id, error_type="param")
        _execute_flow(node.id, "fail", ctx)
        return

    current_depth = getattr(ctx, '_nesting_depth', 0)
    if current_depth >= _MAX_NESTING_DEPTH:
        ctx.log_error(
            f"执行子脚本: 嵌套深度已达上限({_MAX_NESTING_DEPTH}层)，拒绝执行: {script_path}",
            node_id=node.id, error_type="system"
        )
        _execute_flow(node.id, "fail", ctx)
        return

    try:
        with open(script_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except Exception as e:
        ctx.log_error(f"执行子脚本: 读取脚本文件失败: {e}", node_id=node.id, error_type="system")
        _execute_flow(node.id, "fail", ctx)
        return

    try:
        from automation.compiler import parse_graph
        sub_graph = parse_graph(json_data)
    except Exception as e:
        ctx.log_error(f"执行子脚本: 解析脚本失败: {e}", node_id=node.id, error_type="system")
        _execute_flow(node.id, "fail", ctx)
        return

    if sub_graph.errors:
        err_msgs = "; ".join(sub_graph.errors)
        ctx.log_error(f"执行子脚本: 子脚本存在编译错误: {err_msgs}", node_id=node.id, error_type="system")
        _execute_flow(node.id, "fail", ctx)
        return

    if not sub_graph.entry_node_id:
        ctx.log_error("执行子脚本: 子脚本缺少开始节点", node_id=node.id, error_type="system")
        _execute_flow(node.id, "fail", ctx)
        return

    sub_stop_event = threading.Event()
    sub_ctx = ExecContext(sub_graph, sub_stop_event)

    sub_ctx.variables = SubScriptVariableProxy(ctx)
    sub_ctx._nesting_depth = current_depth + 1
    sub_ctx._pause_reasons = set()
    sub_ctx._node_id = node.id

    sub_ctx.node_retry_count = ctx.node_retry_count
    sub_ctx.node_retry_delay_ms = ctx.node_retry_delay_ms

    if ctx.interception_session:
        sub_ctx.interception_session = ctx.interception_session

    ctx._sub_script_contexts[node.id] = sub_ctx

    from automation.engine import _predefine_const_nodes, _execute_node
    _predefine_const_nodes(sub_graph, sub_ctx)

    def _propagate_parent_stop():
        while not ctx.stop_event.is_set():
            if sub_stop_event.wait(timeout=0.05):
                return
        sub_stop_event.set()

    def _propagate_parent_pause():
        while not sub_stop_event.is_set():
            if ctx.pause_event.is_set():
                sub_ctx._pause_reasons.add("parent")
            else:
                sub_ctx._pause_reasons.discard("parent")
            if sub_ctx._pause_reasons:
                sub_ctx.pause_event.set()
            else:
                sub_ctx.pause_event.clear()
            if sub_stop_event.wait(timeout=0.05):
                return

    stop_propagator = threading.Thread(target=_propagate_parent_stop, daemon=True)
    stop_propagator.start()
    pause_propagator = threading.Thread(target=_propagate_parent_pause, daemon=True)
    pause_propagator.start()

    try:
        _execute_node(sub_graph.entry_node_id, sub_ctx)
    except Exception as e:
        ctx.log_error(
            f"执行子脚本: 子脚本执行异常: {e}",
            node_id=node.id, error_type="runtime"
        )
        _execute_flow(node.id, "fail", ctx)
        return
    finally:
        ctx._sub_script_contexts.pop(node.id, None)
        sub_stop_event.set()
        sub_ctx.task_pool.stop_all()
        for bid, bctx in sub_ctx._branches.items():
            bctx.stop_event.set()
            if bctx.thread and bctx.thread.is_alive():
                bctx.thread.join(timeout=2.0)

    if sub_ctx._reached_end:
        _execute_flow(node.id, "next", ctx)
    else:
        sub_errors = sub_ctx.get_errors()
        runtime_errors = [e for e in sub_errors if e.get("type") in ("runtime", "business", "system")]
        if runtime_errors:
            last_err = runtime_errors[-1]
            ctx.log_error(
                f"执行子脚本: 子脚本异常终止 - {last_err.get('message', '未知错误')}",
                node_id=node.id, error_type="runtime"
            )
        else:
            ctx.log_error(
                "执行子脚本: 子脚本异常终止(未到达结束节点)",
                node_id=node.id, error_type="runtime"
            )
        _execute_flow(node.id, "fail", ctx)
