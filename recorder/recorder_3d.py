# -*- coding: utf-8 -*-
"""
[3D游戏高精度宏录制器] - V2.0

设计目标：
1. 鼠标轨迹按 Delta 精确录制（不依赖屏幕绝对位置），支持可调采样间隔。
2. 键鼠动作与轨迹分流录制，可独立开关，也可统一时间线合并输出。
3. 支持两种启动模式：
   - delayed: 按录制键后等待 X 秒开始
   - first_event: 从第一个可录制动作开始（剔除此前延迟/轨迹）
4. 默认不做轨迹化简；提供独立开关启用轨迹宏合并。
5. 输出 3 份文件：完整 / 仅按键动作 / 仅轨迹。

兼容输出格式：
- ["kd", "w", delay_ms]
- ["ku", "w", delay_ms]
- ["md", "left", delay_ms]
- ["mu", "left", delay_ms]
- ["view", [dx, dy], duration_ms]
- ["wait", delay_ms]
"""

import ctypes
import json
import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import psutil
from pynput import keyboard, mouse
from recorder.trajectory_lib import (
    ActionStamp,
    TrackSegment,
    TrackSimplifyConfig,
    compute_action_delay_ns_list,
    merge_and_simplify_tracks,
)


# ==============================================================================
# 录制热键与文件配置
# ==============================================================================
ENABLE_RECORD_HOTKEY_ACTIONS = False
RECORD_TOGGLE_LISTENER_HOTKEY = "不可使用！"
RECORD_ARM_HOTKEY = "f7"
RECORD_STOP_HOTKEY = "f8"
RECORD_SAVE_HOTKEY = "f9"
RECORD_CLEAR_HOTKEY = "f10"

# 基础输出名（不带后缀），最终会自动生成：
# <base>_完整.json / <base>_仅按键.json / <base>_仅轨迹.json
OUTPUT_DIR = "宏/录制宏"
OUTPUT_BASE_NAME = "3d宏"

SUFFIX_FULL = "_完整"
SUFFIX_ACTION = "_仅按键"
SUFFIX_TRACK = "_仅轨迹"


# ==============================================================================
# 录制行为开关
# ==============================================================================
ENABLE_RECORD_ACTIONS = True      # 录制键盘 + 鼠标按键（左右/中键）
ENABLE_RECORD_TRACK = True        # 录制鼠标移动轨迹（view）

# 启动模式: "delayed" | "first_event"（first_event将在delayed设定的延迟之后启动）
START_MODE = "delayed"
START_DELAY_SECONDS = 0.20

# 缓存时长（秒）: 仅保留最近 N 秒，避免超长录制占用内存
MAX_RECORD_SECONDS = 30.0

# 允许录制按键白名单
ENABLE_KEY_WHITELIST = False
ALLOWED_KEYS = {
    "w", "a", "s", "d",
    "1", "2", "3", "4", "5",
    "q", "e", "r", "f",
    "shift",
    "left", "right","space",
}


# ==============================================================================
# 鼠标采样与轨迹合并配置
# ==============================================================================
# 采样间隔（毫秒）:
# 0 或负值 = 每次 on_move 回调都记录（最高精度）
# > 0      = 以该间隔做降采样
MOUSE_SAMPLE_INTERVAL_MS = 0.0

# Delta 缩放（通常保持 1.0）
MOUSE_MOVE_SCALE = 1.0

# 轨迹自动化简（默认关闭）
ENABLE_TRACK_SIMPLIFY = False
# 可选: "rdp" / "intent" / "sliding_window"
# 也可复合，例如 ["sliding_window", "intent", "rdp"]
TRACK_SIMPLIFY_PIPELINE = ["sliding_window", "intent", "rdp"]

# 意图保留化简参数
SIMPLIFY_MIN_DURATION_MS = 1.0
SIMPLIFY_ANGLE_THRESHOLD_DEG = 20.0
SIMPLIFY_SPEED_RATIO_THRESHOLD = 1.6

# 滑动窗口滤波参数
SIMPLIFY_SLIDING_WINDOW_SIZE = 5

# RDP 几何化简参数
SIMPLIFY_RDP_EPSILON = 1.5

# 通用参数
SIMPLIFY_MERGE_GAP_MS = 0.8
SIMPLIFY_MIN_MANHATTAN = 0.001

