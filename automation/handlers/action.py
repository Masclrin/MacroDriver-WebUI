import os
import re
import time
import ctypes
import datetime
import subprocess
import threading

from automation.engine import (
    _resolve_value, _execute_flow, _get_hwnd, _do_click, _interpolated_move,
    _send_click, _get_cursor_pos,
)
from automation.compiler import ExecNode
from automation.engine import ExecContext
from automation.handlers.variable import _extract_var_name

from engine.precision import precise_sleep_v5 as precise_sleep
from engine.input_sendinput import (
    get_vk, set_cursor_pos, send_key_sendinput, send_scroll_sendinput,
    send_unicode_char, release_all_modifiers,
)
from engine.coordinate import resolve_coords


def _get_easing_fn(easing):
    if easing == "linear":
        return lambda t: t
    elif easing == "ease_in":
        return lambda t: t * t
    elif easing == "ease_out":
        return lambda t: t * (2 - t)
    elif easing == "ease_in_out":
        return lambda t: 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t
    return lambda t: t


def _eased_move(phys_x, phys_y, duration_ms, stop_event, easing="ease_in_out", pause_event=None):
    if duration_ms <= 0:
        set_cursor_pos(phys_x, phys_y)
        return
    easing_fn = _get_easing_fn(easing)
    steps = max(1, min(int(duration_ms / 10), 100))
    step_delay = duration_ms / 1000.0 / steps
    cx, cy = _get_cursor_pos()
    for i in range(1, steps + 1):
        if stop_event.is_set():
            return
        t = easing_fn(i / steps)
        x = int(cx + (phys_x - cx) * t)
        y = int(cy + (phys_y - cy) * t)
        set_cursor_pos(x, y)
        if i < steps:
            precise_sleep(step_delay, stop_event, pause_event=pause_event)


def _send_key(vk, up, ctx):
    if ctx and ctx.interception_session:
        ctx.interception_session.send_key(vk, up)
    else:
        send_key_sendinput(vk, up)


