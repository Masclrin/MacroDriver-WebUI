from automation.engine import _resolve_value, _execute_flow, _get_hwnd
from automation.compiler import ExecNode
from automation.engine import ExecContext
from automation.handlers.variable import _extract_var_name
from automation.registry import PluginRegistry

from engine.precision import precise_sleep_v5 as precise_sleep
from engine.coordinate import resolve_coords, resolve_region


def _safe_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.lower() not in ("", "0", "false", "no", "off", "none", "null")
    return bool(val)


def _read_data_input(node, ctx, port_name, fallback=None):
    data_sources = node.get_data_inputs(port_name)
    if data_sources:
        src = data_sources[0]
        key = f"{src['source_node_id']}.{src['source_port']}"
        return ctx.check_results.get(key, fallback)
    return fallback


def _get_out_var_name(node):
    node_def = PluginRegistry.get_node(node.type)
    if node_def and isinstance(node_def, dict):
        display_name = node_def.get("display_name", "")
        if display_name:
            return display_name + "_out"
    return node.id + "_out"


def _handle_const_number(node: ExecNode, ctx: ExecContext):
    value = _resolve_value(node.params.get("value", 0), ctx)
    try:
        value = float(value)
        if value == int(value):
            value = int(value)
    except (ValueError, TypeError):
        value = 0
    ctx.check_results[f"{node.id}.value"] = value
    ctx.safe_set_variable(_get_out_var_name(node), value)


def _handle_const_string(node: ExecNode, ctx: ExecContext):
    value = str(_resolve_value(node.params.get("value", ""), ctx))
    ctx.check_results[f"{node.id}.value"] = value
    ctx.safe_set_variable(_get_out_var_name(node), value)


def _handle_const_bool(node: ExecNode, ctx: ExecContext):
    value = _safe_bool(node.params.get("value", True))
    ctx.check_results[f"{node.id}.value"] = value
    ctx.safe_set_variable(_get_out_var_name(node), value)


def _handle_math_op(node: ExecNode, ctx: ExecContext):
    import math
    a_val = _read_data_input(node, ctx, "A")
    b_val = _read_data_input(node, ctx, "B")
    try:
        a = float(a_val if a_val is not None else _resolve_value(node.params.get("a", 0), ctx))
    except (ValueError, TypeError):
        ctx.log_error(f"数学运算 - 参数a非法输入: {a_val}", node_id=node.id, error_type="math")
        a = 0
    try:
        b = float(b_val if b_val is not None else _resolve_value(node.params.get("b", 0), ctx))
    except (ValueError, TypeError):
        ctx.log_error(f"数学运算 - 参数b非法输入: {b_val}", node_id=node.id, error_type="math")
        b = 0
    op = node.params.get("op", "+")
    _OP_ALIASES = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%", "pow": "^"}
    op = _OP_ALIASES.get(op, op)
    ops = {
        "+": lambda: a + b,
        "-": lambda: a - b,
        "*": lambda: a * b,
        "/": lambda: a / b if b != 0 else 0,
        "%": lambda: a % b if b != 0 else 0,
        "^": lambda: a ** b,
        "min": lambda: min(a, b),
        "max": lambda: max(a, b),
    }
    result = ops.get(op, lambda: 0)()
    ctx.check_results[f"{node.id}.result"] = result
    ctx.safe_set_variable(_get_out_var_name(node), result)


def _handle_math_func(node: ExecNode, ctx: ExecContext):
    import math
    x_val = _read_data_input(node, ctx, "x")
    try:
        x = float(x_val if x_val is not None else _resolve_value(node.params.get("x", 0), ctx))
    except (ValueError, TypeError):
        ctx.log_error(f"数学函数 - 参数x非法输入: {x_val}", node_id=node.id, error_type="math")
        x = 0
    func = node.params.get("func", "abs")
    funcs = {
        "abs": lambda: abs(x),
        "round": lambda: round(x, int(_resolve_value(node.params.get("digits", 0), ctx))),
        "floor": lambda: math.floor(x),
        "ceil": lambda: math.ceil(x),
        "sqrt": lambda: math.sqrt(x) if x >= 0 else 0,
        "sin": lambda: math.sin(x),
        "cos": lambda: math.cos(x),
        "log": lambda: math.log(x) if x > 0 else 0,
        "negate": lambda: -x,
    }
    result = funcs.get(func, lambda: 0)()
    ctx.check_results[f"{node.id}.result"] = result
    ctx.safe_set_variable(_get_out_var_name(node), result)


