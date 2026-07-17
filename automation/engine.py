import os
import random
import re
import sys
import time
import threading
import traceback

from engine.precision import (
    precise_sleep_v5 as precise_sleep,
    boost_process_priority,
    boost_thread_priority,
    set_thread_affinity,
    clear_thread_affinity,
    get_system_cpu_info,
    auto_warmup,
)
from engine.input_sendinput import (
    get_vk, set_cursor_pos, send_click_sendinput,
    send_key_sendinput, send_scroll_sendinput, release_all_modifiers,
    InterceptionSession,
)
from automation.compiler import ExecGraph, ExecNode
from automation.registry import PluginRegistry


_old_engine_module = None
_old_engine_lock = threading.Lock()

_thread_local = threading.local()


class BusinessException(Exception):
    pass

_BUILTIN_VARIABLES = {
    "timestamp": lambda: str(int(time.time() * 1000)),
    "timestamp_s": lambda: str(int(time.time())),
    "date": lambda: time.strftime("%Y-%m-%d"),
    "time": lambda: time.strftime("%H:%M:%S"),
    "datetime": lambda: time.strftime("%Y-%m-%d %H:%M:%S"),
    "datetime_compact": lambda: time.strftime("%Y%m%d_%H%M%S"),
    "random": lambda: str(int(time.time() * 1000) % 100000),
    "random_int": lambda: str(random.randint(0, 999999)),
    "year": lambda: time.strftime("%Y"),
    "month": lambda: time.strftime("%m"),
    "day": lambda: time.strftime("%d"),
    "hour": lambda: time.strftime("%H"),
    "minute": lambda: time.strftime("%M"),
    "second": lambda: time.strftime("%S"),
    "weekday": lambda: str(time.localtime().tm_wday),
    "pid": lambda: str(os.getpid()),
}


def _get_old_engine():
    global _old_engine_module
    if _old_engine_module is not None:
        return _old_engine_module
    with _old_engine_lock:
        if _old_engine_module is not None:
            return _old_engine_module
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


_node_logger_run_counter = [0]

class NodeLogger:
    def __init__(self):
        self._lock = threading.Lock()
        self._enabled = False
        self._continuous = False
        self._run_start_ns = 0
        self._current_run_id = 0
        self._runs = []
        self._max_runs = 50

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def set_continuous(self, continuous):
        self._continuous = continuous

    def start_run(self):
        with self._lock:
            _node_logger_run_counter[0] += 1
            self._run_start_ns = time.perf_counter_ns()
            self._current_run_id = _node_logger_run_counter[0]
            return self._current_run_id

    def end_run(self):
        pass

    def clear(self):
        with self._lock:
            self._runs.clear()
            self._current_run_id = 0

    def record(self, node_id, node_type, start_ns, end_ns, status):
        if not self._enabled:
            return
        run_offset_ms = (start_ns - self._run_start_ns) / 1_000_000.0 if self._run_start_ns else 0
        duration_ms = (end_ns - start_ns) / 1_000_000.0
        entry = {
            "node_id": str(node_id),
            "node_type": node_type or "",
            "start_ns": start_ns,
            "end_ns": end_ns,
            "duration_ms": round(duration_ms, 3),
            "offset_ms": round(run_offset_ms, 3),
            "status": status,
            "run_id": self._current_run_id,
        }
        with self._lock:
            if not self._runs or self._runs[-1]["run_id"] != self._current_run_id:
                self._runs.append({
                    "run_id": self._current_run_id,
                    "start_ns": self._run_start_ns,
                    "entries": [],
                })
                if len(self._runs) > self._max_runs:
                    self._runs = self._runs[-self._max_runs:]
            self._runs[-1]["entries"].append(entry)

    def get_data(self):
        with self._lock:
            runs_copy = []
            for r in self._runs:
                runs_copy.append({
                    "run_id": r["run_id"],
                    "start_ns": r["start_ns"],
                    "entries": list(r["entries"]),
                })
            return {
                "runs": runs_copy,
                "enabled": self._enabled,
                "continuous": self._continuous,
                "current_run_id": self._current_run_id,
            }


class Scope:
    def __init__(self, scope_id, fork_node_id, parent_branch_id=None):
        self.scope_id = scope_id
        self.fork_node_id = fork_node_id
        self.parent_branch_id = parent_branch_id
        self.branch_ids = []
        self.child_scope_ids = []
        self.status = "running"
        self.winner_branch_id = None

    def set_status(self, status):
        self.status = status


