# -*- coding: utf-8 -*-
"""
使用方式:
  from precision import (
      boost_process_priority,
      boost_thread_priority,
      set_thread_affinity,
      precise_sleep_v5,
      auto_warmup,
  )
"""

import ctypes
from ctypes import wintypes
import time
import threading
import struct
import atexit

# ==============================================================================
# 0. WinAPI
# ==============================================================================
kernel32 = ctypes.windll.kernel32
winmm = ctypes.windll.winmm

_timer_period_enabled = False


def set_system_timer_resolution_enabled(enable=True):
    """切换系统定时器分辨率(1ms)。返回当前是否启用。"""
    global _timer_period_enabled
    target = bool(enable)
    if target == _timer_period_enabled:
        return _timer_period_enabled

    try:
        if target:
            winmm.timeBeginPeriod(1)
            _timer_period_enabled = True
        else:
            winmm.timeEndPeriod(1)
            _timer_period_enabled = False
    except Exception:
        # 失败时保持原状态，避免误导调用方。
        pass
    return _timer_period_enabled


def is_system_timer_resolution_enabled():
    return bool(_timer_period_enabled)


set_system_timer_resolution_enabled(True)

def _cleanup():
    try:
        set_system_timer_resolution_enabled(False)
    except Exception:
        pass
atexit.register(_cleanup)

_is_64bit = struct.calcsize("P") == 8

# ==============================================================================
# 1. 高分辨率定时器 (windll — 释放GIL)
# ==============================================================================
CREATE_WAITABLE_TIMER_HIGH_RESOLUTION = 0x00000002
TIMER_ALL_ACCESS = 0x1F0003

class HighResTimer:
    def __init__(self):
        self._is_high_res = False
        self.handle = None
        try:
            kernel32.CreateWaitableTimerExW.restype = wintypes.HANDLE
            kernel32.CreateWaitableTimerExW.argtypes = [
                wintypes.LPVOID, wintypes.LPCWSTR,
                wintypes.DWORD, wintypes.DWORD,
            ]
            self.handle = kernel32.CreateWaitableTimerExW(
                None, None, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS
            )
            if self.handle and self.handle != -1:
                self._is_high_res = True
            else:
                self.handle = kernel32.CreateWaitableTimerExW(
                    None, None, 0, TIMER_ALL_ACCESS
                )
        except Exception:
            self.handle = kernel32.CreateWaitableTimerW(None, True, None)

    @property
    def is_high_resolution(self):
        return self._is_high_res

    def wait(self, seconds):
        if seconds <= 0:
            return 0.0
        due_time_100ns = int(-seconds * 10_000_000)
        due_time = ctypes.c_longlong(due_time_100ns)
        kernel32.SetWaitableTimer(
            self.handle, ctypes.byref(due_time), 0, None, None, False
        )
        kernel32.WaitForSingleObject(self.handle, 0xFFFFFFFF)
        return 0.0

    def close(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

_timer_local = threading.local()
def _get_timer():
    if not hasattr(_timer_local, "timer") or _timer_local.timer is None:
        _timer_local.timer = HighResTimer()
    return _timer_local.timer

# ==============================================================================
# 2. QPC 基础设施
# ==============================================================================
class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

kernel32.QueryPerformanceCounter.argtypes = [ctypes.POINTER(LARGE_INTEGER)]
kernel32.QueryPerformanceCounter.restype = wintypes.BOOL
kernel32.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(LARGE_INTEGER)]
kernel32.QueryPerformanceFrequency.restype = wintypes.BOOL

_freq = LARGE_INTEGER()
kernel32.QueryPerformanceFrequency(ctypes.byref(_freq))
QPC_FREQ = _freq.LowPart | (_freq.HighPart << 32)

# ==============================================================================
# 3. 原生 x64 机器码忙等
# ==============================================================================
_native_spin_func = None
_qpc_func_ptr = ctypes.cast(kernel32.QueryPerformanceCounter, ctypes.c_void_p).value