# 动作并发执行场景: True 时允许跨动作边界统一化简；False 时按动作边界阻断合并
SIMPLIFY_ALLOW_CROSS_ACTION_MERGE = False

# 将动作之间的微小等待嵌入动作 delay（ms），并从轨迹时长中扣除同等时隙
ENABLE_ACTION_DELAY_EMBEDDING = True
ACTION_EMBED_DELAY_MS = 0.2
ACTION_EMBED_MAX_RATIO_TO_NEXT_PRESS = 0.9


# ==============================================================================
# 时间/数值精度与系统调度
# ==============================================================================
# 输出到 JSON 时的舍入位数（统一在此控制）
ROUND_DELAY_MS_DIGITS = 3  # wait/delay 的舍入位数
ROUND_DURATION_MS_DIGITS = 3  # view 的持续时间舍入位数
ROUND_DELTA_DIGITS = 3  # view 的 dx/dy 舍入位数
#sym:MIN_SPEED_PX_PER_SEC
MIN_SPEED_PX_PER_SEC = 10.0  # 录制阶段低速降噪阈值（像素/秒）

# 录制侧超低波动预设
ENABLE_ULTRA_LOW_JITTER_RECORD = True
ULTRA_LOW_JITTER_MOUSE_SAMPLE_INTERVAL_MS = 0.0
ULTRA_LOW_JITTER_DISABLE_LOW_SPEED_FILTER = True

BOOST_PROCESS_PRIORITY = True
BIND_CPU_CORE = -1  # -1 关闭绑核；>=0 绑定到指定核心


# ==============================================================================
# 数据结构
# ==============================================================================
@dataclass
class ActionEvent:
    ts_ns: int
    cmd: str   # kd/ku/md/mu
    key: str


@dataclass
class TrackEvent:
    start_ns: int
    end_ns: int
    dx: float
    dy: float


# ==============================================================================
# 全局状态
# ==============================================================================
action_events: Deque[ActionEvent] = deque()
track_events: Deque[TrackEvent] = deque()
state_lock = threading.Lock()

is_armed = False
is_recording = False
record_start_ns: Optional[int] = None
scheduled_start_ns: Optional[int] = None

stop_program = threading.Event()

# 鼠标轨迹采样状态
last_mouse_pos: Optional[Tuple[int, int]] = None
last_sample_ns: Optional[int] = None

# 热键按下去抖：同一按键长按导致系统重复 keydown 时仅处理一次。
_pressed_hotkeys: set[str] = set()


# ==============================================================================
# 基础工具
# ==============================================================================
def perf_ns() -> int:
    return time.perf_counter_ns()


def ns_to_ms(ns_value: int, digits: int = ROUND_DELAY_MS_DIGITS) -> float:
    return round(ns_value / 1_000_000.0, digits)


def to_rounded(value: float, digits: int) -> float:
    return round(float(value), digits)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def set_high_priority() -> None:
    try:
        if BOOST_PROCESS_PRIORITY:
            pid = ctypes.windll.kernel32.GetCurrentProcessId()
            handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, pid)
            if handle:
                ctypes.windll.kernel32.SetPriorityClass(handle, 0x00000080)

        ctypes.windll.winmm.timeBeginPeriod(1)

        if BIND_CPU_CORE >= 0:
            psutil.Process().cpu_affinity([BIND_CPU_CORE])

        print(f">>> [系统] 录制优先级已提升 | 绑核={BIND_CPU_CORE if BIND_CPU_CORE >= 0 else 'off'}")
    except Exception as exc:
        print(f">>> [警告] 提升优先级失败: {exc}")


def normalize_key_name(key) -> Optional[str]:
    if isinstance(key, keyboard.Key):
        return key.name
    if isinstance(key, keyboard.KeyCode):
        return key.char.lower() if key.char else None
    return None


def normalize_hotkey_name(hotkey) -> str:
    if hotkey is None:
        return ""
    if isinstance(hotkey, keyboard.Key):
        return str(hotkey.name or "").strip().lower()
    return str(hotkey).strip().lower()


def is_hotkey_match(key_name: Optional[str], configured_hotkey) -> bool:
    configured = normalize_hotkey_name(configured_hotkey)
    return bool(configured and key_name and key_name == configured)


