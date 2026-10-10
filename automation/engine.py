import os
import re
import time
import threading
import traceback

from engine.precision import (
    precise_sleep_v5 as precise_sleep,
    boost_process_priority,
    boost_thread_priority,
    set_thread_affinity,
    auto_warmup,
)
from engine.input_sendinput import (
    get_vk, set_cursor_pos, send_click_sendinput,
    send_key_sendinput, send_scroll_sendinput, release_all_modifiers,
    send_unicode_char, InterceptionSession,
)
from automation.compiler import ExecGraph, ExecNode
from automation.registry import PluginRegistry


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
        self._data_lock = threading.RLock()
        self.errors: list = []
        self._executed_nodes: set = set()
        self._upstream_outputs: dict = {}
        self._upstream_node_id: str = None

        for var_name, var_def in graph.variables.items():
            self.variables[var_name] = var_def.get("init")

    def safe_set_variable(self, key, value):
        with self._data_lock:
            self.variables[key] = value

    def safe_get_variable(self, key, default=None):
        with self._data_lock:
            return self.variables.get(key, default)

    def safe_set_check_result(self, key, value):
        with self._data_lock:
            self.check_results[key] = value

    def safe_get_check_result(self, key, default=None):
        with self._data_lock:
            return self.check_results.get(key, default)

    def safe_set_cache(self, key, value):
        with self._data_lock:
            self.last_capture_cache[key] = value

    def safe_get_cache(self, key, default=None):
        with self._data_lock:
            return self.last_capture_cache.get(key, default)

    def log_error(self, message, node_id=None, error_type="system"):
        with self._data_lock:
            self.errors.append({
                "message": message,
                "node_id": node_id,
                "type": error_type,
                "time": time.time(),
            })

    def get_errors(self):
        with self._data_lock:
            return list(self.errors)

    def clear_errors(self):
        with self._data_lock:
            self.errors.clear()


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
    bookmark_pattern = re.compile(r'@([\\w\\u4e00-\\u9fff]+)\\.(x|y|w|h|mode|hwnd_var|remark|name)')
    bookmark_matches = bookmark_pattern.findall(value)
    if bookmark_matches:
        result = value
        for bm_name, bm_param in bookmark_matches:
            found = False
            for nid, node in ctx.graph.nodes.items():
                if node.type == "utility/bookmark" and node.params.get("name") == bm_name:
                    bm_val = node.params.get(bm_param, 0)
                    result = result.replace(f"@{bm_name}.{bm_param}", str(bm_val))
                    found = True
                    break
            if not found:
                print(f"[新引擎] 错误：坐标书签 '@{bm_name}' 未找到")
                result = result.replace(f"@{bm_name}.{bm_param}", "0")
        try:
            if '.' in result or result.replace('-', '').replace('.', '').isdigit():
                return float(result)
        except (ValueError, TypeError):
            pass
        return result
    pattern = re.compile(r'\\$\\{([^}]+)\\}')
    matches = pattern.findall(value)
    if not matches:
        return value
    result = value
    for var_name in matches:
        var_val = ctx.safe_get_variable(var_name)
        if var_val is not None:
            result = result.replace(f"${{{var_name}}}", str(var_val))
        elif '.' in var_name:
            parts = var_name.split('.', 1)
            if len(parts) == 2:
                bm_first, bm_second = parts
                bm_found = False
                for nid, node in ctx.graph.nodes.items():
                    if node.type == "utility/bookmark" and node.params.get("name") == bm_first:
                        bm_val = node.params.get(bm_second, 0)
                        result = result.replace(f"${{{var_name}}}", str(bm_val))
                        bm_found = True
                        break
                if not bm_found:
                    cr_key = f"{bm_first}.{bm_second}"
                    cr_val = ctx.check_results.get(cr_key)
                    if cr_val is not None:
                        result = result.replace(f"${{{var_name}}}", str(cr_val))
                    else:
                        print(f"[新引擎] 警告：引用 '{var_name}' 未定义")
                        result = result.replace(f"${{{var_name}}}", "0")
        elif var_name in ctx.check_results:
            result = result.replace(f"${{{var_name}}}", str(ctx.check_results[var_name]))
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
    cached = ctx.safe_get_cache(hwnd_var)
    if cached is not None and hwnd_var in ctx.hwnd_cache:
        return ctx.hwnd_cache[hwnd_var]
    try:
        hwnd = int(hwnd_var)
        ctx.hwnd_cache[hwnd_var] = hwnd
        return hwnd
    except (ValueError, TypeError):
        pass
    var_val = ctx.safe_get_variable(hwnd_var)
    if var_val is not None:
        try:
            hwnd = int(var_val)
            ctx.hwnd_cache[hwnd_var] = hwnd
            return hwnd
        except (ValueError, TypeError):
            pass
    return None