def _handle_logic_op(node: ExecNode, ctx: ExecContext):
    a_val = _read_data_input(node, ctx, "A")
    b_val = _read_data_input(node, ctx, "B")
    a = _safe_bool(a_val if a_val is not None else _resolve_value(node.params.get("a", True), ctx))
    b = _safe_bool(b_val if b_val is not None else _resolve_value(node.params.get("b", True), ctx))
    op = node.params.get("op", "and")
    ops = {
        "and": lambda: a and b,
        "or": lambda: a or b,
        "xor": lambda: a != b,
        "not": lambda: not a,
        "nand": lambda: not (a and b),
        "nor": lambda: not (a or b),
    }
    result = ops.get(op, lambda: False)()
    ctx.check_results[f"{node.id}.result"] = result
    ctx.safe_set_variable(_get_out_var_name(node), result)


def _handle_compare(node: ExecNode, ctx: ExecContext):
    a_val = _read_data_input(node, ctx, "A")
    b_val = _read_data_input(node, ctx, "B")
    a = float(a_val if a_val is not None else _resolve_value(node.params.get("a", 0), ctx))
    b = float(b_val if b_val is not None else _resolve_value(node.params.get("b", 0), ctx))
    op = node.params.get("op", "gt")
    ops = {
        "eq": lambda: a == b,
        "ne": lambda: a != b,
        "gt": lambda: a > b,
        "lt": lambda: a < b,
        "ge": lambda: a >= b,
        "le": lambda: a <= b,
    }
    result = ops.get(op, lambda: False)()
    ctx.check_results[f"{node.id}.result"] = result
    ctx.safe_set_variable(_get_out_var_name(node), result)


def _handle_string_op(node: ExecNode, ctx: ExecContext):
    s_val = _read_data_input(node, ctx, "str")
    s = str(s_val if s_val is not None else _resolve_value(node.params.get("input_str", ""), ctx))
    op = node.params.get("op", "concat")

    concat_str = str(_resolve_value(node.params.get("concat_str", node.params.get("param_a", "")), ctx))
    search_str = str(_resolve_value(node.params.get("search_str", node.params.get("param_a", "")), ctx))
    replace_str = str(_resolve_value(node.params.get("replace_str", node.params.get("param_b", "")), ctx))
    start_pos = int(_resolve_value(node.params.get("start_pos", node.params.get("param_b", 0)), ctx))
    length = int(_resolve_value(node.params.get("length", node.params.get("param_c", 0)), ctx))
    delimiter = str(_resolve_value(node.params.get("delimiter", node.params.get("param_a", ",")), ctx))
    index = int(_resolve_value(node.params.get("index", node.params.get("param_b", 0)), ctx))

    if op == "concat":
        result = s + concat_str
    elif op == "replace":
        result = s.replace(search_str, replace_str)
    elif op == "upper":
        result = s.upper()
    elif op == "lower":
        result = s.lower()
    elif op == "trim":
        result = s.strip()
    elif op == "substring":
        try:
            end = start_pos + length if length > 0 else len(s)
            result = s[start_pos:end]
        except (ValueError, IndexError):
            result = s
    elif op == "split_index":
        try:
            parts = s.split(delimiter) if delimiter else [s]
            result = parts[index] if 0 <= index < len(parts) else ""
        except (ValueError, IndexError):
            result = s
    elif op == "regex_extract":
        import re
        pattern = str(_resolve_value(node.params.get("pattern", ""), ctx))
        group = int(_resolve_value(node.params.get("group", 0), ctx))
        try:
            m = re.search(pattern, s)
            if m:
                if group <= len(m.groups()):
                    result = m.group(group)
                else:
                    ctx.log_warning(f"正则捕获组越界: 请求 group={group}，但只有 {len(m.groups())} 个捕获组", node_id=node.id)
                    result = ""
            else:
                result = ""
        except re.error as e:
            ctx.log_error(f"字符串操作 - 正则表达式语法错误: {e}", node_id=node.id, error_type="param")
            result = ""
        except IndexError:
            result = ""
    else:
        result = s
    ctx.check_results[f"{node.id}.result"] = result
    ctx.safe_set_variable(_get_out_var_name(node), result)