def is_recordable_key(key_name: str) -> bool:
    if not key_name:
        return False
    if not ENABLE_KEY_WHITELIST:
        return True
    return key_name in ALLOWED_KEYS


def normalize_mouse_button(btn: mouse.Button) -> Optional[str]:
    if btn == mouse.Button.left:
        return "left"
    if btn == mouse.Button.right:
        return "right"
    if btn == mouse.Button.middle:
        return "middle"
    return None


def _trim_old_events(now_ns: int) -> None:
    if MAX_RECORD_SECONDS <= 0:
        return
    keep_after = now_ns - int(MAX_RECORD_SECONDS * 1_000_000_000)

    while action_events and action_events[0].ts_ns < keep_after:
        action_events.popleft()
    while track_events and track_events[0].end_ns < keep_after:
        track_events.popleft()


# ==============================================================================
# 录制状态机
# ==============================================================================
def _arm_recording(now_ns: int) -> None:
    global is_armed, is_recording, record_start_ns, scheduled_start_ns

    is_armed = True
    is_recording = False
    record_start_ns = None

    if START_MODE == "delayed":
        scheduled_start_ns = now_ns + int(max(0.0, START_DELAY_SECONDS) * 1_000_000_000)
        print(f">>> [状态] 已布防，{START_DELAY_SECONDS:.3f}s 后开始录制")
    elif START_MODE == "first_event":
        scheduled_start_ns = now_ns + int(max(0.0, START_DELAY_SECONDS) * 1_000_000_000)
        print(f">>> [状态] 已布防，将在{START_DELAY_SECONDS:.3f}s后的首个可录制事件触发起录")
    else:
        raise ValueError(f"未知 START_MODE: {START_MODE}")


def _stop_recording() -> None:
    global is_armed, is_recording, scheduled_start_ns
    was_active = bool(is_armed or is_recording or scheduled_start_ns is not None)
    is_armed = False
    is_recording = False
    scheduled_start_ns = None
    if was_active:
        print(">>> [状态] 已停止录制")


def _activate_recording_at(start_ns: int, reason: str) -> None:
    global is_recording, record_start_ns
    if is_recording:
        return
    is_recording = True
    record_start_ns = start_ns
    print(f">>> [状态] 开始录制 ({reason})")


def _try_activate_if_due(now_ns: int) -> None:
    if not is_armed or is_recording:
        return
    if START_MODE == "delayed" and scheduled_start_ns is not None and now_ns >= scheduled_start_ns:
        _activate_recording_at(scheduled_start_ns, "延时启动")


def _can_capture_event(now_ns: int, is_valid_event: bool) -> bool:
    """返回当前事件是否应写入缓冲，并在需要时触发起录。"""
    if not is_armed:
        return False

    _try_activate_if_due(now_ns)

    if is_recording:
        return True
    # 首事件触发起录（仅限延迟时间后的有效事件，便于用户切换窗口）
    if START_MODE == "first_event"and scheduled_start_ns is not None and now_ns >= scheduled_start_ns and is_valid_event:  
        _activate_recording_at(now_ns, "首事件启动")
        return True

    return False