class BranchContext:
    def __init__(self, branch_id, parent_ctx, fork_node_id=None, affinity_config=None,
                 parent_branch_id=None, scope_id=None):
        self.branch_id = branch_id
        self.parent_ctx = parent_ctx
        self.fork_node_id = fork_node_id
        self.parent_branch_id = parent_branch_id
        self.scope_id = scope_id
        self.child_scope_ids = []
        self.thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self._status_lock = threading.Lock()
        self._status = "running"
        self.affinity_config = affinity_config
        self._executed_nodes = set()
        self._goto_target = None
        self._upstream_outputs = {}
        self._upstream_node_id = None
        self._current_affinity = None

    @property
    def status(self):
        with self._status_lock:
            return self._status

    def set_status(self, status):
        with self._status_lock:
            self._status = status

    def cancel(self):
        self.stop_event.set()
        with self._status_lock:
            self._status = "cancelled"


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
        self._image_match_cache: dict = {}
        self._image_match_cache_lock = threading.RLock()
        self.hwnd_cache: dict = {}
        self.interception_session: InterceptionSession = None
        self._profile = PROFILE_PRESETS.get("standard", PROFILE_PRESETS["lite"])
        self._goto_target = None
        self._ocr_engine = None
        self._ocr_affinity_core = -1
        self._digit_template_cache = {}
        self._capture_manager = None
        self._data_lock = threading.RLock()
        self.errors: list = []
        self._executed_nodes: set = set()
        self._branches: dict = {}
        self._scopes: dict = {}
        self._join_events: dict = {}
        self._join_arrivals: dict = {}
        self._join_done_flag: dict = {}
        self._affinity_tracker: dict = {}
        self._race_events: dict = {}
        self.node_retry_count: int = 3
        self.node_retry_delay_ms: int = 500
        self._reached_end: bool = False
        self._nesting_depth: int = 0
        self._data_recursion_depth: int = 0
        self._sub_script_contexts: dict = {}
        self.node_logger = NodeLogger()
        self.breakpoints: set = set()
        self._breakpoint_hit_node = None
        self._current_executing_node = None
        self._last_node_status = "ok"

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

    def log_warning(self, message, node_id=None):
        with self._data_lock:
            self.errors.append({
                "message": message,
                "node_id": node_id,
                "type": "warning",
                "time": time.time(),
            })

    def log_info(self, message, node_id=None):
        with self._data_lock:
            self.errors.append({
                "message": message,
                "node_id": node_id,
                "type": "info",
                "time": time.time(),
            })

    def get_errors(self):
        with self._data_lock:
            return list(self.errors)

    def clear_errors(self):
        with self._data_lock:
            self.errors.clear()

    @staticmethod
    def _get_branch_id():
        return getattr(_thread_local, 'branch_id', None)

    @staticmethod
    def _set_branch_id(bid):
        _thread_local.branch_id = bid

    @staticmethod
    def _get_current_affinity():
        return getattr(_thread_local, 'current_affinity', None)

    @staticmethod
    def _set_current_affinity(affinity):
        _thread_local.current_affinity = affinity

    @staticmethod
    def _get_upstream_outputs():
        if not hasattr(_thread_local, 'upstream_outputs'):
            _thread_local.upstream_outputs = {}
        return _thread_local.upstream_outputs

    @staticmethod
    def _set_upstream_outputs(val):
        _thread_local.upstream_outputs = val

    @staticmethod
    def _get_upstream_node_id():
        return getattr(_thread_local, 'upstream_node_id', None)

    @staticmethod
    def _set_upstream_node_id(val):
        _thread_local.upstream_node_id = val

    def _get_current_branch_ctx(self):
        bid = self._get_branch_id()
        return self._branches.get(bid) if bid else None


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

    def start(self, node_id, compiled, macro_name, options, stop_event_parent, on_complete=None, affinity=None) -> str:
        with self._lock:
            self._seed += 1
            task_id = f"task_{self._seed}"

        stop_event = threading.Event()
        pause_event = threading.Event()

        def worker():
            if affinity is not None:
                try:
                    set_thread_affinity(affinity)
                except Exception:
                    pass
            _oe = _get_old_engine()
            try:
                # 节点级 standby 覆盖：on=强制尝试 standby; off=强制 Python; inherit=读全局开关
                _standby_ov = (options or {}).get("standby_override", "inherit")
                if _standby_ov not in ("on", "off", "inherit"):
                    _standby_ov = "inherit"
                _use_standby = (_standby_ov == "on") or (
                    _standby_ov == "inherit" and getattr(_oe, "ENABLE_STANDBY_ENGINE", False)
                    and _oe._standby_available())
                if _use_standby:
                    try:
                        ok = _oe._execute_via_standby(compiled, stop_event, macro_name, options)
                        if ok:
                            with self._lock:
                                if task_id in self.tasks:
                                    self.tasks[task_id].status = "completed"
                            if on_complete:
                                on_complete(task_id, "completed")
                            return
                        if not getattr(_oe, "STANDBY_FALLBACK_ON_FAIL", True):
                            print(f"[TaskPool] standby 执行失败且未启用回退: {macro_name}")
                            with self._lock:
                                if task_id in self.tasks:
                                    self.tasks[task_id].status = "completed"
                            if on_complete:
                                on_complete(task_id, "completed")
                            return
                        print(f"[TaskPool] standby 回退到 Python 路径: {macro_name}")
                    except Exception as se:
                        if not getattr(_oe, "STANDBY_FALLBACK_ON_FAIL", True):
                            raise
                        print(f"[TaskPool] standby 异常, 回退到 Python 路径: {se}")
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
            finally:
                try:
                    clear_thread_affinity()
                except Exception:
                    pass

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

    def _resolve_task_id(self, task_or_node_id):
        with self._lock:
            if task_or_node_id in self.tasks:
                return task_or_node_id
            for tid, t in self.tasks.items():
                if t.node_id == task_or_node_id:
                    return tid
        return task_or_node_id

    def stop(self, task_id) -> bool:
        task_id = self._resolve_task_id(task_id)
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
        task_id = self._resolve_task_id(task_id)
        with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status == "running":
                task.pause_event.set()
                return True
        return False

    def resume(self, task_id) -> bool:
        task_id = self._resolve_task_id(task_id)
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
    if isinstance(value, list):
        return [_resolve_value(item, ctx) for item in value]
    if not isinstance(value, str):
        return value
    bookmark_pattern = re.compile(r'@([\w\u4e00-\u9fff]+)\.(x|y|w|h|mode|hwnd_var|remark|name)')
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
                num_val = float(result)
                if num_val == int(num_val):
                    return int(num_val)
                return num_val
        except (ValueError, TypeError):
            pass
        return result
    pattern = re.compile(r'\$\{([^}]+)\}')
    matches = pattern.findall(value)
    if not matches:
        return value
    if len(matches) == 1 and value == f"${{{matches[0]}}}":
        var_name = matches[0]
        if var_name in _BUILTIN_VARIABLES:
            return _BUILTIN_VARIABLES[var_name]()
        var_val = ctx.safe_get_variable(var_name)
        if var_val is not None:
            if isinstance(var_val, float) and var_val == int(var_val):
                return int(var_val)
            return var_val
        if '.' in var_name:
            parts = var_name.split('.', 1)
            if len(parts) == 2:
                bm_first, bm_second = parts
                for nid, node in ctx.graph.nodes.items():
                    if node.type == "utility/bookmark" and node.params.get("name") == bm_first:
                        return node.params.get(bm_second, 0)
                const_node = ctx.graph.nodes.get(bm_first)
                if const_node and const_node.type.startswith("utility/"):
                    try:
                        from automation.handlers import NODE_HANDLERS
                        handler_name = PluginRegistry.get_node(const_node.type)
                        if handler_name and isinstance(handler_name, dict):
                            h = NODE_HANDLERS.get(handler_name.get("handler"))
                            if h:
                                h(const_node, ctx)
                    except Exception:
                        pass
                cr_key = f"{bm_first}.{bm_second}"
                cr_val = ctx.check_results.get(cr_key)
                if cr_val is not None:
                    return cr_val
        if var_name in ctx.check_results:
            return ctx.check_results[var_name]
        print(f"[新引擎] 警告：变量 '{var_name}' 未定义")
        return ""
    result = value
    for var_name in matches:
        if var_name in _BUILTIN_VARIABLES:
            builtin_val = _BUILTIN_VARIABLES[var_name]()
            result = result.replace(f"${{{var_name}}}", builtin_val)
            continue
        var_val = ctx.safe_get_variable(var_name)
        if var_val is not None:
            display_val = int(var_val) if isinstance(var_val, float) and var_val == int(var_val) else var_val
            result = result.replace(f"${{{var_name}}}", str(display_val))
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
                    const_node2 = ctx.graph.nodes.get(bm_first)
                    if const_node2 and const_node2.type.startswith("utility/"):
                        try:
                            from automation.handlers import NODE_HANDLERS
                            hname = PluginRegistry.get_node(const_node2.type)
                            if hname and isinstance(hname, dict):
                                h2 = NODE_HANDLERS.get(hname.get("handler"))
                                if h2:
                                    h2(const_node2, ctx)
                        except Exception:
                            pass
                    cr_key = f"{bm_first}.{bm_second}"
                    cr_val = ctx.check_results.get(cr_key)
                    if cr_val is not None:
                        result = result.replace(f"${{{var_name}}}", str(cr_val))
                    else:
                        print(f"[新引擎] 警告：引用 '{var_name}' 未定义")
                        result = result.replace(f"${{{var_name}}}", "")
        elif var_name in ctx.check_results:
            result = result.replace(f"${{{var_name}}}", str(ctx.check_results[var_name]))
        else:
            print(f"[新引擎] 警告：变量 '{var_name}' 未定义")
            result = result.replace(f"${{{var_name}}}", "")
    try:
        if '.' in result or result.replace('-', '').replace('.', '').isdigit():
            num_val = float(result)
            if num_val == int(num_val):
                return int(num_val)
            return num_val
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


