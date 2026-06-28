#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standby 引擎 vs 现有路径 精度对比测试 (ns 级)

对比维度:
  1. 纯时序精度 (无注入): precise_sleep_v5 vs standby 自旋
  2. 含注入精度 (按键): Python 路径 vs standby 引擎
  3. RawInput 监听验证: 测量"注入到系统通知"延迟
  4. 大规模真实宏测试: 包含所有动作类型的宏, 500 次重复
  5. 不同间隔扫描: 1ms, 2ms, 5ms, 10ms, 50ms

三类抖动指标 (ns 单位):
  - arrival_jitter: actual_qpc - target_qpc        (自旋到达精度, 注入前)
  - e2e_jitter:     injection_done_qpc - target_qpc (端到端, 注入后)
  - inject_cost:    injection_done_qpc - actual_qpc (SendInput 本身耗时)

QPC 频率 10MHz, 1 tick = 100ns。
jitter_ns = (qpc_diff) * 1_000_000_000 // qpc_freq

用法:
  python test/测试_standby引擎对比.py

注意:
  - 测试会注入真实按键 (A 键) 和鼠标动作, 测试期间不能操作键盘鼠标
  - 鼠标移动用小位移 (dx=1) 避免光标跑飞
  - RawInput 监听线程绑另一个核, 避免与 standby 线程竞争
  - 脚本独立运行, 仅依赖 engine 和 _standby_engine