# ==============================================================================
# 事件采集
# ==============================================================================
def on_key_press(key) -> Optional[bool]:
    try:
        now_ns = perf_ns()
        key_name = normalize_key_name(key)

        if ENABLE_RECORD_HOTKEY_ACTIONS:
            if is_hotkey_match(key_name, RECORD_ARM_HOTKEY):
                if key_name in _pressed_hotkeys:
                    return True
                _pressed_hotkeys.add(key_name)
                with state_lock:
                    if is_armed or is_recording:
                        _stop_recording()
                    else:
                        _arm_recording(now_ns)
                return True

            if is_hotkey_match(key_name, RECORD_STOP_HOTKEY):
                if key_name in _pressed_hotkeys:
                    return True
                _pressed_hotkeys.add(key_name)
                with state_lock:
                    if is_armed or is_recording:
                        _stop_recording()
                return True

            if is_hotkey_match(key_name, RECORD_SAVE_HOTKEY):
                if key_name in _pressed_hotkeys:
                    return True
                _pressed_hotkeys.add(key_name)
                with state_lock:
                    if is_armed or is_recording:
                        _stop_recording()
                process_and_save()
                return True

            if is_hotkey_match(key_name, RECORD_CLEAR_HOTKEY):
                if key_name in _pressed_hotkeys:
                    return True
                _pressed_hotkeys.add(key_name)
                with state_lock:
                    action_events.clear()
                    track_events.clear()
                    _stop_recording()
                print(">>> [状态] 已清空录制缓存")
                return True

            if is_hotkey_match(key_name, RECORD_TOGGLE_LISTENER_HOTKEY):
                if key_name in _pressed_hotkeys:
                    return True
                _pressed_hotkeys.add(key_name)
                stop_program.set()
                return False

        if not ENABLE_RECORD_ACTIONS or not key_name:
            return True
        if not is_recordable_key(key_name):
            return True

        with state_lock:
            if _can_capture_event(now_ns, is_valid_event=True):
                action_events.append(ActionEvent(ts_ns=now_ns, cmd="kd", key=key_name))
                _trim_old_events(now_ns)

        return True
    except Exception as exc:
        print(f">>> [键盘] on_press 出错: {exc}")
        return True


def on_key_release(key) -> Optional[bool]:
    try:
        now_ns = perf_ns()
        key_name = normalize_key_name(key)
        if key_name:
            _pressed_hotkeys.discard(key_name)
        if not ENABLE_RECORD_ACTIONS or not key_name:
            return True
        if not is_recordable_key(key_name):
            return True

        with state_lock:
            if _can_capture_event(now_ns, is_valid_event=True):
                action_events.append(ActionEvent(ts_ns=now_ns, cmd="ku", key=key_name))
                _trim_old_events(now_ns)

        return True
    except Exception as exc:
        print(f">>> [键盘] on_release 出错: {exc}")
        return True


def on_mouse_click(x: int, y: int, button: mouse.Button, pressed: bool) -> None:
    try:
        now_ns = perf_ns()
        btn_name = normalize_mouse_button(button)
        if not ENABLE_RECORD_ACTIONS or not btn_name:
            return
        if not is_recordable_key(btn_name):
            return

        cmd = "md" if pressed else "mu"

        with state_lock:
            if _can_capture_event(now_ns, is_valid_event=True):
                action_events.append(ActionEvent(ts_ns=now_ns, cmd=cmd, key=btn_name))
                _trim_old_events(now_ns)
    except Exception as exc:
        print(f">>> [鼠标] on_click 出错: {exc}")


def on_mouse_move(x: int, y: int) -> None:
    global last_mouse_pos, last_sample_ns

    try:
        now_ns = perf_ns()

        with state_lock:
            _try_activate_if_due(now_ns)

            if not ENABLE_RECORD_TRACK:
                last_mouse_pos = (x, y)
                last_sample_ns = now_ns
                return

            if last_mouse_pos is None:
                last_mouse_pos = (x, y)
                last_sample_ns = now_ns
                return

            if not _can_capture_event(now_ns, is_valid_event=False):
                last_mouse_pos = (x, y)
                last_sample_ns = now_ns
                return

            effective_sample_interval_ms = MOUSE_SAMPLE_INTERVAL_MS
            if ENABLE_ULTRA_LOW_JITTER_RECORD:
                effective_sample_interval_ms = ULTRA_LOW_JITTER_MOUSE_SAMPLE_INTERVAL_MS

            # 可调采样间隔: >0 时按固定间隔降采样；<=0 时逐回调记录。
            if effective_sample_interval_ms > 0 and last_sample_ns is not None:
                interval_ns = int(effective_sample_interval_ms * 1_000_000)
                if now_ns - last_sample_ns < interval_ns:
                    return

            dx = (x - last_mouse_pos[0]) * MOUSE_MOVE_SCALE
            dy = (y - last_mouse_pos[1]) * MOUSE_MOVE_SCALE

            start_ns = last_sample_ns if last_sample_ns is not None else now_ns
            end_ns = now_ns
            dur_ns = max(0, end_ns - start_ns)

            low_speed_filter_enabled = not ENABLE_ULTRA_LOW_JITTER_RECORD or not ULTRA_LOW_JITTER_DISABLE_LOW_SPEED_FILTER
            if dur_ns > 0 and low_speed_filter_enabled:
                speed = math.hypot(dx, dy) / (dur_ns / 1_000_000_000.0)
                if speed < MIN_SPEED_PX_PER_SEC:
                    last_mouse_pos = (x, y)
                    last_sample_ns = now_ns
                    return

            if abs(dx) > 0 or abs(dy) > 0:
                track_events.append(TrackEvent(start_ns=start_ns, end_ns=end_ns, dx=dx, dy=dy))
                _trim_old_events(now_ns)

            last_mouse_pos = (x, y)
            last_sample_ns = now_ns

    except Exception as exc:
        print(f">>> [鼠标] on_move 出错: {exc}")