def _handle_mouse_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        mode = params.get("mode", "screen")
        button = params.get("button", "left")
        click_type = params.get("click_type", "click")
        hold_time = float(_resolve_value(params.get("hold_time", 0), ctx))
        move_duration = float(_resolve_value(params.get("move_duration", 0), ctx))
        before_delay = float(_resolve_value(params.get("before_delay", 0), ctx))
        after_delay = float(_resolve_value(params.get("after_delay", 0), ctx))

        branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
        pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event

        if before_delay > 0:
            precise_sleep(before_delay / 1000.0, ctx.stop_event, pause_event=pause_event)

        if mode == "current":
            _do_click(button, click_type, hold_time, ctx.stop_event, ctx, pause_event=pause_event)
        else:
            x = float(_resolve_value(params.get("x", 0), ctx))
            y = float(_resolve_value(params.get("y", 0), ctx))
            hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
            phys_x, phys_y = resolve_coords(mode, x, y, hwnd)

            if move_duration > 0:
                _eased_move(phys_x, phys_y, move_duration, ctx.stop_event, pause_event=pause_event)
            else:
                set_cursor_pos(phys_x, phys_y)

            _do_click(button, click_type, hold_time, ctx.stop_event, ctx, pause_event=pause_event)

        if after_delay > 0:
            precise_sleep(after_delay / 1000.0, ctx.stop_event, pause_event=pause_event)

        store_hwnd_var = params.get("store_hwnd_var", "")
        if store_hwnd_var:
            if mode == "window" or mode == "relative":
                hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
                if hwnd:
                    ctx.safe_set_variable(_extract_var_name(store_hwnd_var), str(hwnd))
            elif mode == "screen":
                try:
                    import ctypes
                    fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
                    if fg_hwnd:
                        ctx.safe_set_variable(_extract_var_name(store_hwnd_var), str(fg_hwnd))
                    else:
                        print(f"[新引擎] store_hwnd_var: screen模式下无法获取前台窗口句柄")
                except Exception:
                    print(f"[新引擎] store_hwnd_var: screen模式下获取前台窗口句柄失败")
            elif mode == "current":
                try:
                    import ctypes
                    class POINT(ctypes.Structure):
                        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                    pt = POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    cur_hwnd = ctypes.windll.user32.WindowFromPoint(pt.x, pt.y)
                    if cur_hwnd:
                        ctx.safe_set_variable(_extract_var_name(store_hwnd_var), str(cur_hwnd))
                    else:
                        print(f"[新引擎] store_hwnd_var: current模式下无法获取鼠标位置窗口句柄")
                except Exception:
                    print(f"[新引擎] store_hwnd_var: current模式下获取窗口句柄失败")
    except Exception as e:
        print(f"[新引擎] 鼠标点击出错: {e}")
        ctx.log_error(f"鼠标点击出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _handle_key_action(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        action = params.get("action", "click")
        key_raw = str(_resolve_value(params.get("key", ""), ctx))
        delay = float(_resolve_value(params.get("delay", 0), ctx))

        branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
        pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event

        if not key_raw:
            _execute_flow(node.id, "next", ctx)
            return

        if action == "type":
            type_interval = float(_resolve_value(params.get("text_input_delay", 10), ctx)) / 1000.0
            for i, ch in enumerate(key_raw):
                if ctx.stop_event.is_set():
                    break
                if i > 0:
                    precise_sleep(type_interval, ctx.stop_event, pause_event=pause_event)
                send_unicode_char(ch)
            if delay > 0:
                precise_sleep(delay / 1000.0, ctx.stop_event, pause_event=pause_event)
            _execute_flow(node.id, "next", ctx)
            return

        vk = get_vk(key_raw)
        if vk == 0:
            if len(key_raw) == 1:
                vk = ord(key_raw.upper())
            else:
                print(f"[新引擎] 未知按键: {key_raw}")
                _execute_flow(node.id, "next", ctx)
                return

        if action == "click":
            _send_key(vk, False, ctx)
            _send_key(vk, True, ctx)
        elif action == "press":
            _send_key(vk, False, ctx)
        elif action == "release":
            _send_key(vk, True, ctx)

        if delay > 0:
            precise_sleep(delay / 1000.0, ctx.stop_event, pause_event=pause_event)
    except Exception as e:
        print(f"[新引擎] 按键动作出错: {e}")
        ctx.log_error(f"按键动作出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _handle_mouse_scroll(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        delta = float(_resolve_value(params.get("delta", 120), ctx))
        delay = float(_resolve_value(params.get("delay", 0), ctx))

        branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
        pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event

        send_scroll_sendinput(int(delta))

        if delay > 0:
            precise_sleep(delay / 1000.0, ctx.stop_event, pause_event=pause_event)
    except Exception as e:
        print(f"[新引擎] 鼠标滚轮出错: {e}")
        ctx.log_error(f"鼠标滚轮出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _handle_text_input(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        text = str(_resolve_value(params.get("text", ""), ctx))
        interval = float(_resolve_value(params.get("interval", 50), ctx))
        before_delay = float(_resolve_value(params.get("before_delay", 0), ctx))

        branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
        pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event

        if before_delay > 0:
            precise_sleep(before_delay / 1000.0, ctx.stop_event, pause_event=pause_event)

        for ch in text:
            if ctx.stop_event.is_set():
                break
            send_unicode_char(ch)
            if interval > 0:
                precise_sleep(interval / 1000.0, ctx.stop_event, pause_event=pause_event)
    except Exception as e:
        print(f"[新引擎] 文本输入出错: {e}")
        ctx.log_error(f"文本输入出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _handle_wait(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        mode = params.get("mode", "duration")

        if mode == "duration":
            duration = float(_resolve_value(params.get("duration", 0), ctx))
            unit = params.get("unit", "ms")
            if unit == "s":
                seconds = duration
            elif unit == "min":
                seconds = duration * 60
            else:
                seconds = duration / 1000.0
            if seconds > 0:
                branch_ctx_w = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
                pause_ev_w = branch_ctx_w.pause_event if branch_ctx_w else ctx.pause_event
                precise_sleep(seconds, ctx.stop_event, pause_event=pause_ev_w)
        elif mode == "until_time":
            target_hour = int(_resolve_value(params.get("hour", 8), ctx))
            target_minute = int(_resolve_value(params.get("minute", 0), ctx))
            target_second = int(_resolve_value(params.get("second", 0), ctx))
            next_day = params.get("next_day", False)

            now = datetime.datetime.now()
            target = now.replace(hour=target_hour, minute=target_minute,
                                 second=target_second, microsecond=0)
            if target <= now:
                if next_day:
                    target += datetime.timedelta(days=1)
                else:
                    _execute_flow(node.id, "next", ctx)
                    return

            branch_ctx_ut = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
            pause_ev_ut = branch_ctx_ut.pause_event if branch_ctx_ut else ctx.pause_event
            while not ctx.stop_event.is_set():
                if pause_ev_ut and pause_ev_ut.is_set():
                    pause_ev_ut.wait(timeout=0.1)
                    continue
                remaining = (target - datetime.datetime.now()).total_seconds()
                if remaining <= 0:
                    break
                sleep_time = min(remaining, 0.1)
                ctx.stop_event.wait(timeout=sleep_time)
    except Exception as e:
        print(f"[新引擎] 等待节点出错: {e}")
        ctx.log_error(f"等待节点出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _find_window_by_title(title):
    result_hwnd = []

    def enum_callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                if title.lower() in buf.value.lower():
                    result_hwnd.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return result_hwnd


def _handle_window_manage(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        find_mode = params.get("find_mode", "title")
        action = params.get("action", "activate")
        hwnd = None

        if find_mode == "title":
            title = str(_resolve_value(params.get("title", ""), ctx))
            if title:
                hwnds = _find_window_by_title(title)
                if hwnds:
                    hwnd = hwnds[0]
        elif find_mode == "hwnd":
            hwnd_val = str(_resolve_value(params.get("hwnd_value", ""), ctx))
            try:
                hwnd = int(hwnd_val)
            except (ValueError, TypeError):
                pass
        elif find_mode == "hwnd_var":
            hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)

        if hwnd is None:
            print(f"[新引擎] 窗口管理：未找到窗口 (find_mode={find_mode})")
            _execute_flow(node.id, "next", ctx)
            return

        if not ctypes.windll.user32.IsWindow(hwnd):
            print(f"[新引擎] 窗口句柄无效: {hwnd}")
            _execute_flow(node.id, "next", ctx)
            return

        store_hwnd_var = params.get("store_hwnd_var", "")
        if store_hwnd_var:
            ctx.safe_set_variable(_extract_var_name(store_hwnd_var), str(hwnd))

        SW_RESTORE = 9
        SW_MINIMIZE = 6
        SW_MAXIMIZE = 3
        SW_SHOW = 5

        if action == "activate":
            if ctypes.windll.user32.IsIconic(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        elif action == "maximize":
            ctypes.windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
        elif action == "minimize":
            ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
        elif action == "restore":
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
        elif action == "close":
            WM_CLOSE = 0x0010
            ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        elif action == "move_to_monitor":
            monitor_index = int(_resolve_value(params.get("monitor_index", 0), ctx))
            _move_window_to_monitor(hwnd, monitor_index)
    except Exception as e:
        print(f"[新引擎] 窗口管理出错: {e}")
        ctx.log_error(f"窗口管理出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _move_window_to_monitor(hwnd, monitor_index):
    monitors = []

    def monitor_enum_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        monitors.append(hMonitor)
        return True

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_long * 4), ctypes.c_long
    )
    ctypes.windll.user32.EnumDisplayMonitors(
        None, None, MONITORENUMPROC(monitor_enum_callback), 0
    )

    if monitor_index < 0 or monitor_index >= len(monitors):
        print(f"[新引擎] 显示器序号 {monitor_index} 超出范围 (共 {len(monitors)} 个)")
        return

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", ctypes.c_long * 4),
            ("rcWork", ctypes.c_long * 4),
            ("dwFlags", ctypes.c_ulong),
        ]

    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    ctypes.windll.user32.GetMonitorInfoW(monitors[monitor_index], ctypes.byref(mi))

    work = mi.rcWork
    target_x = work[0]
    target_y = work[1]
    work_w = work[2] - work[0]
    work_h = work[3] - work[1]

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                     ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    rect = RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    win_w = rect.right - rect.left
    win_h = rect.bottom - rect.top

    ctypes.windll.user32.SetWindowPos(
        hwnd, 0, target_x, target_y, win_w, win_h, 0x0004
    )


def _handle_program_open(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        path = str(_resolve_value(params.get("path", ""), ctx))
        args = str(_resolve_value(params.get("args", ""), ctx))
        work_dir = str(_resolve_value(params.get("work_dir", ""), ctx))
        wait_start = float(_resolve_value(params.get("wait_start", 0), ctx))
        store_hwnd_var = params.get("store_hwnd_var", "")

        if not path:
            print("[新引擎] 打开程序：路径为空")
            _execute_flow(node.id, "next", ctx)
            return

        if not os.path.exists(path):
            print(f"[新引擎] 打开程序：路径不存在: {path}")
            ctx.log_error(f"程序路径不存在: {path}", node_id=node.id, error_type="runtime")
            _execute_flow(node.id, "next", ctx)
            return

        cmd = f'"{path}"'
        if args:
            cmd += f" {args}"

        actual_work_dir = work_dir if work_dir else os.path.dirname(path)
        if not os.path.isdir(actual_work_dir):
            actual_work_dir = None

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 1

        proc = subprocess.Popen(
            cmd,
            cwd=actual_work_dir,
            startupinfo=startupinfo,
            shell=True,
        )

        if wait_start > 0:
            precise_sleep(wait_start / 1000.0, ctx.stop_event)

        if store_hwnd_var:
            max_retries = 10
            retry_interval = 0.2
            hwnd = None
            for attempt in range(max_retries):
                hwnd = _find_process_main_hwnd(proc.pid)
                if hwnd:
                    break
                if attempt < max_retries - 1:
                    precise_sleep(retry_interval, ctx.stop_event)
            if hwnd:
                ctx.safe_set_variable(_extract_var_name(store_hwnd_var), str(hwnd))
            else:
                print(f"[新引擎] 打开程序：未找到窗口句柄(进程PID={proc.pid}，已重试{max_retries}次)")
                ctx.log_error(f"未找到窗口句柄(进程PID={proc.pid})", node_id=node.id, error_type="runtime")
    except Exception as e:
        print(f"[新引擎] 打开程序出错: {e}")
        ctx.log_error(f"打开程序出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _find_process_main_hwnd(pid):
    result = []

    def enum_callback(hwnd, _):
        proc_id = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value == pid and ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                result.append(hwnd)
                return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return result[0] if result else None


def _handle_program_close(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        close_mode = params.get("close_mode", "name")
        force = params.get("force", False)

        if close_mode == "name":
            process_name = str(_resolve_value(params.get("process_name", ""), ctx))
            if process_name:
                _kill_by_name(process_name, force)
        elif close_mode == "pid":
            pid_val = str(_resolve_value(params.get("pid_value", ""), ctx))
            try:
                pid = int(pid_val)
                _kill_by_pid(pid, force)
            except (ValueError, TypeError):
                print(f"[新引擎] 无效的PID: {pid_val}")
        elif close_mode == "hwnd":
            hwnd_val = str(_resolve_value(params.get("hwnd_value", ""), ctx))
            try:
                hwnd = int(hwnd_val)
                _close_by_hwnd(hwnd)
            except (ValueError, TypeError):
                print(f"[新引擎] 无效的窗口句柄: {hwnd_val}")
        elif close_mode == "hwnd_var":
            hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
            if hwnd:
                _close_by_hwnd(hwnd)
            else:
                print("[新引擎] 窗口变量未找到有效句柄")
    except Exception as e:
        print(f"[新引擎] 关闭程序出错: {e}")
        ctx.log_error(f"关闭程序出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _kill_by_name(process_name, force=False):
    import psutil
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                if force:
                    proc.kill()
                else:
                    proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def _kill_by_pid(pid, force=False):
    import psutil
    try:
        proc = psutil.Process(pid)
        if force:
            proc.kill()
        else:
            proc.terminate()
    except psutil.NoSuchProcess:
        print(f"[新引擎] 进程不存在: PID {pid}")
    except psutil.AccessDenied:
        print(f"[新引擎] 无权限终止进程: PID {pid}")


def _close_by_hwnd(hwnd):
    if ctypes.windll.user32.IsWindow(hwnd):
        WM_CLOSE = 0x0010
        ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    else:
        print(f"[新引擎] 窗口句柄无效: {hwnd}")


def _handle_mouse_move(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        mode = params.get("mode", "screen")
        x = float(_resolve_value(params.get("x", 0), ctx))
        y = float(_resolve_value(params.get("y", 0), ctx))
        hwnd = _get_hwnd(params.get("hwnd_var", ""), ctx)
        phys_x, phys_y = resolve_coords(mode, x, y, hwnd)

        duration = float(_resolve_value(params.get("duration", 200), ctx))
        easing = params.get("easing", "ease_in_out")

        branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
        pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event

        _eased_move(phys_x, phys_y, duration, ctx.stop_event, easing, pause_event=pause_event)
    except Exception as e:
        print(f"[新引擎] 鼠标移动出错: {e}")
        ctx.log_error(f"鼠标移动出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _handle_mouse_move_rel(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        dx = float(_resolve_value(params.get("dx", 0), ctx))
        dy = float(_resolve_value(params.get("dy", 0), ctx))
        duration = float(_resolve_value(params.get("duration", 200), ctx))

        branch_ctx = ctx._branches.get(ctx._get_branch_id()) if ctx._get_branch_id() else None
        pause_event = branch_ctx.pause_event if branch_ctx else ctx.pause_event

        cx, cy = _get_cursor_pos()
        target_x = cx + dx
        target_y = cy + dy

        _eased_move(target_x, target_y, duration, ctx.stop_event, "ease_in_out", pause_event=pause_event)
    except Exception as e:
        print(f"[新引擎] 相对位移出错: {e}")
        ctx.log_error(f"相对位移出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def _handle_flow_control(node: ExecNode, ctx: ExecContext):
    params = node.params
    try:
        action = params.get("action", "stop_all")
        target_task = _resolve_value(params.get("target_task", ""), ctx)

        if action == "stop_all":
            ctx.stop_event.set()
            ctx.task_pool.stop_all()
        elif action == "stop_self":
            ctx.stop_event.set()
        elif action == "stop_task":
            if target_task:
                ctx.task_pool.stop(target_task)
        elif action == "pause_task":
            if target_task:
                ctx.task_pool.pause(target_task)
        elif action == "resume_task":
            if target_task:
                ctx.task_pool.resume(target_task)
    except Exception as e:
        print(f"[新引擎] 动作控制出错: {e}")
        ctx.log_error(f"动作控制出错: {e}", node_id=node.id, error_type="runtime")

    _execute_flow(node.id, "next", ctx)


def register(handlers: dict):
    handlers["_handle_mouse_click"] = _handle_mouse_click
    handlers["_handle_key_action"] = _handle_key_action
    handlers["_handle_mouse_scroll"] = _handle_mouse_scroll
    handlers["_handle_text_input"] = _handle_text_input
    handlers["_handle_wait"] = _handle_wait
    handlers["_handle_window_manage"] = _handle_window_manage
    handlers["_handle_program_open"] = _handle_program_open
    handlers["_handle_program_close"] = _handle_program_close
    handlers["_handle_mouse_move"] = _handle_mouse_move
    handlers["_handle_mouse_move_rel"] = _handle_mouse_move_rel
    handlers["_handle_flow_control"] = _handle_flow_control