def _predefine_const_nodes(graph: ExecGraph, ctx: ExecContext):
    for nid, node in graph.nodes.items():
        if node.type in ("utility/const_number", "utility/const_string", "utility/const_bool"):
            if node.type == "utility/const_number":
                value = node.params.get("value", 0)
                try:
                    value = float(value)
                    if value == int(value):
                        value = int(value)
                except (ValueError, TypeError):
                    value = 0
                ctx.check_results[f"{node.id}.value"] = value
                ctx.safe_set_variable(_get_const_out_var_name(node), value)
            elif node.type == "utility/const_string":
                value = str(node.params.get("value", ""))
                ctx.check_results[f"{node.id}.value"] = value
                ctx.safe_set_variable(_get_const_out_var_name(node), value)
            elif node.type == "utility/const_bool":
                value = bool(node.params.get("value", True))
                ctx.check_results[f"{node.id}.value"] = value
                ctx.safe_set_variable(_get_const_out_var_name(node), value)


def _get_const_out_var_name(node):
    node_def = PluginRegistry.get_node(node.type)
    if node_def and isinstance(node_def, dict):
        display_name = node_def.get("display_name", "")
        if display_name:
            short_id = node.id[-6:] if len(node.id) > 6 else node.id
            return f"{display_name}_{short_id}_out"
    return node.id + "_out"


