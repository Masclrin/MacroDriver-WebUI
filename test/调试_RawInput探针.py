#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Raw Input 探针 — 基于 HardwareEventProbe 方案的黑盒宏延迟测试

通过 Windows Raw Input API 监听实际到达系统的键盘事件，
使用 QueryPerformanceCounter 高精度计时，测量宏驱动的事件注入精度。

与 调试_宏延迟测试.py 的区别：
  - 调试_宏延迟测试.py：测量框架内部函数调用耗时（加载/编译/注入调用）
  - 本脚本：测量实际到达 OS Raw Input 层的事件精度（黑盒视角）

因此本脚本可以对比不同驱动（本项目的宏框架、雷蛇、罗技、XMouse 等）的宏执行精度。

用法:
  python 调试_RawInput探针.py --interval-ms 1 --events 500
  python 调试_RawInput探针.py --interval-ms 10 --events 500
  python 调试_RawInput探针.py --interval-ms 50 --events 500

工作流程:
  1. 终端 1: 运行本脚本，自动生成测试宏文件，开始监听 Raw Input
  2. 终端 2: 运行 运行测试宏.py 或通过 WebUI 触发宏
  3. 探针捕获事件后输出报告和 CSV
"""

import argparse
import ctypes
from ctypes import wintypes
import json
import math
import os
import signal
import statistics
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# Win32 API 类型与常量
# ============================================================

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
WM_QUIT = 0x0012
RIM_TYPEKEYBOARD = 1
RIM_TYPEMOUSE = 0
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_KEYBOARD = 0x06
HID_USAGE_GENERIC_MOUSE = 0x02
RI_KEY_BREAK = 0x0001

VK_F13 = 0x7C
VK_F14 = 0x7D

WND_CLASS_NAME = "RawInputProbeHidden"
WM_APP_QUIT = 0x8000  # 自定义退出消息

# ============================================================
# Win32 结构体
# ============================================================


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
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


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
        ("hCursor", wintypes.HICON),  # HCURSOR 与 HICON 同类型
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


# ============================================================
# Win32 函数原型
# ============================================================

WNDPROC_TYPE = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

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

user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = ctypes.c_longlong

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
user32.RegisterRawInputDevices.restype = wintypes.BOOL

user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, ctypes.POINTER(wintypes.UINT), wintypes.UINT]
user32.GetRawInputData.restype = wintypes.UINT

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

kernel32.QueryPerformanceCounter.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
kernel32.QueryPerformanceCounter.restype = wintypes.BOOL

kernel32.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
kernel32.QueryPerformanceFrequency.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

# ============================================================
# 统计工具
# ============================================================


def percentile(sorted_values: List[float], q: float) -> float:
    """从已排序列表中计算百分位数。"""
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = int(math.ceil(q * len(sorted_values))) - 1
    return sorted_values[max(0, min(index, len(sorted_values) - 1))]


def fmt_us(v: float) -> str:
    if math.isnan(v):
        return "nan"
    return f"{v:.3f}"


# ============================================================
# 宏文件生成
# ============================================================


def generate_test_macro(output_path: str, interval_ms: float, total_events: int) -> str:
    """生成 F13/F14 交替的测试宏文件。

    宏结构: 4 步循环（F13↓ → F14↓ → F13↑ → F14↑），每步间隔 interval_ms。
    loop_steps = 4，总循环数 = total_events // 4。
    """
    loop_steps = 4
    if total_events % loop_steps != 0:
        total_events = (total_events // loop_steps) * loop_steps
        print(f"[宏生成] 事件数调整为 {total_events}（必须是 4 的倍数）")

    loop_count = total_events // loop_steps
    interval_str = str(interval_ms)

    # 使用非标准 JSON 格式（带注释，与项目宏格式一致）
    lines = ["["]
    lines.append(f'    // 自动生成的 Raw Input 探针测试宏')
    lines.append(f'    // 按键: F13/F14 交替 | 间隔: {interval_ms}ms | 事件数: {total_events}')
    lines.append(f'    // 循环: {loop_count} 次 × 4 步 = {total_events} 事件')
    lines.append(f'    ["loop", {loop_count}, [')
    lines.append(f'        ["kd", "F13", {interval_str}],')
    lines.append(f'        ["kd", "F14", {interval_str}],')
    lines.append(f'        ["ku", "F13", {interval_str}],')
    lines.append(f'        ["ku", "F14", {interval_str}]')
    lines.append(f'    ]]')
    lines.append("]")

    content = "\n".join(lines) + "\n"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[宏生成] 已生成: {output_path}")
    print(f"          按键: F13/F14 交替 | 间隔: {interval_ms}ms | 事件数: {total_events}")
    print(f"          循环: {loop_count} 次 × 4 步 = {total_events} 事件")
    return output_path


# ============================================================
# 探针事件
# ============================================================


class ProbeEvent:
    __slots__ = ("index", "kind", "vkey", "state", "tick", "is_trigger")

    def __init__(self, index: int, kind: str, vkey: int, state: str, tick: int, is_trigger: bool = False):
        self.index = index
        self.kind = kind
        self.vkey = vkey
        self.state = state
        self.tick = tick
        self.is_trigger = is_trigger


# ============================================================
# Raw Input 探针核心
# ============================================================


class RawInputProbe:
    """Raw Input 键盘事件探针。

    创建隐藏窗口，注册 Raw Input 设备，监听键盘事件。
    过滤指定的虚拟键码（F13/F14），使用 QPC 计时。
    """

    def __init__(self, filter_vkeys: List[int], expected_events: int, loop_steps: int,
                 interval_us: float, analysis_skip_events: int, timeout_sec: float,
                 expected_timeline_us: Optional[List[float]] = None):
        self.filter_vkeys = set(filter_vkeys)
        self.expected_events = expected_events
        self.loop_steps = loop_steps
        self.interval_us = interval_us
        self.analysis_skip_events = analysis_skip_events
        self.timeout_sec = timeout_sec
        self.expected_timeline_us = expected_timeline_us  # 变间隔模式：预期间隔列表(微秒)

        # 事件存储
        self.all_events: List[ProbeEvent] = []
        self.macro_events: List[ProbeEvent] = []
        self._lock = threading.Lock()

        # 计时
        self.frequency: int = 0
        self.first_macro_tick: int = 0

        # 状态
        self._completed = threading.Event()
        self._stop_reason = ""
        self._window: Optional[int] = None
        self._wndproc_ref = None  # 保持回调引用防止 GC

    # ---- 窗口创建与消息泵 ----

    def _create_window(self) -> int:
        """创建隐藏的 Win32 消息窗口。"""
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
            raise OSError(f"RegisterClassExW 失败: {ctypes.get_last_error()}")

        hwnd = user32.CreateWindowExW(
            0, WND_CLASS_NAME, "RawInputProbe", 0,
            0, 0, 0, 0, None, None, hinstance, None,
        )
        if not hwnd:
            raise OSError(f"CreateWindowExW 失败: {ctypes.get_last_error()}")

        return hwnd

    def _register_raw_input(self) -> None:
        """注册 Raw Input 设备（键盘）。"""
        kbd = RAWINPUTDEVICE()
        kbd.usUsagePage = HID_USAGE_PAGE_GENERIC
        kbd.usUsage = HID_USAGE_GENERIC_KEYBOARD
        kbd.dwFlags = RIDEV_INPUTSINK
        kbd.hwndTarget = self._window

        devices = (RAWINPUTDEVICE * 1)(kbd)
        if not user32.RegisterRawInputDevices(devices, 1, ctypes.sizeof(RAWINPUTDEVICE)):
            err = ctypes.get_last_error()
            raise OSError(f"RegisterRawInputDevices 失败: {err}")
        print(f"[探针] Raw Input 注册成功 (RIDEV_INPUTSINK)，窗口句柄: {self._window}")
        print(f"[探针] 结构体大小: RAWINPUTHEADER={ctypes.sizeof(RAWINPUTHEADER)}, RAWKEYBOARD={ctypes.sizeof(RAWKEYBOARD)}, RAWINPUT={ctypes.sizeof(RAWINPUT)}")

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """窗口消息处理。"""
        if msg == WM_INPUT:
            self._process_raw_input(lparam)
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _process_raw_input(self, raw_input_handle) -> None:
        """处理单条 Raw Input 消息。"""
        if self._completed.is_set():
            return

        # 获取数据大小
        size = wintypes.UINT(0)
        header_size = ctypes.sizeof(RAWINPUTHEADER)
        ret1 = user32.GetRawInputData(raw_input_handle, RID_INPUT, None, ctypes.byref(size), header_size)
        if ret1 != 0 or size.value == 0:
            return

        # 分配缓冲区
        buffer = ctypes.create_string_buffer(size.value)
        written = user32.GetRawInputData(raw_input_handle, RID_INPUT, buffer, ctypes.byref(size), header_size)
        if written != size.value:
            return

        # 检查结构体大小，防止解析越界
        raw_size = ctypes.sizeof(RAWINPUT)
        if size.value < raw_size:
            return

        raw = ctypes.cast(buffer, ctypes.POINTER(RAWINPUT)).contents

        if raw.header.dwType == RIM_TYPEKEYBOARD:
            self._record_keyboard(raw.keyboard)
        # 忽略鼠标事件

    def _record_keyboard(self, kbd: RAWKEYBOARD) -> None:
        """记录键盘事件。"""
        vk = kbd.VKey
        # 应用过滤：如果设置了 filter_vkeys，则只接受匹配的 VK 码
        # 注意：Interception 驱动注入的事件 VK=0（内核级扫描码），也予以接受
        if self.filter_vkeys and vk != 0 and vk not in self.filter_vkeys:
            return

        # 获取高精度时间戳
        tick = ctypes.c_longlong(0)
        kernel32.QueryPerformanceCounter(ctypes.byref(tick))

        state = "up" if (kbd.Flags & RI_KEY_BREAK) else "down"

        with self._lock:
            idx = len(self.all_events)
            event = ProbeEvent(idx, "key", vk, state, tick.value, False)
            self.all_events.append(event)
            self.macro_events.append(event)

            if self.first_macro_tick == 0:
                self.first_macro_tick = tick.value

            if self.expected_events > 0 and len(self.macro_events) >= self.expected_events:
                self._stop_reason = f"达到预期事件数 ({self.expected_events})"
                self._completed.set()
                # 发送 WM_QUIT 让 GetMessageW 返回 0，退出消息循环
                user32.PostQuitMessage(0)

    # ---- 消息循环 ----

    def _message_loop(self) -> None:
        """运行消息泵线程。

        使用 GetMessageW 阻塞等待消息，确保 WM_INPUT 等发送消息能及时派发。
        """
        msg = MSG()
        while not self._completed.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:  # WM_QUIT
                break
            if ret == -1:  # 错误
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    # ---- 公开接口 ----

    def start(self) -> None:
        """启动探针（创建窗口、注册设备、启动消息泵）。"""
        # 获取 QPC 频率
        freq = ctypes.c_longlong(0)
        kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
        self.frequency = freq.value

        self._window = self._create_window()
        self._register_raw_input()

        print(f"[探针] 已启动，监听按键: {self._vk_list_str()}")
        print(f"[探针] QPC 频率: {self.frequency} Hz")
        print(f"[探针] 预期事件: {self.expected_events} | 循环步数: {self.loop_steps} | 预期间隔: {self.interval_us:.0f}us")
        print("[探针] 等待宏事件... (Ctrl+C 停止)")

        # 启动超时监控线程
        if self.timeout_sec > 0:
            t = threading.Thread(target=self._timeout_monitor, daemon=True)
            t.start()

        # 运行消息循环
        self._message_loop()

        # 清理
        if self._window:
            user32.DestroyWindow(self._window)
            self._window = None

    def stop(self, reason: str = "手动停止") -> None:
        """停止探针。"""
        self._stop_reason = reason
        self._completed.set()
        # 发送 WM_QUIT 让 GetMessageW 返回 0，退出消息循环
        user32.PostQuitMessage(0)

    def _vk_list_str(self) -> str:
        if not self.filter_vkeys:
            return "全部键盘事件"
        names = []
        for vk in sorted(self.filter_vkeys):
            if vk == VK_F13:
                names.append("F13")
            elif vk == VK_F14:
                names.append("F14")
            else:
                names.append(f"0x{vk:02X}")
        return ", ".join(names)

    def _timeout_monitor(self) -> None:
        """超时监控线程。"""
        deadline = time.monotonic() + self.timeout_sec
        while not self._completed.is_set():
            if time.monotonic() >= deadline:
                self.stop(f"超时 ({self.timeout_sec}s)")
                break
            time.sleep(0.1)

    # ---- 报告生成 ----

    def generate_report(self) -> str:
        """生成与 HardwareEventProbe 一致的报告。"""
        with self._lock:
            all_events = list(self.all_events)
            macro_events = list(self.macro_events)

        freq = self.frequency
        if freq == 0:
            return "QPC 频率未初始化，无法生成报告。"

        def to_us(ticks: float) -> float:
            return ticks * 1_000_000.0 / freq

        lines = []
        lines.append(f"StopReason: {self._stop_reason}")
        dropped = len(macro_events) - self.expected_events
        lines.append(f"capturedEvents={len(all_events)} macroEvents={len(macro_events)} "
                     f"expectedEvents={self.expected_events} droppedOrExtraEvents={dropped}")

        has_expected = self.expected_events > 0
        capture_complete = not has_expected or len(macro_events) >= self.expected_events
        completeness = (len(macro_events) * 100.0 / self.expected_events) if has_expected else 100.0
        lines.append(f"captureComplete={str(capture_complete).lower()} captureCompleteness={completeness:.3f}% "
                     f"completeLoops={len(macro_events) // self.loop_steps} "
                     f"partialLoopEvents={len(macro_events) % self.loop_steps}")

        # 分析跳过事件
        skip = min(self.analysis_skip_events, len(macro_events))
        metric_events = macro_events[skip:]
        lines.append(f"analysisSkipEvents={skip} metricEvents={len(metric_events)} "
                     f"metricCompleteLoops={len(metric_events) // self.loop_steps} "
                     f"metricPartialLoopEvents={len(metric_events) % self.loop_steps}")

        # 启动延迟
        startup = "unavailable"
        if self.first_macro_tick > 0 and metric_events:
            startup = f"{to_us(metric_events[0].tick - self.first_macro_tick):.3f}us"
        lines.append(f"StartupLatency={startup}")

        if len(metric_events) < 2:
            lines.append("Not enough macro events for cadence metrics.")
            return "\n".join(lines)

        use_variable_intervals = self.expected_timeline_us is not None

        # ── 构建完整预期时间轴 ──
        if use_variable_intervals:
            # 变间隔模式：构建全局累积预期时间轴
            # full_cumulative_us[i] = 事件 i 的预期累积偏移量（从事件 0 开始）
            full_cumulative_us = [0.0]
            for d in self.expected_timeline_us:  # 使用所有延迟，非跳过第一个
                full_cumulative_us.append(full_cumulative_us[-1] + d)
            # metric_events 是跳过了前 skip 个事件后的子集
            expected_cumulative_us = full_cumulative_us[skip:skip + len(metric_events)]
        else:
            # 固定间隔模式
            interval_ticks = self.interval_us * freq / 1_000_000.0

        # 实际间隔
        actual_intervals = []
        interval_errors = []
        ref_interval = self.expected_timeline_us[skip] if use_variable_intervals else self.interval_us

        for i in range(1, len(metric_events)):
            actual = to_us(metric_events[i].tick - metric_events[i - 1].tick)
            actual_intervals.append(actual)
            if use_variable_intervals:
                # metric_events[i-1] ↔ metric_events[i] 对应 macro_events[skip+i-1] ↔ macro_events[skip+i]
                # 预期间隔是 expected_timeline_us[skip + i - 1]
                macro_idx = skip + i - 1
                expected_int = self.expected_timeline_us[macro_idx] if macro_idx < len(self.expected_timeline_us) else ref_interval
                interval_errors.append(abs(actual - expected_int))
            else:
                interval_errors.append(abs(actual - self.interval_us))

        # 累积漂移（相对于全局理想时间轴）
        cumulative_drifts = []
        cumulative_drifts_signed = []  # 带符号的漂移，用于判断方向
        if capture_complete and has_expected and metric_events:
            first_tick = metric_events[0].tick
            for i, ev in enumerate(metric_events):
                if use_variable_intervals:
                    expected_offset_us = expected_cumulative_us[i] if i < len(expected_cumulative_us) else expected_cumulative_us[-1]
                    expected_offset_ticks = int(round(expected_offset_us * freq / 1_000_000.0))
                else:
                    expected_offset_ticks = int(round(interval_ticks * i))
                expected_tick = first_tick + expected_offset_ticks
                drift_us = to_us(ev.tick - expected_tick)
                cumulative_drifts.append(abs(drift_us))
                cumulative_drifts_signed.append(drift_us)

        # 循环内局部漂移（仅固定间隔模式）
        loop_local_drifts = []
        loop_end_local_drifts = []
        if not use_variable_intervals:
            complete_loops = len(metric_events) // self.loop_steps
            for loop_idx in range(complete_loops):
                loop_start_idx = loop_idx * self.loop_steps
                loop_start_tick = metric_events[loop_start_idx].tick
                for offset in range(self.loop_steps):
                    ev_idx = loop_start_idx + offset
                    expected_tick = loop_start_tick + int(round(interval_ticks * offset))
                    drift = abs(to_us(metric_events[ev_idx].tick - expected_tick))
                    loop_local_drifts.append(drift)
                    if offset == self.loop_steps - 1:
                        loop_end_local_drifts.append(drift)

        # 输出统计
        over_2ms = sum(1 for v in actual_intervals if v > 2000)
        over_5ms = sum(1 for v in actual_intervals if v > 5000)
        lines.append(f"actualIntervalUs {_format_range_stats(actual_intervals, 'actualIntervalMin', 'actualIntervalMax', 'actualIntervalRange')}")
        lines.append(f"intervalErrorUs {_format_range_stats(interval_errors, 'intervalErrorMin', 'intervalErrorMax', 'intervalErrorRange')}")
        lines.append(f"intervalThresholds over2msCount={over_2ms} over5msCount={over_5ms}")

        if capture_complete and has_expected and cumulative_drifts:
            lines.append(f"cumulativeDriftAbs {_format_stats(cumulative_drifts)}")
            # 带符号漂移统计：平均漂移方向
            mean_drift = sum(cumulative_drifts_signed) / len(cumulative_drifts_signed) if cumulative_drifts_signed else 0
            lines.append(f"cumulativeDriftSigned mean={mean_drift:.3f}us")
        else:
            lines.append("cumulativeDriftAbs skipped(incomplete capture)")

        if interval_errors:
            lines.append(f"intervalErrorAbs {_format_stats(interval_errors)}")
        if loop_local_drifts:
            lines.append(f"loopLocalDriftAbs {_format_stats(loop_local_drifts)}")
        if loop_end_local_drifts:
            lines.append(f"loopEndLocalDriftAbs {_format_stats(loop_end_local_drifts)}")

        return "\n".join(lines)

    def write_csv(self, path: str) -> None:
        """写入 CSV 事件追踪文件。"""
        with self._lock:
            all_events = list(self.all_events)
            macro_events = list(self.macro_events)
        freq = self.frequency

        def to_us(ticks):
            return ticks * 1_000_000.0 / freq

        use_variable_intervals = self.expected_timeline_us is not None
        first_tick = self.first_macro_tick if self.first_macro_tick else (all_events[0].tick if all_events else 0)

        # 变间隔模式：构建累积预期时间轴（full_cumulative_us[i] = 事件 i 的累积偏移）
        if use_variable_intervals:
            expected_cumulative_us = [0.0]
            for d in self.expected_timeline_us:
                expected_cumulative_us.append(expected_cumulative_us[-1] + d)

        interval_ticks = self.interval_us * freq / 1_000_000.0

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        macro_idx = 0
        with open(path, "w", encoding="utf-8", newline="") as f:
            if use_variable_intervals:
                f.write("index,kind,code,state,isTrigger,tick,relativeUs,stepIndex,expectedDueUs,cumulativeDriftUs\n")
            else:
                f.write("index,kind,code,state,isTrigger,tick,relativeUs,loopIndex,loopOffset,localDueUs,localDriftUs,cumulativeDueUs,cumulativeDriftUs\n")
            for ev in all_events:
                relative = to_us(ev.tick - first_tick)
                loop_idx_str = ""
                loop_offset_str = ""
                local_due = ""
                local_drift = ""
                cum_due = ""
                cum_drift = ""

                if macro_idx < len(macro_events) and ev is macro_events[macro_idx]:
                    if use_variable_intervals:
                        expected_offset_us = expected_cumulative_us[macro_idx] if macro_idx < len(expected_cumulative_us) else 0.0
                        expected_offset_ticks = int(round(expected_offset_us * freq / 1_000_000.0))
                        cum_due_tick = first_tick + expected_offset_ticks
                        drift_us = to_us(ev.tick - cum_due_tick)
                        loop_idx_str = str(macro_idx)
                        cum_due = f"{expected_offset_us:.3f}"
                        cum_drift = f"{drift_us:.3f}"
                    else:
                        li = macro_idx // self.loop_steps
                        lo = macro_idx % self.loop_steps
                        loop_start_tick = macro_events[li * self.loop_steps].tick
                        local_due_tick = loop_start_tick + int(round(interval_ticks * lo))
                        cum_due_tick = first_tick + int(round(interval_ticks * macro_idx))

                        loop_idx_str = str(li)
                        loop_offset_str = str(lo)
                        local_due = f"{self.interval_us * lo:.3f}"
                        local_drift = f"{to_us(ev.tick - local_due_tick):.3f}"
                        cum_due = f"{self.interval_us * macro_idx:.3f}"
                        cum_drift = f"{to_us(ev.tick - cum_due_tick):.3f}"
                    macro_idx += 1

                if use_variable_intervals:
                    f.write(f"{ev.index},{ev.kind},{ev.vkey},{ev.state},"
                            f"{'true' if ev.is_trigger else 'false'},"
                            f"{ev.tick},{relative:.3f},"
                            f"{loop_idx_str},{cum_due},{cum_drift}\n")
                else:
                    f.write(f"{ev.index},{ev.kind},{ev.vkey},{ev.state},"
                            f"{'true' if ev.is_trigger else 'false'},"
                            f"{ev.tick},{relative:.3f},"
                            f"{loop_idx_str},{loop_offset_str},"
                            f"{local_due},{local_drift},"
                            f"{cum_due},{cum_drift}\n")


# ============================================================
# 统计格式化
# ============================================================


def _format_stats(values: List[float]) -> str:
    if not values:
        return "count=0"
    s = sorted(values)
    p50 = percentile(s, 0.50)
    p95 = percentile(s, 0.95)
    p99 = percentile(s, 0.99)
    p999 = percentile(s, 0.999)
    return f"count={len(s)} p50={p50:.3f}us p95={p95:.3f}us p99={p99:.3f}us p99.9={p999:.3f}us max={s[-1]:.3f}us"


def _format_range_stats(values: List[float], min_name: str, max_name: str, range_name: str) -> str:
    if not values:
        return f"count=0 {min_name}=unavailable {max_name}=unavailable {range_name}=unavailable"
    s = sorted(values)
    mn = s[0]
    mx = s[-1]
    p50 = percentile(s, 0.50)
    p95 = percentile(s, 0.95)
    p99 = percentile(s, 0.99)
    p999 = percentile(s, 0.999)
    return (f"count={len(s)} {min_name}={mn:.3f}us {max_name}={mx:.3f}us "
            f"{range_name}={mx - mn:.3f}us p50={p50:.3f}us p95={p95:.3f}us "
            f"p99={p99:.3f}us p99.9={p999:.3f}us")


# ============================================================
# 主程序
# ============================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Raw Input 探针 — 黑盒宏延迟测试（基于 HardwareEventProbe 方案）",
    )
    parser.add_argument("--interval-ms", type=float, default=1.0,
                        help="事件间预期间隔（毫秒），默认 1.0")
    parser.add_argument("--events", type=int, default=500,
                        help="预期捕获的事件数（默认 500，必须是 4 的倍数）")
    parser.add_argument("--filter-vk", type=str, default="",
                        help="过滤的虚拟键码，逗号分隔，如 F13,F14（默认空=接受所有键盘事件）")
    parser.add_argument("--analysis-skip-events", type=int, default=4,
                        help="跳过前 N 个事件不参与指标统计（默认 4，跳过首循环预热）")
    parser.add_argument("--timeout-sec", type=float, default=60.0,
                        help="超时秒数（默认 60）")
    parser.add_argument("--csv", type=str, default=None,
                        help="CSV 输出路径（默认自动生成到 test/artifacts/）")
    parser.add_argument("--macro-output", type=str, default=None,
                        help="生成的宏文件路径（默认 test/宏/RawInput探针测试宏.json）")
    parser.add_argument("--no-generate-macro", action="store_true",
                        help="不自动生成宏文件")
    parser.add_argument("--expected-timeline", type=str, default=None,
                        help="变间隔模式：预期时间轴 JSON 文件（预期间隔列表，微秒）")
    args = parser.parse_args()

    # 加载预期时间轴（变间隔模式）
    expected_timeline_us = None
    if args.expected_timeline:
        with open(args.expected_timeline, "r", encoding="utf-8") as f:
            raw = json.load(f)
        expected_timeline_us = [float(v) for v in raw]
        total_events = len(expected_timeline_us)
        interval_us = expected_timeline_us[0] if expected_timeline_us else 1000.0
        loop_steps = 1  # 变间隔模式：每步独立，无循环结构
        print(f"[探针] 已加载预期时间轴: {len(expected_timeline_us)} 步")
        print(f"        最小间隔: {min(expected_timeline_us):.1f}us / "
              f"最大间隔: {max(expected_timeline_us):.1f}us / "
              f"总时长: {sum(expected_timeline_us)/1e6:.3f}s")
    else:
        # 计算参数（固定间隔模式）
        loop_steps = 4  # F13↓, F14↓, F13↑, F14↑
        total_events = args.events
        if total_events % loop_steps != 0:
            total_events = (total_events // loop_steps) * loop_steps
            if total_events == 0:
                total_events = loop_steps
            print(f"[警告] 事件数调整为 {total_events}（必须是 {loop_steps} 的倍数）")

        interval_us = args.interval_ms * 1000.0

    # 解析过滤键
    filter_vkeys = []
    if args.filter_vk:
        for token in args.filter_vk.split(","):
            token = token.strip().upper()
            if token == "F13":
                filter_vkeys.append(VK_F13)
            elif token == "F14":
                filter_vkeys.append(VK_F14)
            else:
                try:
                    filter_vkeys.append(int(token, 0))
                except ValueError:
                    print(f"[警告] 无法解析虚拟键码: {token}")

    if not filter_vkeys:
        print("[探针] 未设置过滤键，将接受所有键盘事件（VK=0的Interception事件也会被捕获）")

    # 确定路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    macro_path = args.macro_output or os.path.join(project_dir, "宏", "RawInput探针测试宏.json")
    csv_path = args.csv or os.path.join(script_dir, "artifacts", f"rawinput_probe_{int(args.interval_ms)}ms.csv")

    # 生成宏文件
    if not args.no_generate_macro:
        generate_test_macro(macro_path, args.interval_ms, total_events)

    print()
    print("=" * 60)
    print("Raw Input 探针 — 宏延迟测试")
    print(f"按键: {args.filter_vk} | 间隔: {args.interval_ms}ms | 事件: {total_events}")
    print(f"循环步数: {loop_steps} | 跳过分析: {args.analysis_skip_events} 事件")
    print(f"CSV: {csv_path}")
    print("=" * 60)
    print()
    print("请在新终端中运行以下命令来执行测试宏：")
    print(f"  cd \"{script_dir}\"")
    print(f"  python 运行测试宏.py --interval-ms {args.interval_ms} --events {total_events}")
    print()

    # 创建探针
    probe = RawInputProbe(
        filter_vkeys=filter_vkeys,
        expected_events=total_events,
        loop_steps=loop_steps,
        interval_us=interval_us,
        analysis_skip_events=args.analysis_skip_events,
        timeout_sec=args.timeout_sec,
        expected_timeline_us=expected_timeline_us,
    )

    # 处理 Ctrl+C
    def on_ctrl_c(sig, frame):
        print("\n[探针] 收到中断信号，正在停止...")
        probe.stop("用户中断 (Ctrl+C)")

    signal.signal(signal.SIGINT, on_ctrl_c)

    try:
        probe.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[探针] 错误: {e}")
        return

    # 输出报告
    print()
    report = probe.generate_report()
    print(report)

    # 写入 CSV
    probe.write_csv(csv_path)
    print(f"\nCSV 已保存: {csv_path}")

    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()