# ==============================================================================
# 轨迹化简（默认不启用）
# ==============================================================================
def _angle_deg(dx: float, dy: float) -> float:
    import math
    return math.degrees(math.atan2(dy, dx))


def simplify_track_events(events: Sequence[TrackEvent]) -> List[TrackEvent]:
    if not events:
        return []

    merged: List[TrackEvent] = []

    def can_merge(a: TrackEvent, b: TrackEvent) -> bool:
        # 只合并相邻时间段，避免跨段吃掉中间动作。
        if b.start_ns < a.end_ns:
            return False
        gap_ms = (b.start_ns - a.end_ns) / 1_000_000.0
        if gap_ms > SIMPLIFY_MIN_DURATION_MS:
            return False

        manhattan_a = abs(a.dx) + abs(a.dy)
        manhattan_b = abs(b.dx) + abs(b.dy)
        if manhattan_a < SIMPLIFY_MIN_MANHATTAN and manhattan_b < SIMPLIFY_MIN_MANHATTAN:
            return True

        angle_a = _angle_deg(a.dx, a.dy)
        angle_b = _angle_deg(b.dx, b.dy)
        diff = abs(angle_a - angle_b)
        diff = 360.0 - diff if diff > 180.0 else diff
        return diff <= SIMPLIFY_ANGLE_THRESHOLD_DEG

    cur = events[0]
    for nxt in events[1:]:
        if can_merge(cur, nxt):
            # 合并时保留不变时间线的覆盖范围：start 不变、end 延展。
            cur = TrackEvent(
                start_ns=cur.start_ns,
                end_ns=nxt.end_ns,
                dx=cur.dx + nxt.dx,
                dy=cur.dy + nxt.dy,
            )
        else:
            merged.append(cur)
            cur = nxt
    merged.append(cur)
    return merged


# ==============================================================================
# 时间线合成
# ==============================================================================
def _split_tracks_by_actions(
    tracks: Sequence[TrackEvent],
    action_ts_list: Sequence[int],
) -> List[TrackEvent]:
    """
    将轨迹段按动作时间点切分，保证动作可插入轨迹中且时间线不变。
    使用线性比例切分 dx/dy，避免轨迹总位移损失。
    """
    if not tracks:
        return []

    action_ts_sorted = sorted(action_ts_list)
    result: List[TrackEvent] = []

    for tr in tracks:
        total_ns = tr.end_ns - tr.start_ns
        if total_ns <= 0:
            continue

        split_points = [tr.start_ns]
        for ts in action_ts_sorted:
            if tr.start_ns < ts < tr.end_ns:
                split_points.append(ts)
        split_points.append(tr.end_ns)

        split_points = sorted(set(split_points))
        if len(split_points) <= 1:
            continue

        remaining_dx = tr.dx
        remaining_dy = tr.dy
        remaining_ns = float(total_ns)

        for i in range(len(split_points) - 1):
            a = split_points[i]
            b = split_points[i + 1]
            seg_ns = b - a
            if seg_ns <= 0:
                continue

            if i == len(split_points) - 2:
                seg_dx = remaining_dx
                seg_dy = remaining_dy
            else:
                ratio = seg_ns / remaining_ns if remaining_ns > 0 else 0.0
                seg_dx = tr.dx * ratio
                seg_dy = tr.dy * ratio
                remaining_dx -= seg_dx
                remaining_dy -= seg_dy
                remaining_ns -= seg_ns

            if abs(seg_dx) > 0 or abs(seg_dy) > 0:
                result.append(TrackEvent(start_ns=a, end_ns=b, dx=seg_dx, dy=seg_dy))

    return result