_DATA_RECURSION_LIMIT = 100

def _ensure_data_inputs(node_id: str, ctx: ExecContext, _depth: int = 0):
    effective_depth = ctx._data_recursion_depth + _depth
    if effective_depth > _DATA_RECURSION_LIMIT:
        ctx.log_error(f"数据依赖递归深度超限(节点 {node_id}，可能存在无限环路)", node_id=node_id, error_type="runtime")
        return
    node = ctx.graph.nodes.get(node_id)
    if node is None:
        return
    branch_ctx = ctx._get_current_branch_ctx()
    executed_set = branch_ctx._executed_nodes if branch_ctx else ctx._executed_nodes
    for port_name, sources in node.data_inputs.items():
        for src in sources:
            src_node_id = src["source_node_id"]
            src_port = src["source_port"]
            key = f"{src_node_id}.{src_port}"
            if key in ctx.check_results:
                continue
            if src_node_id in executed_set:
                continue
            src_node = ctx.graph.nodes.get(src_node_id)
            if src_node is None:
                continue
            _ensure_data_inputs(src_node_id, ctx, _depth + 1)
            if ctx.stop_event.is_set():
                return
            if branch_ctx and branch_ctx.stop_event.is_set():
                return
            ctx._data_recursion_depth = effective_depth + 1
            _execute_node(src_node_id, ctx)
            ctx._data_recursion_depth = _depth


def _collect_flow_descendants(graph, node_id, port_name):
    visited = set()
    result = set()
    visited.add(node_id)
    node = graph.nodes.get(node_id)
    if node is None:
        return result
    children = node.get_flow_children(port_name)
    stack = list(children)
    while stack:
        child_id = stack.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        result.add(child_id)
        child_node = graph.nodes.get(child_id)
        if child_node is None:
            continue
        for pn in child_node.flow_children:
            for grandchild_id in child_node.get_flow_children(pn):
                if grandchild_id not in visited:
                    stack.append(grandchild_id)
    return result


def _get_active_fork_descendant_nodes(ctx: ExecContext):
    active_nodes = set()
    for scope in ctx._scopes.values():
        if scope.status == "cancelled":
            continue
        fork_node_id = scope.fork_node_id
        has_active = False
        for bid in scope.branch_ids:
            bctx = ctx._branches.get(bid)
            if bctx and bctx.status == "running":
                has_active = True
                break
        if has_active:
            fork_node = ctx.graph.nodes.get(fork_node_id)
            if fork_node:
                for port_name in fork_node.flow_children:
                    descendants = _collect_flow_descendants(ctx.graph, fork_node_id, port_name)
                    active_nodes.update(descendants)
    return active_nodes