def _ensure_data_inputs(node_id: str, ctx: ExecContext):
    node = ctx.graph.nodes.get(node_id)
    if node is None:
        return
    for port_name, sources in node.data_inputs.items():
        for src in sources:
            src_node_id = src["source_node_id"]
            src_port = src["source_port"]
            key = f"{src_node_id}.{src_port}"
            if key in ctx.check_results:
                continue
            if src_node_id in ctx._executed_nodes:
                continue
            src_node = ctx.graph.nodes.get(src_node_id)
            if src_node is None:
                continue
            _ensure_data_inputs(src_node_id, ctx)
            if ctx.stop_event.is_set():
                return
            _execute_node(src_node_id, ctx)


def _execute_flow(node_id: str, port_name: str, ctx: ExecContext):
    if ctx.stop_event.is_set():
        return
    node = ctx.graph.nodes.get(node_id)
    if node is None:
        return
    upstream_key = f"{node_id}.{port_name}"
    upstream_data = {}
    for k, v in ctx.check_results.items():
        if k.startswith(f"{node_id}."):
            upstream_data[k] = v
    ctx._upstream_outputs = upstream_data
    ctx._upstream_node_id = node_id
    children = node.get_flow_children(port_name)
    for child_id in children:
        _execute_node(child_id, ctx)
        if ctx.stop_event.is_set():
            return


def _execute_node(node_id: str, ctx: ExecContext):
    from automation.handlers import NODE_HANDLERS

    with ctx._data_lock:
        if node_id in ctx._executed_nodes:
            return
        ctx._executed_nodes.add(node_id)

    _ensure_data_inputs(node_id, ctx)
    if ctx.stop_event.is_set():
        return

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

        if node.type == "flow/end":
            ctx.stop_event.set()
            ctx.task_pool.stop_all()
            return

        handler_name = PluginRegistry.get_node(node.type)
        if handler_name is None:
            print(f"[新引擎] 未知节点类型: {node.type}")
            ctx.log_error(f"未知节点类型: {node.type}", node_id=current_id, error_type="system")
            return

        handler_method_name = handler_name.get("handler")
        handler = NODE_HANDLERS.get(handler_method_name)
        if handler is None:
            if handler_method_name is None:
                return
            print(f"[新引擎] 未注册处理器: {handler_method_name}")
            ctx.log_error(f"未注册处理器: {handler_method_name}", node_id=current_id, error_type="system")
            return

        ctx._goto_target = None
        try:
            handler(node, ctx)
        except (FileNotFoundError, ImportError, TypeError, ValueError) as e:
            error_msg = f"节点 {node.type}({current_id}) 系统错误: {e}"
            print(f"[新引擎] {error_msg}")
            ctx.log_error(error_msg, node_id=current_id, error_type="system")
        except Exception as e:
            error_msg = f"节点 {node.type}({current_id}) 执行异常: {e}"
            print(f"[新引擎] {error_msg}")
            ctx.log_error(error_msg, node_id=current_id, error_type="runtime")

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


def execute_graph(graph: ExecGraph, stop_event: threading.Event):
    from automation.handlers import register_all_handlers
    register_all_handlers()

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
