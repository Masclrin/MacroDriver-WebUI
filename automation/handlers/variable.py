from automation.engine import _resolve_value, _execute_flow, ExecContext
from automation.compiler import ExecNode


def _extract_var_name(val):
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        return val[2:-1]
    return val


def _read_data_input(node, ctx, port_name, fallback=None):
    data_sources = node.get_data_inputs(port_name)
    if data_sources:
        src = data_sources[0]
        key = f"{src['source_node_id']}.{src['source_port']}"
        return ctx.check_results.get(key, fallback)
    return fallback


def _log_div_zero(ctx, node, a, b):
    ctx.log_error(f"除零错误: {a} / {b} (除数b=0) 位于节点 {node.type}", node_id=node.id, error_type="math")
    return 0


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
            if isinstance(raw_value, str):
                value = _resolve_value(raw_value, ctx)
            else:
                value = raw_value
            var_type = var_item.get("type", "string")
            if var_type == "number":
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = 0.0
            elif var_type == "boolean":
                if isinstance(value, bool):
                    pass
                elif isinstance(value, str):
                    value = value.lower() not in ("", "0", "false", "no", "off", "none", "null")
                else:
                    value = bool(value)
            ctx.safe_set_variable(name, value)
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
            if isinstance(value, bool):
                pass
            elif isinstance(value, str):
                value = value.lower() not in ("", "0", "false", "no", "off", "none", "null")
            else:
                value = bool(value)
        if name:
            ctx.safe_set_variable(name, value)
    _execute_flow(node.id, "next", ctx)


def _handle_var_math(node: ExecNode, ctx: ExecContext):
    op = node.params.get("op", "+")
    _MATH_OP_ALIASES = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%"}
    op = _MATH_OP_ALIASES.get(op, op)

    a_input = _read_data_input(node, ctx, "A")
    b_input = _read_data_input(node, ctx, "B")
    a = float(a_input if a_input is not None else _resolve_value(node.params.get("a", "0"), ctx))
    b = float(b_input if b_input is not None else _resolve_value(node.params.get("b", "0"), ctx))
    store_var = node.params.get("store_var", "")

    ops = {
        "+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b,
        "/": lambda: a / b if b != 0 else _log_div_zero(ctx, node, a, b),
        "%": lambda: a % b if b != 0 else _log_div_zero(ctx, node, a, b),
        "^": lambda: a ** b,
        "min": lambda: min(a, b), "max": lambda: max(a, b),
        "abs": lambda: abs(a), "round": lambda: round(a, int(b)),
    }
    result = ops.get(op, lambda: 0)()

    ctx.check_results[f"{node.id}.result"] = result
    if store_var:
        ctx.safe_set_variable(_extract_var_name(store_var), result)
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
    store_var = node.params.get("store_var", "")

    concat_str = str(_resolve_value(node.params.get("concat_str", node.params.get("b", "")), ctx))
    search_str = str(_resolve_value(node.params.get("search_str", node.params.get("b", "")), ctx))
    replace_str = str(_resolve_value(node.params.get("replace_str", node.params.get("c", "")), ctx))
    start_pos = int(_resolve_value(node.params.get("start_pos", 0), ctx))
    length = int(_resolve_value(node.params.get("length", 0), ctx))
    delimiter = str(_resolve_value(node.params.get("delimiter", node.params.get("b", ",")), ctx))
    index = int(_resolve_value(node.params.get("index", node.params.get("c", 0)), ctx))
    regex_pattern = str(_resolve_value(node.params.get("regex_pattern", node.params.get("b", "")), ctx))

    if op == "concat":
        result = a + concat_str
    elif op == "substring":
        try:
            end = start_pos + length if length > 0 else len(a)
            result = a[start_pos:end]
        except (ValueError, IndexError):
            result = a
    elif op == "replace":
        result = a.replace(search_str, replace_str)
    elif op == "split_index":
        parts = a.split(delimiter) if delimiter else [a]
        try:
            result = parts[index] if 0 <= index < len(parts) else (parts[0] if parts else "")
        except (ValueError, IndexError):
            result = a
    elif op == "regex_extract":
        import re
        match = re.search(regex_pattern, a)
        result = match.group(0) if match else ""
    elif op == "upper":
        result = a.upper()
    elif op == "lower":
        result = a.lower()
    elif op == "trim":
        result = a.strip()
    else:
        result = a

    if store_var:
        ctx.safe_set_variable(_extract_var_name(store_var), result)
    ctx.check_results[f"{node.id}.result"] = result
    _execute_flow(node.id, "next", ctx)


def _handle_var_convert(node: ExecNode, ctx: ExecContext):
    to_type = node.params.get("to_type", "number")
    input_var = _resolve_value(node.params.get("input_var", ""), ctx)
    store_var = node.params.get("store_var", "")

    val_input = _read_data_input(node, ctx, "val")
    if val_input is not None:
        value = val_input
    elif input_var:
        value = input_var
    else:
        value = ""

    if to_type == "number":
        try:
            result = float(value)
        except (ValueError, TypeError):
            try:
                result = float(str(value).strip())
            except (ValueError, TypeError):
                result = 0.0
    elif to_type == "string":
        result = str(value)
    elif to_type == "boolean":
        if isinstance(value, bool):
            result = value
        elif isinstance(value, (int, float)):
            result = value != 0
        elif isinstance(value, str):
            result = value.lower() not in ("", "0", "false", "no", "off", "none", "null")
        else:
            result = bool(value)
    else:
        result = value

    if store_var:
        ctx.safe_set_variable(_extract_var_name(store_var), result)
    ctx.check_results[f"{node.id}.result"] = result
    _execute_flow(node.id, "next", ctx)


def _handle_var_random(node: ExecNode, ctx: ExecContext):
    import random
    import string as _string_lib

    params = node.params
    mode = params.get("mode", "number")
    store_var = params.get("store_var", "")

    if mode == "number":
        min_val = float(_resolve_value(params.get("min_val", 1), ctx))
        max_val = float(_resolve_value(params.get("max_val", 100), ctx))
        int_only = params.get("int_only", True)
        if int_only:
            result = random.randint(int(min_val), int(max_val))
        else:
            result = random.uniform(min_val, max_val)
    else:
        charset = params.get("charset", "alpha")
        custom_chars = _resolve_value(params.get("custom_chars", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"), ctx)
        length = int(_resolve_value(params.get("length", 8), ctx))

        charset_map = {
            "alpha": _string_lib.ascii_letters,
            "alphanumeric": _string_lib.ascii_letters + _string_lib.digits,
            "numeric": _string_lib.digits,
        }
        if charset == "custom" and custom_chars:
            chars = custom_chars
        else:
            chars = charset_map.get(charset, _string_lib.ascii_letters)
        result = "".join(random.choices(chars, k=max(1, length)))

    ctx.check_results[f"{node.id}.result"] = result
    if store_var:
        ctx.safe_set_variable(_extract_var_name(store_var), result)
    _execute_flow(node.id, "next", ctx)


def register(handlers: dict):
    handlers["_handle_var_set"] = _handle_var_set
    handlers["_handle_var_math"] = _handle_var_math
    handlers["_handle_var_compare"] = _handle_var_compare
    handlers["_handle_var_string"] = _handle_var_string
    handlers["_handle_var_convert"] = _handle_var_convert
    handlers["_handle_var_random"] = _handle_var_random