def _create_native_spin_func():
    kernel32.VirtualAlloc.restype = ctypes.c_void_p
    kernel32.VirtualAlloc.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD
    ]
    mc = bytes([
        0x53, 0x41, 0x54, 0x48, 0x83, 0xEC, 0x28,
        0x48, 0x89, 0xCB, 0x49, 0x89, 0xD4,
        0x48, 0x8D, 0x4C, 0x24, 0x20, 0x41, 0xFF, 0xD4,
        0x48, 0x8B, 0x44, 0x24, 0x20, 0x48, 0x39, 0xD8,
        0x72, 0xEE,
        0x48, 0x83, 0xC4, 0x28, 0x41, 0x5C, 0x5B, 0xC3,
    ])
    buf = kernel32.VirtualAlloc(None, 4096, 0x1000, 0x40)
    if not buf:
        return None
    ctypes.memmove(buf, mc, len(mc))
    return ctypes.CFUNCTYPE(None, ctypes.c_uint64, ctypes.c_void_p)(buf)

def _init_native_spin():
    global _native_spin_func
    if _is_64bit:
        _native_spin_func = _create_native_spin_func()

_init_native_spin()

# ==============================================================================
# 4. 混合忙等 (100us 脉冲 + Python yield)
# ==============================================================================
_PULSE_DURATION = 0.0001  # 100us

def _hybrid_spin_wait(end_time_perf, stop_event, perf_counter):
    if _native_spin_func is not None:
        while perf_counter() < end_time_perf:
            if stop_event.is_set():
                return
            now = perf_counter()
            pulse_end = min(now + _PULSE_DURATION, end_time_perf)
            target_qpc = int(pulse_end * QPC_FREQ)
            _native_spin_func(target_qpc, _qpc_func_ptr)
    else:
        while perf_counter() < end_time_perf:
            if stop_event.is_set():
                return
            time.sleep(0)

# ==============================================================================
# 5. 自适应偏差补偿器 (v5.1 修复: 作用于最终目标)
# ==============================================================================
class AdaptiveCompensator:
    """
    v5:   bias -> 调整 timer->spin 切换点 (不影响总延迟!)
    v5.1: bias -> 直接调整 最终目标 (总延迟居中到 target)
    """
    def __init__(self, alpha=0.04, warmup=30):
        self.bias = 0.0
        self.alpha = alpha
        self.warmup = warmup
        self.count = 0
        self._errors = []
        self._window = 60

    @property
    def is_converged(self):
        return self.count >= self.warmup

    def _is_outlier(self, value):
        if len(self._errors) < 20:
            return False
        n = len(self._errors)
        mean = sum(self._errors) / n
        var = sum((e - mean) ** 2 for e in self._errors) / n
        std = var ** 0.5
        return std > 0 and abs(value - mean) > 3 * std

    def get_adjusted_target(self, original_target, min_total=0.0002):
        if self.count < self.warmup:
            return original_target
        adjusted = original_target - self.bias
        adjusted = max(adjusted, min_total)
        adjusted = max(adjusted, original_target * 0.1)
        return adjusted

    def update(self, actual_delay, target):
        error = actual_delay - target
        self.count += 1
        self._errors.append(error)
        if len(self._errors) > self._window:
            self._errors.pop(0)
        if self._is_outlier(error):
            return
        self.bias = self.bias + self.alpha * error
        self.bias = max(-0.0002, min(0.002, self.bias))

    def reset(self):
        self.bias = 0.0
        self.count = 0
        self._errors.clear()

# ==============================================================================
# 6. 一次标定: 混合忙等固有开销
# ==============================================================================
_HYBRID_SPIN_OVERHEAD = None