def _reset_body_nodes(body_nodes, ctx: ExecContext):
    branch_ctx = ctx._get_current_branch_ctx()
    executed_set = branch_ctx._executed_nodes if branch_ctx else ctx._executed_nodes
    active_fork_nodes = _get_active_fork_descendant_nodes(ctx)
    with ctx._data_lock:
        executed_set -= body_nodes
        keys_to_remove = set()
        for k in ctx.check_results:
            for nid in body_nodes:
                if k.startswith(f"{nid}."):
                    if nid not in active_fork_nodes:
                        keys_to_remove.add(k)
                    break
        for k in keys_to_remove:
            del ctx.check_results[k]
        for nid in body_nodes:
            if nid in ctx._join_events:
                ctx._join_events[nid].clear()
            if nid in ctx._join_arrivals:
                ctx._join_arrivals[nid].clear()
            if nid in ctx._join_done_flag:
                ctx._join_done_flag[nid] = False


def _cancel_child_scopes(parent_branch_id, ctx: ExecContext):
    for scope in ctx._scopes.values():
        if scope.parent_branch_id == parent_branch_id:
            for bid in scope.branch_ids:
                bctx = ctx._branches.get(bid)
                if bctx and bctx.status == "running":
                    bctx.cancel()
                _cancel_child_scopes(bid, ctx)
            scope.status = "cancelled"


def _get_pause_event(ctx: ExecContext):
    branch_ctx = ctx._get_current_branch_ctx()
    return branch_ctx.pause_event if branch_ctx else ctx.pause_event


def _execute_flow(node_id: str, port_name: str, ctx: ExecContext):
    _marker = getattr(ctx, '_log_done_marker', None)
    if _marker is not None and _marker[0] == 0:
        _marker[0] = time.perf_counter_ns()
    if ctx.stop_event.is_set():
        return
    branch_ctx = ctx._get_current_branch_ctx()
    if branch_ctx and branch_ctx.stop_event.is_set():
        return
    node = ctx.graph.nodes.get(node_id)
    if node is None:
        return
    upstream_key = f"{node_id}.{port_name}"
    upstream_data = {}
    for k, v in ctx.check_results.items():
        if k.startswith(f"{node_id}."):
            upstream_data[k] = v
    ctx._set_upstream_outputs(upstream_data)
    ctx._set_upstream_node_id(node_id)
    children = node.get_flow_children(port_name)
    for child_id in children:
        _execute_node(child_id, ctx)
        if ctx.stop_event.is_set():
            return
        if branch_ctx and branch_ctx.stop_event.is_set():
            return


def _has_output_port(node, port_name):
    node_def = PluginRegistry.get_node(node.type)
    if node_def and isinstance(node_def, dict):
        for out_port in node_def.get("outputs", []):
            if out_port.get("name") == port_name:
                return True
    return False


def _handle_plugin_node(node, ctx: ExecContext):
    try:
        from core.plugin_manager import PluginManager
        from core.plugin_context import PluginContext
        from automation.detection.capture import capture_screen

        node_def = PluginRegistry.get_node(node.type)
        plugin_id = None
        action = node.type.split("/", 1)[-1]
        if node_def and isinstance(node_def, dict):
            plugin_id = node_def.get("_plugin_id")
            action = node_def.get("backendAction", action)
        if not plugin_id:
            for pid in PluginManager._plugins:
                manifest = PluginManager.get_manifest(pid)
                if manifest and action in manifest.get("nodes", []):
                    plugin_id = pid
                    break
        if not plugin_id:
            plugin_id = node.type.split("/", 1)[-1]
        params = dict(node.params) if node.params else {}

        if node_def and isinstance(node_def, dict):
            schema = node_def.get("params_schema", {})
            for key, field_def in schema.items():
                if isinstance(field_def, dict) and field_def.get("varRef") and key in params:
                    params[key] = _resolve_value(params[key], ctx)

        # 创建带有执行期能力的 PluginContext
        # 让插件可以使用DXGI截图、读写变量等能力
        def _capture_fn(region):
            return capture_screen(region, ctx)

        plugin_ctx = PluginContext(
            emit_fn=PluginManager._emit_to_window,
            capture_fn=_capture_fn,
            var_get_fn=lambda name, default=None: ctx.safe_get_variable(name, default),
            var_set_fn=lambda name, value: ctx.safe_set_variable(name, value),
            ctx_ref=ctx,
        )

        result = PluginManager.execute(plugin_id, action, params, context=plugin_ctx)
        if result and isinstance(result, dict):
            for k, v in result.get("set_variables", {}).items():
                ctx.safe_set_variable(k, v)
            for k, v in result.get("check_results", {}).items():
                ctx.safe_set_check_result(f"{node.id}.{k}", v)
            if not result.get("ok"):
                ctx.log_error(
                    result.get("error", "插件执行失败"),
                    node_id=str(node.id),
                    error_type="plugin",
                )
    except Exception as e:
        ctx.log_error(f"插件节点异常 {node.type}: {e}", node_id=str(node.id), error_type="plugin")
        _execute_flow(node.id, "fail" if _has_output_port(node, "fail") else "next", ctx)
        return

    ok = result.get("ok", True) if result and isinstance(result, dict) else True
    if result and isinstance(result, dict) and "flow_port" in result:
        fp = result["flow_port"]
        if _has_output_port(node, fp):
            flow_port = fp
        else:
            flow_port = "next"
    elif ok:
        flow_port = "success" if _has_output_port(node, "success") else "next"
    else:
        flow_port = "fail" if _has_output_port(node, "fail") else "next"
    _execute_flow(node.id, flow_port, ctx)