def _build_event_stream(
    actions: Sequence[ActionEvent], tracks: Sequence[TrackEvent], action_delay_ns_list: Optional[Sequence[int]] = None
) -> List[Tuple[int, int, dict]]:
    """
    返回统一事件流: (start_ns, priority, payload)
    priority: 0=action, 1=view
    """
    stream: List[Tuple[int, int, dict]] = []

    for idx, a in enumerate(actions):
        delay_ns = 0
        if action_delay_ns_list is not None and idx < len(action_delay_ns_list):
            delay_ns = max(0, int(action_delay_ns_list[idx]))
        stream.append((
            a.ts_ns,
            0,
            {
                "type": "action",
                "cmd": a.cmd,
                "key": a.key,
                "post_delay_ms": ns_to_ms(delay_ns, ROUND_DELAY_MS_DIGITS),
            },
        ))

    for t in tracks:
        stream.append((t.start_ns, 1, {
            "type": "view",
            "start_ns": t.start_ns,
            "end_ns": t.end_ns,
            "dx": t.dx,
            "dy": t.dy,
        }))

    stream.sort(key=lambda item: (item[0], item[1]))
    return stream


def _append_wait(macro: List[List], wait_ms: float) -> None:
    if wait_ms <= 0:
        return
    macro.append(["wait", to_rounded(wait_ms, ROUND_DELAY_MS_DIGITS)])


def _is_action_cmd(cmd: str) -> bool:
    return cmd in ("kd", "ku", "md", "mu")


def _merge_wait_into_action_delay(macro: Sequence[List]) -> List[List]:
    merged: List[List] = []
    for row in macro:
        if not row:
            continue
        if row[0] == "wait" and merged and _is_action_cmd(str(merged[-1][0])) and len(merged[-1]) >= 3:
            merged[-1][2] = to_rounded(float(merged[-1][2]) + float(row[1]), ROUND_DELAY_MS_DIGITS)
            continue
        merged.append(list(row))
    return merged


def _merge_consecutive_waits(macro: Sequence[List]) -> List[List]:
    merged: List[List] = []
    pending_wait = 0.0

    for row in macro:
        if not row:
            continue
        if row[0] == "wait":
            pending_wait += float(row[1])
            continue

        if pending_wait > 0:
            merged.append(["wait", to_rounded(pending_wait, ROUND_DELAY_MS_DIGITS)])
            pending_wait = 0.0
        merged.append(list(row))

    if pending_wait > 0:
        merged.append(["wait", to_rounded(pending_wait, ROUND_DELAY_MS_DIGITS)])

    return merged


def _build_macro_from_stream(stream: Sequence[Tuple[int, int, dict]], anchor_ns: int) -> List[List]:
    macro: List[List] = []
    prev_ns = anchor_ns

    for start_ns, _, payload in stream:
        if start_ns > prev_ns:
            wait_ms = ns_to_ms(start_ns - prev_ns, ROUND_DELAY_MS_DIGITS)
            _append_wait(macro, wait_ms)

        if payload["type"] == "action":
            macro.append([payload["cmd"], payload["key"], payload.get("post_delay_ms", 0)])
            prev_ns = start_ns
        else:
            duration_ns = max(0, payload["end_ns"] - payload["start_ns"])
            duration_ms = ns_to_ms(duration_ns, ROUND_DURATION_MS_DIGITS)
            if duration_ms <= 0:
                prev_ns = payload["end_ns"]
                continue

            dx = to_rounded(payload["dx"], ROUND_DELTA_DIGITS)
            dy = to_rounded(payload["dy"], ROUND_DELTA_DIGITS)
            if abs(dx) <= 0 and abs(dy) <= 0:
                _append_wait(macro, duration_ms)
            else:
                macro.append(["view", [dx, dy], duration_ms])
            prev_ns = payload["end_ns"]

    return _merge_wait_into_action_delay(_merge_consecutive_waits(macro))