def _calibrate_hybrid_spin_overhead():
    global _HYBRID_SPIN_OVERHEAD
    _get_timer().wait(0.001)
    samples = []
    stop = threading.Event()
    pc = time.perf_counter
    for _ in range(300):
        start = pc()
        end = start + 0.000001
        _hybrid_spin_wait(end, stop, pc)
        samples.append((pc() - start) * 1_000_000)
    samples.sort()
    _HYBRID_SPIN_OVERHEAD = samples[len(samples) // 2] / 1_000_000
    return _HYBRID_SPIN_OVERHEAD

# ==============================================================================
# 7. 线程本地状态 + 优先级管理
# ==============================================================================
_comp_local = threading.local()

def _get_compensator():
    if not hasattr(_comp_local, "comp") or _comp_local.comp is None:
        _comp_local.comp = AdaptiveCompensator(alpha=0.04, warmup=30)
    return _comp_local.comp

# ==============================================================================
# 进程/线程优先级档位
# ------------------------------------------------------------------------------
# 原实现只有 boost_process_priority()，把整个进程抬到 HIGH_PRIORITY_CLASS，
# 且全仓库没有任何恢复调用 —— 一旦跑过一次宏，WebUI 进程（含 OCR、截图线程、
# 监视器轮询）会永久以高优先级运行，直接和游戏抢 CPU。这与"不抢占游戏资源"
# 的需求正面冲突。这里改为「档位 + 记住原始值 + 可恢复」。
# ==============================================================================
PROCESS_PRIORITY_TIERS = {
    "idle": 0x00000040,          # IDLE_PRIORITY_CLASS
    "below": 0x00004000,         # BELOW_NORMAL_PRIORITY_CLASS
    "normal": 0x00000020,        # NORMAL_PRIORITY_CLASS
    "above": 0x00008000,         # ABOVE_NORMAL_PRIORITY_CLASS
    "high": 0x00000080,          # HIGH_PRIORITY_CLASS
    "realtime": 0x00000100,      # REALTIME_PRIORITY_CLASS
}

THREAD_PRIORITY_TIERS = {
    "idle": -15,
    "lowest": -2,
    "below": -1,
    "normal": 0,
    "above": 1,
    "highest": 2,
    "time_critical": 15,
}

_original_process_priority = None
_original_thread_priority = None
_priority_lock = threading.Lock()


def _decl(fn, restype, argtypes):
    try:
        fn.restype = restype
        fn.argtypes = argtypes
    except Exception:
        pass


# ctypes 默认把返回值当 c_int 且参数按 int 传入。64 位下 GetCurrentProcess()
# 返回的句柄会被截断，GetPriorityClass 因此失败返回 0（0 不是合法的优先级类，
# 会被误当成 IDLE 记进 _original_process_priority）。显式声明签名修正该问题。
_decl(kernel32.GetCurrentProcess, wintypes.HANDLE, [])
_decl(kernel32.GetPriorityClass, wintypes.DWORD, [wintypes.HANDLE])
_decl(kernel32.SetPriorityClass, wintypes.BOOL, [wintypes.HANDLE, wintypes.DWORD])
_decl(kernel32.GetCurrentThread, wintypes.HANDLE, [])
_decl(kernel32.GetThreadPriority, ctypes.c_int, [wintypes.HANDLE])
_decl(kernel32.SetThreadPriority, wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int])

# 线程亲和性：DWORD_PTR 在 64 位下是 64 位宽，必须显式声明签名，否则
#   · 参数按 32 位 int 传入 —— GetCurrentThread() 返回的 0xFFFF...FFFE 会直接抛
#     `ArgumentError argument 1: OverflowError: int too long to convert`；
#   · 返回值按 c_int 接收 —— 失败(=0)与「原掩码恰好 0」无法区分。
# 两者叠加的结果：64 位下绑核要么报错，要么静默失效。
# c_size_t 即 DWORD_PTR。
_decl(kernel32.SetThreadAffinityMask, ctypes.c_size_t,
      [wintypes.HANDLE, ctypes.c_size_t])
_decl(kernel32.GetProcessAffinityMask, wintypes.BOOL,
      [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)])


def get_process_priority():
    try:
        return int(kernel32.GetPriorityClass(kernel32.GetCurrentProcess()))
    except Exception:
        return 0


def set_process_priority_tier(tier="above"):
    """设置进程优先级档位。首次调用会记住原始值，供 restore 使用。"""
    global _original_process_priority
    cls = PROCESS_PRIORITY_TIERS.get(str(tier).lower())
    if cls is None:
        return False
    with _priority_lock:
        try:
            if _original_process_priority is None:
                cur = get_process_priority()
                if cur:
                    _original_process_priority = cur
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), cls)
            return True
        except Exception:
            return False


