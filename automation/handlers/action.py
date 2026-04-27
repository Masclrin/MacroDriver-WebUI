from automation.engine import (
    _resolve_value, _get_hwnd, _execute_flow, _send_key, _send_click,
    _do_click, _interpolated_move, _get_cursor_pos,
)
from automation.compiler import ExecNode
from automation.engine import ExecContext

from engine.precision import precise_sleep_v5 as precise_sleep
from engine.input_sendinput import get_vk, set_cursor_pos, send_click_sendinput, send_scroll_sendinput


def _handle_mouse_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    x = _resolve_value(params.get("x", 0), ctx)
    y = _resolve_value(params.get("y", 0), ctx)
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

    from engine.coordinate import resolve_coords
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
            from engine.input_sendinput import send_unicode_char
            send_unicode_char(ch)
        if interval > 0:
            precise_sleep(interval / 1000.0, ctx.stop_event)

    _execute_flow(node.id, "next", ctx)


def _handle_wait(node: ExecNode, ctx: ExecContext):
    duration = float(_resolve_value(node.params.get("duration", 1000), ctx))
    precise_sleep(duration / 1000.0, ctx.stop_event)
    _execute_flow(node.id, "next", ctx)


def _handle_mouse_move(node: ExecNode, ctx: ExecContext):
    params = node.params
    x = _resolve_value(params.get("x", 0), ctx)
    y = _resolve_value(params.get("y", 0), ctx)
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

    from engine.coordinate import resolve_coords
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


def register(handlers: dict):
    handlers["_handle_mouse_click"] = _handle_mouse_click
    handlers["_handle_key_action"] = _handle_key_action
    handlers["_handle_mouse_scroll"] = _handle_mouse_scroll
    handlers["_handle_text_input"] = _handle_text_input
    handlers["_handle_wait"] = _handle_wait
    handlers["_handle_mouse_move"] = _handle_mouse_move
    handlers["_handle_mouse_move_rel"] = _handle_mouse_move_rel