def _execute_node(node_id: str, ctx: ExecContext):
    from automation.handlers import NODE_HANDLERS

    branch_ctx = ctx._get_current_branch_ctx()
    executed_set = branch_ctx._executed_nodes if branch_ctx else ctx._executed_nodes

    with ctx._data_lock:
        if node_id in executed_set:
            return

    current_id = node_id

    if current_id in ctx.breakpoints:
        ctx._breakpoint_hit_node = current_id
        ctx.pause_event.set()
        if branch_ctx:
            branch_ctx.pause_event.set()

    _saved_depth = ctx._data_recursion_depth
    ctx._data_recursion_depth = 0
    _ensure_data_inputs(current_id, ctx)
    ctx._data_recursion_depth = _saved_depth
    if ctx.stop_event.is_set():
        return
    max_goto_iterations = 100000

    for _ in range(max_goto_iterations):
        if ctx.stop_event.is_set():
            return
        if branch_ctx and branch_ctx.stop_event.is_set():
            return

        while (ctx.pause_event.is_set() or (branch_ctx and branch_ctx.pause_event.is_set())) and not ctx.stop_event.is_set() and not (branch_ctx and branch_ctx.stop_event.is_set()):
            time.sleep(0.05)

        if ctx.stop_event.is_set():
            return
        if branch_ctx and branch_ctx.stop_event.is_set():
            return

        node = ctx.graph.nodes.get(current_id)
        if node is None:
            print(f"[新引擎] 节点不存在: {current_id}")
            return

        handler_name = PluginRegistry.get_node(node.type)
        if handler_name is None:
            if node.type.startswith("plugin/"):
                handler = _handle_plugin_node
            else:
                print(f"[新引擎] 未知节点类型: {node.type}")
                ctx.log_error(f"未知节点类型: {node.type}", node_id=current_id, error_type="system")
                return
        else:
            handler_method_name = handler_name.get("handler")
            if handler_method_name and handler_method_name.startswith("_plugin_"):
                handler = _handle_plugin_node
            else:
                handler = NODE_HANDLERS.get(handler_method_name)
                if handler is None:
                    if handler_method_name is None:
                        return
                    print(f"[新引擎] 未注册处理器: {handler_method_name}")
                    ctx.log_error(f"未注册处理器: {handler_method_name}", node_id=current_id, error_type="system")
                    return

        handler_name_info = handler_name if isinstance(handler_name, dict) else None
        _original_params = None
        if handler_name_info and node.params:
            schema = handler_name_info.get("params_schema", {})
            if schema:
                _original_params = node.params
                _resolved_params = dict(node.params)
                for key, field_def in schema.items():
                    if isinstance(field_def, dict) and field_def.get("varRef") and key in _resolved_params:
                        _resolved_params[key] = _resolve_value(_resolved_params[key], ctx)
                node.params = _resolved_params

        ctx._goto_target = None
        if branch_ctx:
            branch_ctx._goto_target = None

        with ctx._data_lock:
            executed_set.add(current_id)
        ctx._current_executing_node = current_id

        _log_enabled = ctx.node_logger._enabled
        _log_start_ns = 0
        _done_container = [0]
        if _log_enabled:
            _log_start_ns = time.perf_counter_ns()
            ctx._log_done_marker = _done_container

        _last_exception = None
        _retry_count = ctx.node_retry_count
        _retry_delay = ctx.node_retry_delay_ms / 1000.0

        _node_status = "ok"
        try:
            for _attempt in range(_retry_count + 1):
                if ctx.stop_event.is_set():
                    return
                if branch_ctx and branch_ctx.stop_event.is_set():
                    return
                try:
                    handler(node, ctx)
                    _last_exception = None
                    break
                except BusinessException as e:
                    _last_exception = e
                    if _attempt < _retry_count:
                        print(f"[新引擎] 节点 {node.type}({current_id}) 业务异常(第{_attempt+1}次)，{_retry_delay*1000:.0f}ms后重试: {e}")
                        if _retry_delay > 0:
                            time.sleep(_retry_delay)
                        continue
                    else:
                        error_msg = f"节点 {node.type}({current_id}) 业务异常重试{_retry_count}次后仍失败: {e}"
                        print(f"[新引擎] {error_msg}")
                        ctx.log_error(error_msg, node_id=current_id, error_type="business")
                        _node_status = "error"
                except (FileNotFoundError, ImportError, TypeError, ValueError, MemoryError) as e:
                    _last_exception = e
                    error_msg = f"节点 {node.type}({current_id}) 系统错误: {e}"
                    print(f"[新引擎] {error_msg}")
                    ctx.log_error(error_msg, node_id=current_id, error_type="system")
                    _node_status = "error"
                    break
                except Exception as e:
                    _last_exception = e
                    if _attempt < _retry_count:
                        print(f"[新引擎] 节点 {node.type}({current_id}) 执行异常(第{_attempt+1}次)，{_retry_delay*1000:.0f}ms后重试: {e}")
                        if _retry_delay > 0:
                            time.sleep(_retry_delay)
                        continue
                    else:
                        error_msg = f"节点 {node.type}({current_id}) 执行异常重试{_retry_count}次后仍失败: {e}"
                        print(f"[新引擎] {error_msg}")
                        ctx.log_error(error_msg, node_id=current_id, error_type="runtime")
                        _node_status = "error"

            if _log_enabled:
                if _done_container[0] == 0:
                    _done_container[0] = time.perf_counter_ns()
                ctx.node_logger.record(str(current_id), node.type, _log_start_ns, _done_container[0], _node_status)

            if _last_exception is not None:
                fail_port = "fail" if _has_output_port(node, "fail") else "next"
                _execute_flow(current_id, fail_port, ctx)
        finally:
            if _original_params is not None:
                node.params = _original_params

        goto_target = branch_ctx._goto_target if (branch_ctx and branch_ctx._goto_target) else ctx._goto_target
        if goto_target:
            with ctx._data_lock:
                executed_set.discard(goto_target)
            _ensure_data_inputs(goto_target, ctx)
            current_id = goto_target
            if branch_ctx:
                branch_ctx._goto_target = None
            else:
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