def restore_process_priority():
    """恢复进程优先级到本进程首次被修改前的值。"""
    global _original_process_priority
    with _priority_lock:
        if _original_process_priority is None:
            return False
        try:
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), _original_process_priority)
            return True
        except Exception:
            return False


def set_thread_priority_tier(tier="time_critical"):
    """设置当前线程优先级档位。首次调用会记住原始值。"""
    global _original_thread_priority
    val = THREAD_PRIORITY_TIERS.get(str(tier).lower())
    if val is None:
        return False
    with _priority_lock:
        try:
            if _original_thread_priority is None:
                _original_thread_priority = int(
                    kernel32.GetThreadPriority(kernel32.GetCurrentThread())
                )
            kernel32.SetThreadPriority(kernel32.GetCurrentThread(), val)
            return True
        except Exception:
            return False


def restore_thread_priority():
    global _original_thread_priority
    with _priority_lock:
        if _original_thread_priority is None:
            return False
        try:
            kernel32.SetThreadPriority(kernel32.GetCurrentThread(), _original_thread_priority)
            return True
        except Exception:
            return False


def boost_process_priority():
    # 兼容旧调用：语义等价但会被记账，之后可用 restore_process_priority() 还原。
    return set_process_priority_tier("high")


def boost_thread_priority():
    return set_thread_priority_tier("time_critical")

# 单个处理器组最多 64 个逻辑处理器；SetThreadAffinityMask 的掩码也受此限制。
_MAX_CORES_PER_GROUP = 64
_affinity_warned = set()
_affinity_warn_lock = threading.Lock()


def _affinity_warn(msg):
    """同一条警告只打印一次，避免每个线程/每次循环刷屏。"""
    with _affinity_warn_lock:
        if msg in _affinity_warned:
            return
        _affinity_warned.add(msg)
    print(f"[绑核] {msg}")


def get_logical_cpu_count():
    import os
    return max(1, min(int(os.cpu_count() or 1), _MAX_CORES_PER_GROUP))


def get_process_affinity_mask():
    """返回 (进程允许的掩码, 系统掩码)；取不到时返回 (None, None)。"""
    try:
        proc_mask = ctypes.c_size_t()
        sys_mask = ctypes.c_size_t()
        ok = kernel32.GetProcessAffinityMask(
            kernel32.GetCurrentProcess(),
            ctypes.byref(proc_mask), ctypes.byref(sys_mask))
        if ok:
            return proc_mask.value, sys_mask.value
    except Exception:
        pass
    return None, None


def set_thread_affinity(core_index=3):
    """把当前线程绑定到指定逻辑核心。

    返回 bool（不再静默成功）：
      · 索引非法 / 不在进程亲和集合内 / 系统调用失败 → False
      · 成功 → True
    调用方可用返回值决定是否打印“已绑核”，避免失败也报成功。
    """
    try:
        core_index = int(core_index)
    except (TypeError, ValueError):
        _affinity_warn("核心索引非法: {!r}".format(core_index))
        return False

    num_cores = get_logical_cpu_count()
    if core_index < 0 or core_index >= num_cores:
        _affinity_warn("核心索引 {} 超出可用范围 [0, {})，本次不绑核".format(core_index, num_cores))
        return False

    mask = 1 << core_index
    proc_mask, _ = get_process_affinity_mask()
    if proc_mask and not (mask & proc_mask):
        _affinity_warn("CPU{} 不在进程允许的核心集合内(0x{:X})，本次不绑核".format(core_index, proc_mask))
        return False

    try:
        prev = kernel32.SetThreadAffinityMask(kernel32.GetCurrentThread(), mask)
    except Exception as e:
        _affinity_warn("绑定 CPU{} 异常: {}".format(core_index, e))
        return False

    if not prev:
        _affinity_warn("绑定 CPU{} 失败(SetThreadAffinityMask 返回 0)".format(core_index))
        return False
    return True


