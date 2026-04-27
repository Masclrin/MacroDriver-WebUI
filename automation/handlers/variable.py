from automation.engine import _resolve_value, _execute_flow, ExecContext
from automation.compiler import ExecNode


def _read_data_input(node, ctx, port_name, fallback=None):
    data_sources = node.get_data_inputs(port_name)
    if data_sources:
        src = data_sources[0]
        key = f"{src['source_node_id']}.{src['source_port']}"
        return ctx.check_results.get(key, fallback)
    return fallback


def _handle_var_set(node: ExecNode, ctx: ExecContext):
    import json
    vars_json = node.params.get("vars_json", "[]")
    multi_mode = False
    try:
        vars_list = json.loads(vars_json) if vars_json else []
        if isinstance(vars_list, list) and len(vars_list) > 0:
            multi_mode = True
    except (json.JSONDecodeError, TypeError):
        vars_list = []

    if multi_mode:
        for var_item in vars_list:
            if not isinstance(var_item, dict):
                continue
            name = var_item.get("name", "")
            if not name:
                continue
            raw_value = var_item.get("value", "")
            value = _resolve_value(str(raw_value), ctx)
            var_type = var_item.get("type", "string")
            if var_type == "number":
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = 0.0
            elif var_type == "boolean":
                value = bool(value)
            ctx.variables[name] = value
    else:
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

    a_input = _read_data_input(node, ctx, "A")
    b_input = _read_data_input(node, ctx, "B")
    a = float(a_input if a_input is not None else _resolve_value(node.params.get("a", "0"), ctx))
    b = float(b_input if b_input is not None else _resolve_value(node.params.get("b", "0"), ctx))
    store_var = node.params.get("store_var", "")

    ops = {
        "add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b,
        "div": lambda: a / b if b != 0 else 0, "mod": lambda: a % b if b != 0 else 0,
        "min": lambda: min(a, b), "max": lambda: max(a, b),
        "abs": lambda: abs(a), "round": lambda: round(a, int(b)),
    }
    result = ops.get(op, lambda: 0)()

    ctx.check_results[f"{node.id}.result"] = result
    if store_var:
        ctx.variables[store_var] = result
    _execute_flow(node.id, "next", ctx)


def _handle_var_compare(node: ExecNode, ctx: ExecContext):
    op = node.params.get("op", "gt")
    _COMPARE_OP_ALIASES = {">": "gt", "<": "lt", ">=": "ge", "<=": "le", "==": "eq", "!=": "ne"}
    op = _COMPARE_OP_ALIASES.get(op, op)

    a_input = _read_data_input(node, ctx, "A")
    b_input = _read_data_input(node, ctx, "B")
    a = _resolve_value(a_input if a_input is not None else node.params.get("a", "0"), ctx)
    b = _resolve_value(b_input if b_input is not None else node.params.get("b", "0"), ctx)

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

    str_input = _read_data_input(node, ctx, "str")
    a = str(str_input if str_input is not None else _resolve_value(node.params.get("a", ""), ctx))
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
    ctx.check_results[f"{node.id}.result"] = result
    _execute_flow(node.id, "next", ctx)


def _handle_var_convert(node: ExecNode, ctx: ExecContext):
    to_type = node.params.get("to_type", "number")
    input_var = node.params.get("input_var", "")
    store_var = node.params.get("store_var", "")

    val_input = _read_data_input(node, ctx, "val")
    if val_input is not None:
        value = val_input
    elif input_var:
        value = ctx.variables.get(input_var, "")
    else:
        value = ""

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
    ctx.check_results[f"{node.id}.result"] = result
    _execute_flow(node.id, "next", ctx)


def register(handlers: dict):
    handlers["_handle_var_set"] = _handle_var_set
    handlers["_handle_var_math"] = _handle_var_math
    handlers["_handle_var_compare"] = _handle_var_compare
    handlers["_handle_var_string"] = _handle_var_string
    handlers["_handle_var_convert"] = _handle_var_convert