def build_output_macros(
    actions: Sequence[ActionEvent],
    tracks: Sequence[TrackEvent],
    anchor_override_ns: Optional[int] = None,
) -> Dict[str, List[List]]:
    if not actions and not tracks:
        return {"full": [], "action": [], "track": []}

    lib_cfg = TrackSimplifyConfig(
        enabled=ENABLE_TRACK_SIMPLIFY,
        pipeline=list(TRACK_SIMPLIFY_PIPELINE),
        rdp_epsilon=SIMPLIFY_RDP_EPSILON,
        intent_angle_threshold_deg=SIMPLIFY_ANGLE_THRESHOLD_DEG,
        intent_speed_ratio_threshold=SIMPLIFY_SPEED_RATIO_THRESHOLD,
        intent_min_dt_ms=SIMPLIFY_MIN_DURATION_MS,
        sliding_window_size=SIMPLIFY_SLIDING_WINDOW_SIZE,
        merge_gap_ms=SIMPLIFY_MERGE_GAP_MS,
        min_manhattan_after_simplify=SIMPLIFY_MIN_MANHATTAN,
        allow_cross_action_merge=SIMPLIFY_ALLOW_CROSS_ACTION_MERGE,
        enable_action_delay_embedding=ENABLE_ACTION_DELAY_EMBEDDING,
        action_embed_delay_ms=ACTION_EMBED_DELAY_MS,
        action_embed_max_ratio_to_next_press=ACTION_EMBED_MAX_RATIO_TO_NEXT_PRESS,
    )

    lib_tracks = [
        TrackSegment(start_ns=t.start_ns, end_ns=t.end_ns, dx=t.dx, dy=t.dy)
        for t in tracks
    ]
    lib_actions = [
        ActionStamp(ts_ns=a.ts_ns, cmd=a.cmd, key=a.key)
        for a in actions
    ]

    merged_tracks = merge_and_simplify_tracks(lib_tracks, lib_actions, config=lib_cfg)
    action_delay_ns_list = compute_action_delay_ns_list(lib_actions, lib_cfg)
    split_tracks = [
        TrackEvent(start_ns=t.start_ns, end_ns=t.end_ns, dx=t.dx, dy=t.dy)
        for t in merged_tracks
    ]

    anchor_candidates: List[int] = []
    if actions:
        anchor_candidates.append(min(a.ts_ns for a in actions))
    if split_tracks:
        anchor_candidates.append(min(t.start_ns for t in split_tracks))

    anchor_ns = min(anchor_candidates) if anchor_candidates else 0
    if anchor_override_ns is not None:
        # 保持不变化时间线：优先使用录制起点；但若缓存裁剪导致起点已被丢弃，则回退到现存最早事件。
        anchor_ns = max(anchor_override_ns, anchor_ns)

    full_stream = _build_event_stream(actions, split_tracks, action_delay_ns_list)
    action_stream = _build_event_stream(actions, [], action_delay_ns_list)
    track_stream = _build_event_stream([], split_tracks)

    full_macro = _build_macro_from_stream(full_stream, anchor_ns)
    action_macro = _build_macro_from_stream(action_stream, anchor_ns)
    track_macro = _build_macro_from_stream(track_stream, anchor_ns)

    return {
        "full": full_macro,
        "action": action_macro,
        "track": track_macro,
    }


# ==============================================================================
# 输出
# ==============================================================================
def _ensure_output_dir() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _macro_path(suffix: str) -> str:
    name = f"{OUTPUT_BASE_NAME}{suffix}.json"
    return os.path.join(OUTPUT_DIR, name)


def save_json_macro(path: str, macro: Sequence[List]) -> None:
    content = "[\n" + ",\n".join(f"    {json.dumps(row, ensure_ascii=False)}" for row in macro) + "\n]"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def process_and_save() -> None:
    with state_lock:
        actions_snapshot = list(action_events)
        tracks_snapshot = list(track_events)
        start_anchor_snapshot = record_start_ns

    if not actions_snapshot and not tracks_snapshot:
        print(">>> [保存] 无可用录制数据")
        return

    outputs = build_output_macros(
        actions_snapshot,
        tracks_snapshot,
        anchor_override_ns=start_anchor_snapshot,
    )

    _ensure_output_dir()
    path_full = _macro_path(SUFFIX_FULL)
    path_action = _macro_path(SUFFIX_ACTION)
    path_track = _macro_path(SUFFIX_TRACK)

    save_json_macro(path_full, outputs["full"])
    save_json_macro(path_action, outputs["action"])
    save_json_macro(path_track, outputs["track"])

    print(">>> [保存] 输出完成:")
    print(f"    - 完整宏: {path_full} | 指令数={len(outputs['full'])}")
    print(f"    - 仅按键: {path_action} | 指令数={len(outputs['action'])}")
    print(f"    - 仅轨迹: {path_track} | 指令数={len(outputs['track'])}")