"""

import sys
import os
import time
import math
import statistics
import threading
import ctypes
from ctypes import wintypes

# 添加项目根目录到 path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from engine.precision import (
    boost_process_priority,
    boost_thread_priority,
    set_thread_affinity,
    precise_sleep_v5,
    QPC_FREQ,
)
from engine.input_sendinput import (
    send_key_sendinput,
    send_click_sendinput,
    send_move_sendinput,
    set_cursor_pos,
    send_scroll_sendinput,
)

# ==============================================================================
# Win32 API
# ==============================================================================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


kernel32.QueryPerformanceCounter.argtypes = [ctypes.POINTER(LARGE_INTEGER)]
kernel32.QueryPerformanceCounter.restype = wintypes.BOOL
kernel32.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(LARGE_INTEGER)]
kernel32.QueryPerformanceFrequency.restype = wintypes.BOOL


def qpc_now():
    li = LARGE_INTEGER()
    kernel32.QueryPerformanceCounter(ctypes.byref(li))
    return li.LowPart | (li.HighPart << 32)


def qpc_frequency():
    li = LARGE_INTEGER()
    kernel32.QueryPerformanceFrequency(ctypes.byref(li))
    return li.LowPart | (li.HighPart << 32)


# ==============================================================================
# 统计工具
# ==============================================================================
def percentile(values, q):
    if not values:
        return float("nan")
    arr = sorted(values)
    pos = (len(arr) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return arr[lo]
    return arr[lo] + (arr[hi] - arr[lo]) * (pos - lo)


def stats_ns(title, values_ns):
    """打印 ns 级统计块。values_ns 单位 ns (整数)。"""
    if not values_ns:
        print(f"\n[{title}] 无数据")
        return None
    p50 = percentile(values_ns, 0.50)
    p95 = percentile(values_ns, 0.95)
    p99 = percentile(values_ns, 0.99)
    p999 = percentile(values_ns, 0.999)
    mx = max(values_ns)
    mn = min(values_ns)
    mean = statistics.fmean(values_ns)
    stdev = statistics.stdev(values_ns) if len(values_ns) > 1 else 0.0
    print(f"\n[{title}]")
    print(f"  样本数: {len(values_ns)}")
    print(f"  范围:   [{mn}, {mx}] ns")
    print(f"  均值:   {mean:.1f} ns  (stdev={stdev:.1f})")
    print(f"  p50:    {p50:.0f} ns")
    print(f"  p95:    {p95:.0f} ns")
    print(f"  p99:    {p99:.0f} ns")
    print(f"  p99.9:  {p999:.0f} ns")
    print(f"  max:    {mx} ns")
    return {"p50": p50, "p95": p95, "p99": p99, "p999": p999, "max": mx,
            "mean": mean, "stdev": stdev}


def ticks_to_ns(qpc_diff, freq):
    """QPC tick 差转 ns (整数)。"""
    return int(qpc_diff) * 1_000_000_000 // freq


# ==============================================================================
# 动作类型常量 (与 _standby_engine 对齐)
# ==============================================================================
ACT_NOP = 0
ACT_KEY_DOWN = 1
ACT_KEY_UP = 2
ACT_MOUSE_MOVE_REL = 3
ACT_MOUSE_DOWN = 4
ACT_MOUSE_UP = 5
ACT_MOUSE_SCROLL = 6
ACT_SET_CURSOR_POS = 7

# 状态码
ST_OK = 0
ST_SENDINPUT_FAILED = 1
ST_INTERCEPTION_FAIL = 2
ST_SKIPPED = 3

# VK 码表 (与 engine.input_sendinput.VK_MAP 一致)
VK_MAP = {
    "left": 0x01, "right": 0x02, "middle": 0x04,
    "back": 0x08, "tab": 0x09, "enter": 0x0D, "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    "esc": 0x1B, "space": 0x20,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46,
    "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C,
    "m": 0x4D, "n": 0x4E, "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52,
    "s": 0x53, "t": 0x54, "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58,
    "y": 0x59, "z": 0x5A,
}


def get_vk(key):
    return VK_MAP.get(str(key).lower(), 0)


# ==============================================================================
# 宏编译: 脚本 → standby 时间线
# 与 宏执行框架3.2.py 的 compile_macro + compile_to_timeline 逻辑等价,
# 但直接生成 standby events, 不生成 Python func 闭包, 保证脚本独立运行。
# ==============================================================================
def _split_int_delta_preserve_sum(total_delta, steps):
    """按步拆分整数位移, 确保每步和为 round(total_delta)。"""
    if steps <= 0:
        return []
    target_total = int(round(float(total_delta)))
    out = []
    prev = 0
    for i in range(1, steps + 1):
        current = int(round(target_total * i / steps))
        out.append(current - prev)
        prev = current
    return out


def _split_float_duration_preserve_sum(total_seconds, steps):
    """按步拆分时长, 确保每步和为 total_seconds。"""
    if steps <= 0:
        return []
    total = max(0.0, float(total_seconds))
    out = []
    prev = 0.0
    for i in range(1, steps + 1):
        current = total * i / steps
        out.append(current - prev)
        prev = current
    return out


def compile_macro_to_timeline(script):
    """把宏脚本编译成 standby 时间线 events。

    与 宏执行框架3.2.py 的 compile_macro + compile_to_timeline 等价。
    返回: (events, events_meta)
      events: [(offset_ns, action_type, p1, p2, p3), ...]
      events_meta: [(desc, offset_ns, atype), ...]  与 events 一一对应
    """
    events = []
    meta = []
    offset_ns = 0

    def _parse(item):
        nonlocal offset_ns
        cmd = item[0]

        if cmd == "loop":
            loop_count = int(item[1])
            loop_body = item[2]
            for _ in range(loop_count):
                for sub in loop_body:
                    _parse(sub)
            return

        if cmd == "wait":
            delay_s = max(0.0, float(item[1]) / 1000.0)
            offset_ns += int(delay_s * 1_000_000_000)
            return

        if cmd == "view":
            dx = float(item[1][0])
            dy = float(item[1][1])
            dur_ms = max(0.0, float(item[2]))
            min_step_interval = 10
            max_steps = 100
            min_steps = 1
            target_steps = int(dur_ms / min_step_interval)
            steps = max(min_steps, min(target_steps, max_steps))
            step_dx_list = _split_int_delta_preserve_sum(dx, steps)
            step_dy_list = _split_int_delta_preserve_sum(dy, steps)
            step_delay_list = _split_float_duration_preserve_sum(dur_ms / 1000.0, steps)
            for i in range(steps):
                offset_ns += int(step_delay_list[i] * 1_000_000_000)
                sx = step_dx_list[i]
                sy = step_dy_list[i]
                if sx != 0 or sy != 0:
                    events.append((offset_ns, ACT_MOUSE_MOVE_REL, int(sx), int(sy), 0))
                    meta.append((f"view(step={i+1}/{steps},dx={sx},dy={sy})", offset_ns, "view"))
            return

        if cmd == "move_to":
            target_x = int(item[1])
            target_y = int(item[2])
            dur_ms = max(0.0, float(item[3]))
            min_step_ms = 10
            max_steps = 100
            steps = max(1, min(int(dur_ms / min_step_ms), max_steps))
            step_delay_list = _split_float_duration_preserve_sum(dur_ms / 1000.0, steps)
            for i in range(steps):
                t = (i + 1) / steps
                cur_x = int(round(target_x * t))
                cur_y = int(round(target_y * t))
                offset_ns += int(step_delay_list[i] * 1_000_000_000)
                events.append((offset_ns, ACT_SET_CURSOR_POS, cur_x, cur_y, 0))
                meta.append((f"move_to({cur_x},{cur_y})", offset_ns, "move_to"))
            return

        if cmd == "scroll":
            delta = int(item[1])
            # scroll 的 delay_s = 0.0, 不增加 offset_ns
            events.append((offset_ns, ACT_MOUSE_SCROLL, delta, 0, 0))
            meta.append((f"scroll({delta})", offset_ns, "scroll"))
            return

        # kd / ku / md / mu
        key_name = item[1]
        delay_s = max(0.0, float(item[2]) / 1000.0)
        offset_ns += int(delay_s * 1_000_000_000)

        if cmd == "kd":
            vk = get_vk(key_name)
            events.append((offset_ns, ACT_KEY_DOWN, int(vk), 0, 0))
            meta.append((f"kd({key_name})", offset_ns, "kd"))
        elif cmd == "ku":
            vk = get_vk(key_name)
            events.append((offset_ns, ACT_KEY_UP, int(vk), 0, 0))
            meta.append((f"ku({key_name})", offset_ns, "ku"))
        elif cmd == "md":
            key_lower = key_name.lower()
            if key_lower == "middle":
                events.append((offset_ns, ACT_MOUSE_DOWN, 3, 0, 0))
            else:
                is_left = (key_lower == "left")
                btn = 1 if is_left else 2
                events.append((offset_ns, ACT_MOUSE_DOWN, btn, 0, 0))
            meta.append((f"md({key_name})", offset_ns, "md"))
        elif cmd == "mu":
            key_lower = key_name.lower()
            if key_lower == "middle":
                events.append((offset_ns, ACT_MOUSE_UP, 3, 0, 0))
            else:
                is_left = (key_lower == "left")
                btn = 1 if is_left else 2
                events.append((offset_ns, ACT_MOUSE_UP, btn, 0, 0))
            meta.append((f"mu({key_name})", offset_ns, "mu"))

    for step in script:
        _parse(step)
    return events, meta


# ==============================================================================
# RawInput 监听线程
# 在独立线程中创建隐藏窗口 + 注册 RawInput + 消息泵, 监听键盘事件。
# 绑另一个核, 避免与 standby 线程竞争。
# ==============================================================================
WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
RIM_TYPEKEYBOARD = 1
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_KEYBOARD = 0x06
RI_KEY_BREAK = 0x0001

WND_CLASS_NAME = "StandbyTestRawInputProbe"


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("keyboard", RAWKEYBOARD),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


# Win32 函数原型
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_longlong
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = ctypes.c_longlong
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
user32.RegisterRawInputDevices.restype = wintypes.BOOL
user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, ctypes.POINTER(wintypes.UINT), wintypes.UINT]
user32.GetRawInputData.restype = wintypes.UINT
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = wintypes.SHORT
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

WNDPROC_TYPE = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class RawInputListener:
    """RawInput 键盘事件监听器。

    在独立线程中创建隐藏窗口 + 注册 RawInput + 运行消息泵,
    监听指定 VK 的按键事件, 用 QPC 记录时间戳。
    """

    def __init__(self, filter_vk=0x41):
        self.filter_vk = filter_vk
        self.events = []          # [(qpc, vk, is_down), ...]
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._thread_id = 0
        self._hwnd = None
        self._wndproc_ref = None  # 保持回调引用防止 GC
        self._ready = threading.Event()
        self.qpc_freq = qpc_frequency()

    def start(self, core_index):
        """启动监听线程。"""
        self._stop_event.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, args=(core_index,), daemon=True)
        self._thread.start()
        # 等待窗口创建完成
        self._ready.wait(timeout=2.0)

    def stop(self):
        """停止监听线程。"""
        self._stop_event.set()
        # 向监听线程发送 WM_QUIT 退出消息泵
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_events(self):
        """获取捕获的事件列表副本。"""
        with self._lock:
            return list(self.events)

    def _run(self, core_index):
        """监听线程主函数。"""
        # 绑核 + 提升优先级
        try:
            set_thread_affinity(core_index)
        except Exception:
            pass
        boost_thread_priority()
        self._thread_id = kernel32.GetCurrentThreadId()

        try:
            self._create_window()
            self._register_raw_input()
        except Exception as e:
            print(f"[RawInput] 初始化失败: {e}")
            self._ready.set()
            return

        self._ready.set()
        self._message_loop()

        # 清理
        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None

    def _create_window(self):
        """创建隐藏消息窗口。"""
        hinstance = kernel32.GetModuleHandleW(None)
        self._wndproc_ref = WNDPROC_TYPE(self._wndproc)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = self._wndproc_ref
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinstance
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = WND_CLASS_NAME
        wc.hIconSm = None

        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if atom == 0:
            # 可能已注册, 忽略错误
            pass

        hwnd = user32.CreateWindowExW(
            0, WND_CLASS_NAME, "StandbyTestProbe", 0,
            0, 0, 0, 0, None, None, hinstance, None,
        )
        if not hwnd:
            raise OSError(f"CreateWindowExW 失败: {ctypes.get_last_error()}")
        self._hwnd = hwnd

    def _register_raw_input(self):
        """注册 RawInput 键盘设备 (RIDEV_INPUTSINK, 即使窗口不在前台也接收)。"""
        kbd = RAWINPUTDEVICE()
        kbd.usUsagePage = HID_USAGE_PAGE_GENERIC
        kbd.usUsage = HID_USAGE_GENERIC_KEYBOARD
        kbd.dwFlags = RIDEV_INPUTSINK
        kbd.hwndTarget = self._hwnd
        devices = (RAWINPUTDEVICE * 1)(kbd)
        if not user32.RegisterRawInputDevices(devices, 1, ctypes.sizeof(RAWINPUTDEVICE)):
            raise OSError(f"RegisterRawInputDevices 失败: {ctypes.get_last_error()}")

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """窗口消息处理。"""
        if msg == WM_INPUT:
            self._process_raw_input(lparam)
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _process_raw_input(self, raw_input_handle):
        """处理单条 RawInput 消息。"""
        if self._stop_event.is_set():
            return

        size = wintypes.UINT(0)
        header_size = ctypes.sizeof(RAWINPUTHEADER)
        ret = user32.GetRawInputData(raw_input_handle, RID_INPUT, None, ctypes.byref(size), header_size)
        if ret != 0 or size.value == 0:
            return

        buffer = ctypes.create_string_buffer(size.value)
        written = user32.GetRawInputData(raw_input_handle, RID_INPUT, buffer, ctypes.byref(size), header_size)
        if written != size.value:
            return

        if size.value < ctypes.sizeof(RAWINPUT):
            return

        raw = ctypes.cast(buffer, ctypes.POINTER(RAWINPUT)).contents
        if raw.header.dwType == RIM_TYPEKEYBOARD:
            self._record_keyboard(raw.keyboard)

    def _record_keyboard(self, kbd):
        """记录键盘事件。"""
        vk = kbd.VKey
        # 过滤指定 VK (SendInput 注入的事件 VK 正常; Interception 注入可能 VK=0, 也接受)
        if self.filter_vk and vk != 0 and vk != self.filter_vk:
            return

        tick = qpc_now()
        is_down = not (kbd.Flags & RI_KEY_BREAK)

        with self._lock:
            self.events.append((tick, int(vk), is_down))

    def _message_loop(self):
        """消息泵 (GetMessageW 阻塞, 收到 WM_QUIT 退出)。"""
        msg = MSG()
        while not self._stop_event.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:  # WM_QUIT 或错误
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


# ==============================================================================
# GetAsyncKeyState 轮询监听 (RawInput 不可用时的回退方案)
# ==============================================================================
class AsyncKeyStatePoller:
    """高优先级线程轮询 GetAsyncKeyState, 记录按键状态翻转的 QPC。

    1us 间隔自旋, 绑另一个核。
    """

    def __init__(self, vk=0x41):
        self.vk = vk
        self.events = []          # [(qpc, vk, is_down), ...]
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self.qpc_freq = qpc_frequency()

    def start(self, core_index):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(core_index,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_events(self):
        with self._lock:
            return list(self.events)

    def _run(self, core_index):
        try:
            set_thread_affinity(core_index)
        except Exception:
            pass
        boost_thread_priority()

        prev_pressed = bool(user32.GetAsyncKeyState(self.vk) & 0x8000)
        while not self._stop_event.is_set():
            now_pressed = bool(user32.GetAsyncKeyState(self.vk) & 0x8000)
            if now_pressed != prev_pressed:
                tick = qpc_now()
                with self._lock:
                    self.events.append((tick, self.vk, now_pressed))
                prev_pressed = now_pressed
            # 纯自旋, 不 sleep (time.sleep 最低精度 1-15ms, 无法捕获 5ms 事件)
            # 偶尔让出时间片避免完全饿死系统 (每 4096 次迭代让出一次)
            if (len(self.events) & 0xFFF) == 0:
                kernel32.SwitchToThread()


# ==============================================================================
# standby 执行辅助
# ==============================================================================
def run_standby(se, events, core, use_interception=0, timeout_ms=30000):
    """提交时间线并执行 standby, 返回 results 列表。"""
    se.submit_timeline(events, 0)
    se.start(core, use_interception)

    # 等待完成
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        if se.wait_completion(10):
            break
    else:
        se.stop()
        print("[standby] 超时, 强制停止")
        return []

    return se.get_results()


def extract_jitters(results, qpc_freq):
    """从 standby results 提取三类抖动 (ns)。

    返回: (arrival_jitters, e2e_jitters, inject_costs, key_event_indices)
      key_event_indices: KEY_DOWN/KEY_UP 事件的索引列表 (用于 RawInput 对比)
    """
    arrival = []
    e2e = []
    inject = []
    key_indices = []
    for i, r in enumerate(results):
        target_qpc, actual_qpc, inj_done_qpc, action_type, status = r
        if status == ST_SKIPPED:
            continue
        arrival.append(ticks_to_ns(actual_qpc - target_qpc, qpc_freq))
        e2e.append(ticks_to_ns(inj_done_qpc - target_qpc, qpc_freq))
        inject.append(ticks_to_ns(inj_done_qpc - actual_qpc, qpc_freq))
        if action_type in (ACT_KEY_DOWN, ACT_KEY_UP):
            key_indices.append(i)
    return arrival, e2e, inject, key_indices


# ==============================================================================
# precise_sleep 路径执行 (对比基准)
# ==============================================================================
def _execute_sendinput(atype, p1, p2, p3):
    """根据动作类型调用对应的 SendInput 函数。"""
    if atype == ACT_KEY_DOWN:
        send_key_sendinput(p1, False)
    elif atype == ACT_KEY_UP:
        send_key_sendinput(p1, True)
    elif atype == ACT_MOUSE_MOVE_REL:
        send_move_sendinput(p1, p2)
    elif atype == ACT_MOUSE_DOWN:
        # p1: 1=L, 2=R, 3=M
        if p1 == 1:
            send_click_sendinput(left=True, up=False)
        elif p1 == 2:
            send_click_sendinput(left=False, up=False)
        else:
            send_click_sendinput(left=None, up=False)
    elif atype == ACT_MOUSE_UP:
        if p1 == 1:
            send_click_sendinput(left=True, up=True)
        elif p1 == 2:
            send_click_sendinput(left=False, up=True)
        else:
            send_click_sendinput(left=None, up=True)
    elif atype == ACT_MOUSE_SCROLL:
        send_scroll_sendinput(p1)
    elif atype == ACT_SET_CURSOR_POS:
        set_cursor_pos(p1, p2)
    # ACT_NOP: 无注入


def execute_via_precise_sleep(events, qpc_freq, stop_event, comp):
    """用 precise_sleep + SendInput 执行 standby 时间线, 记录抖动。

    返回与 standby get_results() 格式一致的 results 列表:
      [(target_qpc, actual_qpc, injection_done_qpc, action_type, status), ...]
    """
    from engine.precision import _get_compensator
    if comp is None:
        comp = _get_compensator()

    results = []
    start_qpc = qpc_now()
    prev_offset_ns = 0

    for offset_ns, atype, p1, p2, p3 in events:
        # 相对延迟 (距上一个事件)
        delay_ns = offset_ns - prev_offset_ns
        delay_s = delay_ns / 1_000_000_000.0
        prev_offset_ns = offset_ns

        # target_qpc = start_qpc + offset_ns * qpc_freq / 1e9
        target_qpc = start_qpc + (offset_ns * qpc_freq) // 1_000_000_000

        # sleep
        if delay_s > 0:
            precise_sleep_v5(delay_s, stop_event, comp)

        # 到达 (注入前)
        actual_qpc = qpc_now()

        # 注入
        try:
            _execute_sendinput(atype, p1, p2, p3)
            status = ST_OK
        except Exception:
            status = ST_SENDINPUT_FAILED

        # 注入完成
        injection_done_qpc = qpc_now()
        results.append((target_qpc, actual_qpc, injection_done_qpc, atype, status))

    return results


# ==============================================================================
# 测试 1: 纯时序对比 (无注入)
# ==============================================================================
def test_pure_timing_standby(se, n=300, interval_s=0.005, core=1):
    """standby 纯时序测试 (ACT_NOP, 无注入)。返回 arrival_jitters (ns)。"""
    interval_ns = int(interval_s * 1e9)
    events = [(i * interval_ns, ACT_NOP, 0, 0, 0) for i in range(1, n + 1)]

    results = run_standby(se, events, core, use_interception=0, timeout_ms=int(n * interval_s * 1000 + 5000))
    qpc_freq = se.get_qpc_frequency()
    arrival, _, _, _ = extract_jitters(results, qpc_freq)
    return arrival


def test_pure_timing_precise_sleep(n=300, interval_s=0.005):
    """precise_sleep_v5 纯时序测试 (无注入)。返回 jitters (ns)。"""
    from engine.precision import _get_compensator
    stop = threading.Event()
    comp = _get_compensator()

    # 预热
    for _ in range(30):
        precise_sleep_v5(interval_s, stop, comp)

    jitters = []
    for _ in range(n):
        start = qpc_now()
        precise_sleep_v5(interval_s, stop, comp)
        actual = qpc_now()
        # 目标: start + interval_s
        target_qpc = start + int(interval_s * QPC_FREQ)
        jitter_ns = ticks_to_ns(actual - target_qpc, QPC_FREQ)
        jitters.append(jitter_ns)
    return jitters


# ==============================================================================
# 测试 2: 含注入对比 (按键)
# ==============================================================================
def test_injection_standby(se, n=200, interval_s=0.005, vk=0x41, core=1):
    """standby 含注入测试 (A 键交替 down/up)。返回 (arrival, e2e, inject) (ns)。"""
    interval_ns = int(interval_s * 1e9)
    events = []
    for i in range(n):
        offset_ns = (i + 1) * interval_ns
        if i % 2 == 0:
            events.append((offset_ns, ACT_KEY_DOWN, vk, 0, 0))
        else:
            events.append((offset_ns, ACT_KEY_UP, vk, 0, 0))

    results = run_standby(se, events, core, use_interception=0, timeout_ms=int(n * interval_s * 1000 + 5000))
    qpc_freq = se.get_qpc_frequency()
    arrival, e2e, inject, _ = extract_jitters(results, qpc_freq)
    return arrival, e2e, inject


def test_injection_precise_sleep(n=200, interval_s=0.005, vk=0x41):
    """precise_sleep + SendInput 含注入测试。返回 (arrival, e2e, inject) (ns)。"""
    from engine.precision import _get_compensator
    stop = threading.Event()
    comp = _get_compensator()

    # 预热
    for _ in range(20):
        precise_sleep_v5(interval_s, stop, comp)

    arrival, e2e, inject = [], [], []
    interval_ns = int(interval_s * 1e9)

    start_qpc = qpc_now()
    for i in range(n):
        target_qpc = start_qpc + (i + 1) * interval_ns * QPC_FREQ // 1_000_000_000
        is_down = (i % 2 == 0)

        precise_sleep_v5(interval_s, stop, comp)
        actual_qpc = qpc_now()
        send_key_sendinput(vk, not is_down)
        inj_done_qpc = qpc_now()

        arrival.append(ticks_to_ns(actual_qpc - target_qpc, QPC_FREQ))
        e2e.append(ticks_to_ns(inj_done_qpc - target_qpc, QPC_FREQ))
        inject.append(ticks_to_ns(inj_done_qpc - actual_qpc, QPC_FREQ))
    return arrival, e2e, inject


# ==============================================================================
# 测试 3: RawInput 监听验证
# ==============================================================================
def test_rawinput_validation(se, n=100, interval_s=0.005, vk=0x41, standby_core=1, listen_core=0):
    """GetAsyncKeyState 轮询验证: 测量"注入到系统通知"延迟。

    standby 注入 n 个 A 键事件, AsyncKeyStatePoller 在另一个核自旋轮询捕获,
    对比 injection_done_qpc 与轮询捕获时间。
    """
    interval_ns = int(interval_s * 1e9)
    events = []
    for i in range(n):
        offset_ns = (i + 1) * interval_ns
        if i % 2 == 0:
            events.append((offset_ns, ACT_KEY_DOWN, vk, 0, 0))
        else:
            events.append((offset_ns, ACT_KEY_UP, vk, 0, 0))

    # 启动 AsyncKeyState 轮询监听 (纯自旋, 绑另一个核)
    poller = AsyncKeyStatePoller(vk)
    poller.start(listen_core)
    time.sleep(0.05)  # 等监听稳定

    # 执行 standby
    results = run_standby(se, events, standby_core, use_interception=0,
                          timeout_ms=int(n * interval_s * 1000 + 5000))

    # 停止监听
    poller.stop()

    raw_events = poller.get_events()
    qpc_freq = se.get_qpc_frequency()

    if not results or not raw_events:
        print(f"[AsyncKey验证] results={len(results)} captured={len(raw_events)} (数据不足)")
        return None

    # 提取 standby 的 key 事件 (按时间顺序)
    key_results = []
    for r in results:
        target_qpc, actual_qpc, inj_done_qpc, action_type, status = r
        if status == ST_SKIPPED:
            continue
        if action_type in (ACT_KEY_DOWN, ACT_KEY_UP):
            key_results.append((inj_done_qpc, action_type))

    # 按顺序匹配轮询事件
    # 轮询事件: (qpc, vk, is_down)
    # standby key 事件: (inj_done_qpc, action_type)  DOWN=1, UP=2
    latencies = []
    matched = 0
    raw_idx = 0
    for inj_done_qpc, atype in key_results:
        expected_down = (atype == ACT_KEY_DOWN)
        # 在 raw_events 中找下一个匹配的事件
        while raw_idx < len(raw_events):
            raw_qpc, raw_vk, raw_is_down = raw_events[raw_idx]
            raw_idx += 1
            if raw_is_down == expected_down:
                latency_ns = ticks_to_ns(raw_qpc - inj_done_qpc, qpc_freq)
                latencies.append(latency_ns)
                matched += 1
                break

    print(f"\n[AsyncKey验证] standby key 事件: {len(key_results)}, 轮询捕获: {len(raw_events)}, 匹配: {matched}")
    if matched < len(key_results):
        print(f"  [警告] 匹配数 {matched} < standby key 事件数 {len(key_results)} (可能部分事件未捕获)")

    return latencies


# ==============================================================================
# 测试 4: 大规模真实宏测试
# ==============================================================================
def build_real_macro_script(repeats=500):
    """构造包含所有动作类型的真实宏脚本。

    动作类型: 键盘按键 / 鼠标左键 / 鼠标右键 / wait / view / move_to / scroll
    用 A 键 (0x41), 鼠标移动用小位移 (dx=1) 避免光标跑飞。
    """
    single = [
        ["kd", "A", 2],              # 键盘按下
        ["ku", "A", 2],              # 键盘抬起
        ["md", "left", 2],           # 鼠标左键按下
        ["mu", "left", 2],           # 鼠标左键抬起
        ["md", "right", 2],          # 鼠标右键按下
        ["mu", "right", 2],          # 鼠标右键抬起
        ["wait", 2],                 # 等待
        ["view", [1, 0], 10],        # 鼠标相对移动 dx=1 dy=0
        ["move_to", 500, 500, 10],   # 鼠标绝对定位
        ["scroll", 120],             # 滚轮
    ]
    return [["loop", repeats, single]]


def test_real_macro_standby(se, repeats=500, core=1):
    """standby 执行真实宏, 返回 (arrival, e2e, inject, events_meta)。"""
    script = build_real_macro_script(repeats)
    events, meta = compile_macro_to_timeline(script)

    print(f"  编译: {len(events)} 个事件 (重复 {repeats} 次)")
    total_time_s = events[-1][0] / 1e9 if events else 0
    print(f"  预计总时长: {total_time_s:.2f}s")

    results = run_standby(se, events, core, use_interception=0,
                          timeout_ms=int(total_time_s * 1000 + 10000))
    qpc_freq = se.get_qpc_frequency()
    arrival, e2e, inject, _ = extract_jitters(results, qpc_freq)
    return arrival, e2e, inject, meta


def test_real_macro_precise_sleep(repeats=500):
    """precise_sleep 路径执行真实宏, 返回 (arrival, e2e, inject)。"""
    from engine.precision import _get_compensator
    script = build_real_macro_script(repeats)
    events, _ = compile_macro_to_timeline(script)

    print(f"  编译: {len(events)} 个事件 (重复 {repeats} 次)")
    total_time_s = events[-1][0] / 1e9 if events else 0
    print(f"  预计总时长: {total_time_s:.2f}s")

    stop = threading.Event()
    comp = _get_compensator()
    results = execute_via_precise_sleep(events, QPC_FREQ, stop, comp)

    arrival, e2e, inject, _ = extract_jitters(results, QPC_FREQ)
    return arrival, e2e, inject


# ==============================================================================
# 测试 5: 不同间隔扫描
# ==============================================================================
def test_sweep_intervals(se, intervals_ms=(1, 2, 5, 10, 50), n_per_interval=100, core=1):
    """扫描不同间隔下的 standby vs precise_sleep 抖动。"""
    print("\n" + "=" * 90)
    print(" 不同间隔下的抖动扫描 (standby vs precise_sleep, 纯时序无注入)")
    print("=" * 90)
    header = f"{'间隔(ms)':>8} | {'standby p50(ns)':>16} | {'standby p99(ns)':>16} | {'precise p50(ns)':>16} | {'precise p99(ns)':>16}"
    print(header)
    print("-" * 90)

    for interval_ms in intervals_ms:
        interval_s = interval_ms / 1000.0

        sb = test_pure_timing_standby(se, n=n_per_interval, interval_s=interval_s, core=core)
        sb_p50 = percentile(sb, 0.50) if sb else float("nan")
        sb_p99 = percentile(sb, 0.99) if sb else float("nan")

        ps = test_pure_timing_precise_sleep(n=n_per_interval, interval_s=interval_s)
        ps_p50 = percentile(ps, 0.50) if ps else float("nan")
        ps_p99 = percentile(ps, 0.99) if ps else float("nan")

        print(f"{interval_ms:>8.1f} | {sb_p50:>16.0f} | {sb_p99:>16.0f} | {ps_p50:>16.0f} | {ps_p99:>16.0f}")


# ==============================================================================
# 主程序
# ==============================================================================
def main():
    print("=" * 90)
    print(" Standby 引擎 vs 现有路径 精度对比测试 (ns 级)")
    print("=" * 90)

    # 提升进程/线程优先级
    boost_process_priority()
    boost_thread_priority()

    # 加载 standby 引擎
    try:
        import _standby_engine as se
        se.init()
    except Exception as e:
        print(f"[错误] 无法加载 _standby_engine: {e}")
        print("请先编译 C 扩展: python engine\\setup_standby.py build_ext --inplace")
        return

    qpc_freq = se.get_qpc_frequency()
    core = se.auto_pick_core()
    if core is None:
        core = 1
    ic_ok = bool(se.is_interception_available())

    print(f"\n[环境] QPC 频率: {qpc_freq} Hz  (1 tick = {1_000_000_000 // qpc_freq} ns)")
    print(f"[环境] 自动选定核心: CPU{core}")
    print(f"[环境] Interception: {'可用' if ic_ok else '不可用'}")
    print(f"[环境] Python: {sys.version.split()[0]}")

    # 监听线程绑另一个核
    listen_core = core - 1 if core > 0 else core + 1

    # 安全警告
    print("\n" + "!" * 90)
    print("! 测试将注入真实按键 (A 键) 和鼠标动作, 测试期间请勿操作键盘鼠标!")
    print(f"! standby 线程绑 CPU{core}, 监听线程绑 CPU{listen_core}")
    print("!" * 90)
    print("\n3 秒后开始测试...")
    for i in range(3, 0, -1):
        print(f"  {i}...", flush=True)
        time.sleep(1)

    # ===== 测试 1: 纯时序对比 (5ms 间隔) =====
    print("\n" + "=" * 90)
    print(" 测试 1: 纯时序精度对比 (无注入, 5ms 间隔, 300 样本)")
    print("=" * 90)

    print("\n[1a] 现有路径 precise_sleep_v5 ...")
    ps_pure = test_pure_timing_precise_sleep(n=300, interval_s=0.005)
    ps_pure_stats = stats_ns("precise_sleep_v5 纯时序 (arrival_jitter)", ps_pure)

    print("\n[1b] standby 引擎纯时序 ...")
    sb_pure = test_pure_timing_standby(se, n=300, interval_s=0.005, core=core)
    sb_pure_stats = stats_ns("standby 纯时序 (arrival_jitter)", sb_pure)

    # ===== 测试 2: 含注入对比 (5ms 间隔, 按键) =====
    print("\n" + "=" * 90)
    print(" 测试 2: 含注入精度对比 (A 键 SendInput, 5ms 间隔, 200 样本)")
    print("=" * 90)

    print("\n[2a] 现有路径 precise_sleep + send_key_sendinput ...")
    ps_arr, ps_e2e, ps_inj = test_injection_precise_sleep(n=200, interval_s=0.005, vk=0x41)
    ps_arr_stats = stats_ns("precise_sleep + 注入 (arrival_jitter)", ps_arr)
    ps_e2e_stats = stats_ns("precise_sleep + 注入 (e2e_jitter)", ps_e2e)
    ps_inj_stats = stats_ns("precise_sleep + 注入 (inject_cost)", ps_inj)

    print("\n[2b] standby 引擎含注入 ...")
    sb_arr, sb_e2e, sb_inj = test_injection_standby(se, n=200, interval_s=0.005, vk=0x41, core=core)
    sb_arr_stats = stats_ns("standby + 注入 (arrival_jitter)", sb_arr)
    sb_e2e_stats = stats_ns("standby + 注入 (e2e_jitter)", sb_e2e)
    sb_inj_stats = stats_ns("standby + 注入 (inject_cost)", sb_inj)

    # ===== 测试 3: RawInput 监听验证 =====
    print("\n" + "=" * 90)
    print(" 测试 3: RawInput 监听验证 (A 键, 5ms 间隔, 100 样本)")
    print("=" * 90)
    print("\n测量 standby injection_done_qpc → RawInput 捕获时间的延迟 (注入到系统通知)")

    raw_latencies = test_rawinput_validation(se, n=100, interval_s=0.005, vk=0x41,
                                             standby_core=core, listen_core=listen_core)
    if raw_latencies:
        raw_stats = stats_ns("RawInput 延迟 (injection_done → 系统通知)", raw_latencies)
    else:
        raw_stats = None
        print("[RawInput验证] 无数据 (可能 RawInput 未捕获到事件)")

    # ===== 测试 4: 大规模真实宏测试 =====
    print("\n" + "=" * 90)
    print(" 测试 4: 大规模真实宏测试 (500 次重复, 包含所有动作类型)")
    print("=" * 90)

    print("\n[4a] standby 引擎真实宏 ...")
    sb_m_arr, sb_m_e2e, sb_m_inj, _ = test_real_macro_standby(se, repeats=500, core=core)
    sb_m_arr_stats = stats_ns("standby 真实宏 (arrival_jitter)", sb_m_arr)
    sb_m_e2e_stats = stats_ns("standby 真实宏 (e2e_jitter)", sb_m_e2e)
    sb_m_inj_stats = stats_ns("standby 真实宏 (inject_cost)", sb_m_inj)

    print("\n[4b] precise_sleep 路径真实宏 ...")
    ps_m_arr, ps_m_e2e, ps_m_inj = test_real_macro_precise_sleep(repeats=500)
    ps_m_arr_stats = stats_ns("precise_sleep 真实宏 (arrival_jitter)", ps_m_arr)
    ps_m_e2e_stats = stats_ns("precise_sleep 真实宏 (e2e_jitter)", ps_m_e2e)
    ps_m_inj_stats = stats_ns("precise_sleep 真实宏 (inject_cost)", ps_m_inj)

    # ===== 测试 5: 不同间隔扫描 =====
    test_sweep_intervals(se, intervals_ms=(1, 2, 5, 10, 50), n_per_interval=100, core=core)

    # ===== 总结 =====
    print("\n" + "=" * 90)
    print(" 总结")
    print("=" * 90)

    print("\n--- 纯时序 (5ms, 无注入) ---")
    if sb_pure_stats and ps_pure_stats:
        print(f"  arrival p99:  standby={sb_pure_stats['p99']:.0f}ns  vs  precise={ps_pure_stats['p99']:.0f}ns")

    print("\n--- 含注入 (5ms, A 键) ---")
    if sb_e2e_stats and ps_e2e_stats:
        print(f"  e2e p99:      standby={sb_e2e_stats['p99']:.0f}ns  vs  precise={ps_e2e_stats['p99']:.0f}ns")
    if sb_inj_stats and ps_inj_stats:
        print(f"  inject p50:   standby={sb_inj_stats['p50']:.0f}ns  vs  precise={ps_inj_stats['p50']:.0f}ns")

    print("\n--- 真实宏 (500 次重复) ---")
    if sb_m_e2e_stats and ps_m_e2e_stats:
        print(f"  e2e p99:      standby={sb_m_e2e_stats['p99']:.0f}ns  vs  precise={ps_m_e2e_stats['p99']:.0f}ns")
    if sb_m_inj_stats and ps_m_inj_stats:
        print(f"  inject p50:   standby={sb_m_inj_stats['p50']:.0f}ns  vs  precise={ps_m_inj_stats['p50']:.0f}ns")

    if raw_stats:
        print(f"\n--- RawInput 验证 ---")
        print(f"  注入→系统通知 p99: {raw_stats['p99']:.0f}ns")

    # 验收标准
    print("\n--- 验收标准 ---")
    target_e2e_p99 = 3000  # ns = 3us
    if sb_e2e_stats:
        passed = sb_e2e_stats['p99'] < target_e2e_p99
        print(f"  standby 含注入 e2e p99 < {target_e2e_p99}ns (3us): "
              f"{'✓ 通过' if passed else '✗ 未通过'} (实际 {sb_e2e_stats['p99']:.0f}ns)")
    if sb_m_e2e_stats:
        passed = sb_m_e2e_stats['p99'] < target_e2e_p99
        print(f"  standby 真实宏 e2e p99 < {target_e2e_p99}ns (3us): "
              f"{'✓ 通过' if passed else '✗ 未通过'} (实际 {sb_m_e2e_stats['p99']:.0f}ns)")

    print("\n" + "=" * 90)


if __name__ == "__main__":
    main()