def clear_thread_affinity():
    """解除绑定，恢复为「进程允许的全部核心」。

    用进程亲和掩码而不是 (1<<cpu_count)-1 —— 后者在进程本身被限制过核心
    （如通过任务管理器设置过亲和性、或跨处理器组）时会把线程放到不允许的核上。
    """
    proc_mask, _ = get_process_affinity_mask()
    mask = proc_mask or ((1 << get_logical_cpu_count()) - 1)
    if not mask:
        return False
    try:
        prev = kernel32.SetThreadAffinityMask(kernel32.GetCurrentThread(), mask)
        return bool(prev)
    except Exception as e:
        _affinity_warn("解除绑核异常: {}".format(e))
        return False

def get_system_cpu_info():
    import os
    total_cores = os.cpu_count() or 4
    return {
        "total_cores": total_cores,
        "physical_cores": total_cores // 2 if total_cores > 1 else 1,
    }

def auto_warmup(target_s=0.030, iterations=30):
    stop = threading.Event()
    comp = _get_compensator()
    for _ in range(iterations):
        precise_sleep_v5(target_s, stop, comp)

# ==============================================================================
# 8. 核心: precise_sleep_v5
# ==============================================================================
_TIMER_LATE_THRESHOLD = 0.0008  # 800us


def _wait_unpause(pause_event, stop_event):
    while pause_event.is_set() and not stop_event.is_set():
        stop_event.wait(timeout=0.05)


def precise_sleep_v5(seconds, stop_event, compensator=None, pause_event=None):
    if seconds <= 0 or stop_event.is_set():
        return

    if compensator is None:
        compensator = _get_compensator()

    global _HYBRID_SPIN_OVERHEAD
    if _HYBRID_SPIN_OVERHEAD is None:
        _calibrate_hybrid_spin_overhead()

    timer = _get_timer()
    perf_counter = time.perf_counter
    start_perf = perf_counter()

    if pause_event is not None and pause_event.is_set():
        _wait_unpause(pause_event, stop_event)
        if stop_event.is_set():
            return
        elapsed = perf_counter() - start_perf
        if elapsed >= seconds:
            compensator.update(elapsed, seconds)
            return

    # ★ 关键修复: bias 作用于最终目标
    adjusted_target = compensator.get_adjusted_target(seconds)
    actual_end_perf = start_perf + adjusted_target

    # 自适应忙等裕度
    if adjusted_target < 0.002:
        spin_margin = 0.00015
    elif adjusted_target < 0.005:
        spin_margin = 0.0002
    else:
        spin_margin = 0.00015

    # 极短延迟: 直接忙等
    if adjusted_target <= spin_margin * 2:
        _hybrid_spin_wait(actual_end_perf, stop_event, perf_counter)
        compensator.update(perf_counter() - start_perf, adjusted_target)
        return

    intermediate_end_perf = actual_end_perf - spin_margin

    # ---- Phase 1: 粗睡眠 (windll, 释放GIL) ----
    if seconds > 0.05:
        coarse_threshold = 0.005
        max_chunk = 0.005
    elif seconds > 0.01:
        coarse_threshold = 0.003
        max_chunk = 0.003
    else:
        coarse_threshold = 0.001
        max_chunk = 0.002

    while perf_counter() < intermediate_end_perf - coarse_threshold:
        if pause_event is not None and pause_event.is_set():
            _wait_unpause(pause_event, stop_event)
            if stop_event.is_set():
                compensator.update(perf_counter() - start_perf, seconds)
                return
            if perf_counter() >= actual_end_perf:
                compensator.update(perf_counter() - start_perf, seconds)
                return
        if stop_event.is_set():
            compensator.update(perf_counter() - start_perf, seconds)
            return
        remaining = intermediate_end_perf - perf_counter()
        chunk = min(max_chunk, remaining - coarse_threshold * 0.5)
        if chunk > 0.0001:
            before_wait = perf_counter()
            timer.wait(chunk)
            after_wait = perf_counter()
            # ★ 迟到检测
            if (after_wait - before_wait - chunk) > _TIMER_LATE_THRESHOLD:
                break

    # ---- Phase 2: 中精度 (windll, 释放GIL) ----
    fine_threshold = 0.0002
    while perf_counter() < intermediate_end_perf - fine_threshold:
        if pause_event is not None and pause_event.is_set():
            _wait_unpause(pause_event, stop_event)
            if stop_event.is_set():
                compensator.update(perf_counter() - start_perf, seconds)
                return
            if perf_counter() >= actual_end_perf:
                compensator.update(perf_counter() - start_perf, seconds)
                return
        if stop_event.is_set():
            compensator.update(perf_counter() - start_perf, seconds)
            return
        remaining = intermediate_end_perf - perf_counter()
        chunk = min(0.0001, remaining - fine_threshold * 0.5)
        if chunk > 0.00001:
            timer.wait(chunk)

    # ---- Phase 3: 混合忙等 ----
    if not stop_event.is_set():
        _hybrid_spin_wait(actual_end_perf, stop_event, perf_counter)

    compensator.update(perf_counter() - start_perf, seconds)