def _handle_condition(node: ExecNode, ctx: ExecContext):
    cond_val = _read_data_input(node, ctx, "cond")
    true_val = _read_data_input(node, ctx, "if_true")
    false_val = _read_data_input(node, ctx, "if_false")

    if cond_val is not None:
        cond = _safe_bool(cond_val)
    else:
        cond_var = _resolve_value(node.params.get("cond_var", ""), ctx)
        if cond_var:
            cond = _safe_bool(cond_var)
        else:
            cond = False

    if cond:
        result = _resolve_value(true_val if true_val is not None else node.params.get("true_val", ""), ctx)
    else:
        result = _resolve_value(false_val if false_val is not None else node.params.get("false_val", ""), ctx)
    ctx.check_results[f"{node.id}.result"] = result
    ctx.safe_set_variable(_get_out_var_name(node), result)


def _handle_bookmark(node: ExecNode, ctx: ExecContext):
    mode = node.params.get("mode", "screen")
    x = float(_resolve_value(node.params.get("x", 0), ctx))
    y = float(_resolve_value(node.params.get("y", 0), ctx))
    w = float(_resolve_value(node.params.get("w", 0), ctx))
    h = float(_resolve_value(node.params.get("h", 0), ctx))
    hwnd = None
    if mode in ("window", "relative"):
        hwnd = _get_hwnd(node.params.get("hwnd_var", ""), ctx)
    if mode == "screen":
        ctx.check_results[f"{node.id}.x"] = x
        ctx.check_results[f"{node.id}.y"] = y
        ctx.check_results[f"{node.id}.w"] = w
        ctx.check_results[f"{node.id}.h"] = h
    else:
        rx, ry = resolve_coords(mode, x, y, hwnd)
        rw_rh = resolve_region(mode, (0, 0, w, h), hwnd)
        ctx.check_results[f"{node.id}.x"] = rx
        ctx.check_results[f"{node.id}.y"] = ry
        ctx.check_results[f"{node.id}.w"] = rw_rh[2]
        ctx.check_results[f"{node.id}.h"] = rw_rh[3]


def _handle_utility_delay(node: ExecNode, ctx: ExecContext):
    ms = float(_resolve_value(node.params.get("ms", 1000), ctx))
    branch_ctx = ctx._get_current_branch_ctx()
    pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event
    precise_sleep(ms / 1000.0, ctx.stop_event, pause_event=pause_event)
    _execute_flow(node.id, "next", ctx)


def register(handlers: dict):
    handlers["_handle_const_number"] = _handle_const_number
    handlers["_handle_const_string"] = _handle_const_string
    handlers["_handle_const_bool"] = _handle_const_bool
    handlers["_handle_math_op"] = _handle_math_op
    handlers["_handle_math_func"] = _handle_math_func
    handlers["_handle_logic_op"] = _handle_logic_op
    handlers["_handle_compare"] = _handle_compare
    handlers["_handle_string_op"] = _handle_string_op
    handlers["_handle_condition"] = _handle_condition
    handlers["_handle_bookmark"] = _handle_bookmark
    handlers["_handle_utility_delay"] = _handle_utility_delay