def _do_click(button, click_type, hold_time, stop_event, ctx: ExecContext = None, pause_event=None):
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
            precise_sleep(hold_time / 1000.0, stop_event, pause_event=pause_event)
        _send_click(left, True, ctx) if ctx else send_click_sendinput(left=left, up=True)
        return
    if click_type == "dblclick":
        for _ in range(2):
            _send_click(left, False, ctx) if ctx else send_click_sendinput(left=left, up=False)
            precise_sleep(0.01, stop_event, pause_event=pause_event)
            _send_click(left, True, ctx) if ctx else send_click_sendinput(left=left, up=True)
            precise_sleep(0.01, stop_event, pause_event=pause_event)
        return
    _send_click(left, False, ctx) if ctx else send_click_sendinput(left=left, up=False)
    precise_sleep(0.01, stop_event, pause_event=pause_event)
    _send_click(left, True, ctx) if ctx else send_click_sendinput(left=left, up=True)


def _interpolated_move(phys_x, phys_y, duration_ms, stop_event, pause_event=None):
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
            precise_sleep(step_delay, stop_event, pause_event=pause_event)


def _get_cursor_pos():
    import ctypes
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def execute_graph(graph: ExecGraph, stop_event: threading.Event, breakpoints: set = None, log_enabled: bool = False):
    from automation.handlers import register_all_handlers
    register_all_handlers()

    from automation.handlers.control import _clear_script_cache
    _clear_script_cache()

    ctx = ExecContext(graph, stop_event)
    graph._exec_ctx = ctx

    profile_name = graph.settings.get("execution_profile", "standard")
    profile = PROFILE_PRESETS.get(profile_name, PROFILE_PRESETS["standard"])
    ctx._profile = profile

    ctx.node_retry_count = graph.settings.get("node_retry_count", 3)
    ctx.node_retry_delay_ms = graph.settings.get("node_retry_delay_ms", 500)

    if breakpoints:
        ctx.breakpoints = set(str(b) for b in breakpoints)

    if log_enabled:
        ctx.node_logger.enable()

    if profile.get("interception_kb") or profile.get("interception_mouse"):
        # 全局参数优先级高于执行档案: 总开关关闭时, 无论 profile 如何, 都不使用 Interception
        # 总开关 AND 键盘/鼠标分开关 AND profile 设置, 三者同时为真才启用
        try:
            _old_eng = _get_old_engine()
            g_use_ic = bool(getattr(_old_eng, "USE_INTERCEPTION", True))
            g_use_ic_kb = g_use_ic and bool(getattr(_old_eng, "USE_INTERCEPTION_KEYBOARD", True))
            g_use_ic_mouse = g_use_ic and bool(getattr(_old_eng, "USE_INTERCEPTION_MOUSE", True))
        except Exception as _e:
            print(f"[新引擎] 读取旧引擎 Interception 全局参数失败, 仅按 profile 决策: {_e}")
            g_use_ic = True
            g_use_ic_kb = True
            g_use_ic_mouse = True

        use_kb = bool(profile.get("interception_kb", False)) and g_use_ic_kb
        use_mouse = bool(profile.get("interception_mouse", False)) and g_use_ic_mouse

        if not g_use_ic:
            print("[新引擎] Interception 总开关已关闭, 键鼠均使用 SendInput")

        if use_kb or use_mouse:
            try:
                ctx.interception_session = InterceptionSession(
                    use_keyboard=use_kb,
                    use_mouse=use_mouse,
                )
            except Exception as e:
                print(f"[新引擎] InterceptionSession 初始化失败，回退 SendInput: {e}")
                ctx.interception_session = None

    if not graph.entry_node_id:
        print("[新引擎] 错误：未找到入口节点")
        return

    _predefine_const_nodes(graph, ctx)

    start_node = graph.nodes.get(graph.entry_node_id) if graph.entry_node_id else None
    start_params = start_node.params if start_node else {}

    _should_boost = start_params.get("boost_priority", profile.get("boost_priority", True))
    if _should_boost:
        try:
            boost_process_priority()
            boost_thread_priority()
            print("[新引擎] 进程/线程优先级已提升")
        except Exception as e:
            print(f"[新引擎] 优先级提升失败: {e}")

    _should_affinity = start_params.get("affinity_enabled", profile.get("affinity", False))
    _affinity_core = start_params.get("affinity_core", -1)

    if _should_affinity:
        import os as _os
        try:
            total_cores = _os.cpu_count() or 4
        except Exception:
            total_cores = 4

        if _affinity_core < 0 or _affinity_core >= total_cores:
            _affinity_core = total_cores - 1

        try:
            set_thread_affinity(_affinity_core)
            with ctx._data_lock:
                ctx._affinity_tracker["main"] = _affinity_core
            print(f"[新引擎] 主执行线程已绑定到核心 {_affinity_core}")
        except Exception as e:
            print(f"[新引擎] 主线程绑核失败: {e}")

    _ocr_preload_needed = False
    _ocr_affinity_core_collect = -1
    for nid, node in graph.nodes.items():
        if node.type in ("detection/check_ocr", "monitor/monitor_ocr"):
            if node.params.get("ocr_preload", True):
                _ocr_preload_needed = True
            core_val = node.params.get("ocr_affinity_core", -1)
            if isinstance(core_val, (int, float)) and int(core_val) >= 0:
                _ocr_affinity_core_collect = int(core_val)

    if _ocr_preload_needed:
        try:
            from automation.detection.ocr import OCREngine
            engine = OCREngine()
            engine._get_rapidocr()
            with ctx._data_lock:
                ctx._ocr_engine = engine
            if _should_affinity and _ocr_affinity_core_collect >= 0:
                ctx._ocr_affinity_core = _ocr_affinity_core_collect
                ctx._affinity_tracker["ocr"] = _ocr_affinity_core_collect
            else:
                ctx._ocr_affinity_core = -1
            print("[新引擎] OCR 引擎已预加载")
        except Exception as e:
            print(f"[新引擎] OCR 预加载失败: {e}")

    if ctx.node_logger._enabled:
        ctx.node_logger.start_run()

    try:
        _execute_node(graph.entry_node_id, ctx)
    finally:
        if ctx.node_logger._enabled and not ctx.node_logger._continuous:
            ctx.node_logger.end_run()
        try:
            clear_thread_affinity()
        except Exception:
            pass
        release_all_modifiers()
        ctx.task_pool.stop_all()
        ctx.stop_event.set()
        for bid, bctx in ctx._branches.items():
            bctx.stop_event.set()
            if bctx.thread and bctx.thread.is_alive():
                bctx.thread.join(timeout=3.0)
        if ctx._capture_manager is not None:
            ctx._capture_manager.stop_all()