# ==============================================================================
# 9. 基准测试
# ==============================================================================
def benchmark_precision(iterations=500, warmup=50):
    import statistics

    boost_process_priority()
    boost_thread_priority()
    set_thread_affinity(core_index=1)

    timer = _get_timer()
    comp = _get_compensator()

    print("=" * 70)
    print(" Tier 0 精度引擎 v5.1 基准测试")
    print(f" 高分辨率定时器: {'TSC' if timer.is_high_resolution else '回退'}")
    spin_type = "x64 混合(100us)" if _native_spin_func else "Python回退"
    print(f" 忙等模式: {spin_type}")
    print(f" GIL策略: windll释放 + 混合yield(每100us)")
    print(f" 全局时钟: 1ms (timeBeginPeriod)")
    print(f" 补偿策略: 最终目标补偿 (居中)")
    if _HYBRID_SPIN_OVERHEAD is not None:
        print(f" 混合忙等开销标定: {_HYBRID_SPIN_OVERHEAD * 1e6:.1f}us")
    print(f" 测试: 预热{warmup}次 + 测量{iterations}次")
    print("=" * 70)

    test_cases = [
        ("1ms", 0.001),
        ("5ms", 0.005),
        ("10ms", 0.010),
        ("50ms", 0.050),
        ("100ms", 0.100),
    ]

    for name, target_s in test_cases:
        stop = threading.Event()
        comp.reset()

        for _ in range(warmup):
            precise_sleep_v5(target_s, stop, comp)

        target_ms = target_s * 1000
        samples = []
        for _ in range(iterations):
            s = time.perf_counter()
            precise_sleep_v5(target_s, stop, comp)
            samples.append((time.perf_counter() - s) * 1000)

        mean = statistics.mean(samples)
        median = statistics.median(samples)
        stdev = statistics.stdev(samples)
        max_err = max(abs(v - target_ms) for v in samples)
        outliers = sum(1 for v in samples if abs(v - target_ms) > 0.1)

        non_outliers = [v for v in samples if abs(v - target_ms) <= 0.1]
        if len(non_outliers) > 1:
            nm = statistics.mean(non_outliers)
            nmed = statistics.median(non_outliers)
            nsd = statistics.stdev(non_outliers)
        else:
            nm = nmed = nsd = float("nan")

        below = sum(1 for v in samples if v < target_ms)
        above = sum(1 for v in samples if v >= target_ms)

        print(f"\n  {name:>5s} 目标: {target_ms:>7.2f}ms")
        print(f"  范围: [{min(samples):.4f}, {max(samples):.4f}]")
        print(f"  均值: {mean:.4f}ms (偏移{(mean - target_ms) * 1000:+.1f}us)")
        print(f"  中位数: {median:.4f}ms (偏移{(median - target_ms) * 1000:+.1f}us)")
        print(f"  最大误差: {max_err:.4f}ms  异常值(>100us): {outliers}/{iterations}")
        print(f"  下方/上方: {below}/{above} ({below / len(samples) * 100:.0f}%/{above / len(samples) * 100:.0f}%)")
        print(f"  收敛偏差: {comp.bias * 1e6:.1f}us")
        print(f"  非异常值: 均值={nm:.4f}ms 中位数={nmed:.4f}ms sigma={nsd:.4f}ms")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    benchmark_precision()