# ==============================================================================
# 启动
# ==============================================================================
def main() -> None:
    if not is_admin():
        print(">>> [警告] 建议以管理员身份运行，以减少游戏内监听失败概率")

    set_high_priority()

    print("=" * 72)
    print("3D游戏高精度宏录制器 V2.0")
    print("=" * 72)
    if ENABLE_RECORD_HOTKEY_ACTIONS:
        print(
            "热键: "
            f"{normalize_hotkey_name(RECORD_ARM_HOTKEY)}=布防/停止 | "
            f"{normalize_hotkey_name(RECORD_STOP_HOTKEY)}=停止 | "
            f"{normalize_hotkey_name(RECORD_SAVE_HOTKEY)}=保存 | "
            f"{normalize_hotkey_name(RECORD_CLEAR_HOTKEY)}=清空 | "
            f"{normalize_hotkey_name(RECORD_TOGGLE_LISTENER_HOTKEY)}=退出"
        )
    else:
        print("热键动作: 已关闭（建议通过 WebUI 按钮控制录制，避免与执行监听冲突）")
    print(f"模式: START_MODE={START_MODE}, START_DELAY_SECONDS={START_DELAY_SECONDS}")
    print(f"录制开关: ACTIONS={ENABLE_RECORD_ACTIONS}, TRACK={ENABLE_RECORD_TRACK}")
    print(f"白名单: ENABLE_KEY_WHITELIST={ENABLE_KEY_WHITELIST}, keys={sorted(ALLOWED_KEYS)}")
    print(f"采样: MOUSE_SAMPLE_INTERVAL_MS={MOUSE_SAMPLE_INTERVAL_MS}")
    print(f"化简: ENABLE_TRACK_SIMPLIFY={ENABLE_TRACK_SIMPLIFY}, PIPELINE={TRACK_SIMPLIFY_PIPELINE}")
    print(
        f"化简参数: angle={SIMPLIFY_ANGLE_THRESHOLD_DEG}, "
        f"speed_ratio={SIMPLIFY_SPEED_RATIO_THRESHOLD}, "
        f"window={SIMPLIFY_SLIDING_WINDOW_SIZE}, rdp={SIMPLIFY_RDP_EPSILON}"
    )
    print(f"跨动作合并: {SIMPLIFY_ALLOW_CROSS_ACTION_MERGE} | 动作嵌入延迟: {ENABLE_ACTION_DELAY_EMBEDDING}")
    print(f"动作嵌入参数: delay_ms={ACTION_EMBED_DELAY_MS}, max_ratio_to_next_press={ACTION_EMBED_MAX_RATIO_TO_NEXT_PRESS}")
    print(f"录制降噪: MIN_SPEED_PX_PER_SEC={MIN_SPEED_PX_PER_SEC}")
    print(
        f"录制超低波动: ENABLE_ULTRA_LOW_JITTER_RECORD={ENABLE_ULTRA_LOW_JITTER_RECORD}, "
        f"sample_ms={ULTRA_LOW_JITTER_MOUSE_SAMPLE_INTERVAL_MS}, "
        f"disable_low_speed_filter={ULTRA_LOW_JITTER_DISABLE_LOW_SPEED_FILTER}"
    )
    print(f"舍入: delay_ms={ROUND_DELAY_MS_DIGITS}, duration_ms={ROUND_DURATION_MS_DIGITS}, delta={ROUND_DELTA_DIGITS}")
    print(f"缓存: MAX_RECORD_SECONDS={MAX_RECORD_SECONDS}")
    print("=" * 72)

    key_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    mouse_listener = mouse.Listener(on_click=on_mouse_click, on_move=on_mouse_move)

    key_listener.start()
    mouse_listener.start()

    try:
        stop_program.wait()
    except KeyboardInterrupt:
        pass
    finally:
        key_listener.stop()
        mouse_listener.stop()
        print(">>> [系统] 录制器已退出")


if __name__ == "__main__":
    main()
