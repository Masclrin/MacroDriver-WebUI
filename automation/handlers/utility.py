from automation.engine import _resolve_value, _execute_flow
from automation.compiler import ExecNode
from automation.engine import ExecContext

from engine.precision import precise_sleep_v5 as precise_sleep


def _read_data_input(node, ctx, port_name, fallback=None):
    data_sources = node.get_data_inputs(port_name)
    if data_sources:
        src = data_sources[0]
        key = f"{src['source_node_id']}.{src['source_port']}"
        return ctx.check_results.get(key, fallback)
    return fallback


def _handle_const_number(node: ExecNode, ctx: ExecContext):
    value = node.params.get("value", 0)
    ctx.check_results[f"{node.id}.value"] = value
    ctx.variables[node.id + "_out"] = value


def _handle_const_string(node: ExecNode, ctx: ExecContext):
    value = node.params.get("value", "")
    ctx.check_results[f"{node.id}.value"] = value
    ctx.variables[node.id + "_out"] = value


def _handle_const_bool(node: ExecNode, ctx: ExecContext):
    value = bool(node.params.get("value", True))
    ctx.check_results[f"{node.id}.value"] = value
    ctx.variables[node.id + "_out"] = value


def _handle_math_op(node: ExecNode, ctx: ExecContext):
    import math
    a_val = _read_data_input(node, ctx, "A")
    b_val = _read_data_input(node, ctx, "B")
    a = float(a_val if a_val is not None else _resolve_value(node.params.get("a", 0), ctx))
    b = float(b_val if b_val is not None else _resolve_value(node.params.get("b", 0), ctx))
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
    result = ops.get(op, lambda: 0)()
    ctx.check_results[f"{node.id}.result"] = result
    ctx.variables[node.id + "_out"] = result


def _handle_math_func(node: ExecNode, ctx: ExecContext):
    import math
    x_val = _read_data_input(node, ctx, "x")
    x = float(x_val if x_val is not None else _resolve_value(node.params.get("x", 0), ctx))
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
    result = funcs.get(func, lambda: 0)()
    ctx.check_results[f"{node.id}.result"] = result
    ctx.variables[node.id + "_out"] = result


def _handle_logic_op(node: ExecNode, ctx: ExecContext):
    a_val = _read_data_input(node, ctx, "A")
    b_val = _read_data_input(node, ctx, "B")
    a = bool(a_val if a_val is not None else _resolve_value(node.params.get("a", True), ctx))
    b = bool(b_val if b_val is not None else _resolve_value(node.params.get("b", True), ctx))
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
    ctx.variables[node.id + "_out"] = result


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
    ctx.variables[node.id + "_out"] = result


def _handle_string_op(node: ExecNode, ctx: ExecContext):
    s_val = _read_data_input(node, ctx, "str")
    s = str(s_val if s_val is not None else _resolve_value(node.params.get("input_str", ""), ctx))
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
    ctx.check_results[f"{node.id}.result"] = result
    ctx.variables[node.id + "_out"] = result


def _handle_condition(node: ExecNode, ctx: ExecContext):
    cond_val = _read_data_input(node, ctx, "cond")
    true_val = _read_data_input(node, ctx, "if_true")
    false_val = _read_data_input(node, ctx, "if_false")

    if cond_val is not None:
        cond = bool(cond_val)
    else:
        cond_var = node.params.get("cond_var", "")
        if cond_var:
            cond = bool(ctx.variables.get(cond_var, False))
        else:
            cond = False

    if cond:
        result = _resolve_value(true_val if true_val is not None else node.params.get("true_val", ""), ctx)
    else:
        result = _resolve_value(false_val if false_val is not None else node.params.get("false_val", ""), ctx)
    ctx.check_results[f"{node.id}.result"] = result
    ctx.variables[node.id + "_out"] = result


def _handle_bookmark(node: ExecNode, ctx: ExecContext):
    x = float(node.params.get("x", 0))
    y = float(node.params.get("y", 0))
    w = float(node.params.get("w", 0))
    h = float(node.params.get("h", 0))
    ctx.check_results[f"{node.id}.x"] = x
    ctx.check_results[f"{node.id}.y"] = y
    ctx.check_results[f"{node.id}.w"] = w
    ctx.check_results[f"{node.id}.h"] = h


def _handle_utility_delay(node: ExecNode, ctx: ExecContext):
    ms = float(node.params.get("ms", 1000))
    precise_sleep(ms / 1000.0, ctx.stop_event)
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
