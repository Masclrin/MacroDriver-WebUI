# -*- coding: utf-8 -*-
"""
轨迹化简与动作时间线合并库。

支持：
1. RDP 几何化简
2. 意图保留化简（转向/速度突变保留）
3. 滑动窗口滤波（平滑抖动）
4. 多策略可组合 pipeline
5. 独立上传轨迹与动作时间点，执行切分 + 化简 + 合并
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, degrees, hypot
from typing import Any, Dict, Iterable, List, Optional, Sequence


@dataclass
class TrackSegment:
    start_ns: int
    end_ns: int
    dx: float
    dy: float


@dataclass
class ActionStamp:
    ts_ns: int
    cmd: str = ""
    key: str = ""


@dataclass
class TrackSimplifyConfig:
    enabled: bool = False
    pipeline: List[str] = field(default_factory=lambda: ["intent"])

    # RDP 参数
    rdp_epsilon: float = 1.5

    # 意图保留参数
    intent_angle_threshold_deg: float = 20.0
    intent_speed_ratio_threshold: float = 1.6
    intent_min_dt_ms: float = 1.0

    # 滑动窗口滤波参数
    sliding_window_size: int = 5

    # 通用合并/清理参数
    merge_gap_ms: float = 0.8
    min_manhattan_after_simplify: float = 0.001

    # 动作与轨迹并发场景参数
    allow_cross_action_merge: bool = False
    enable_action_delay_embedding: bool = True
    action_embed_delay_ms: float = 0.2
    action_embed_max_ratio_to_next_press: float = 0.9


def normalize_track_segments(raw_tracks: Sequence[Any]) -> List[TrackSegment]:
    tracks: List[TrackSegment] = []
    for item in raw_tracks:
        if isinstance(item, TrackSegment):
            seg = item
        elif isinstance(item, dict):
            seg = TrackSegment(
                start_ns=int(item.get("start_ns", 0)),
                end_ns=int(item.get("end_ns", 0)),
                dx=float(item.get("dx", 0.0)),
                dy=float(item.get("dy", 0.0)),
            )
        else:
            seg = TrackSegment(
                start_ns=int(getattr(item, "start_ns")),
                end_ns=int(getattr(item, "end_ns")),
                dx=float(getattr(item, "dx")),
                dy=float(getattr(item, "dy")),
            )

        if seg.end_ns > seg.start_ns:
            tracks.append(seg)

    tracks.sort(key=lambda s: (s.start_ns, s.end_ns))
    return tracks


def normalize_action_stamps(raw_actions: Sequence[Any]) -> List[ActionStamp]:
    stamps: List[ActionStamp] = []
    for item in raw_actions:
        if isinstance(item, ActionStamp):
            act = item
        elif isinstance(item, dict):
            act = ActionStamp(
                ts_ns=int(item.get("ts_ns", item.get("start_ns", 0))),
                cmd=str(item.get("cmd", "")),
                key=str(item.get("key", "")),
            )
        else:
            act = ActionStamp(
                ts_ns=int(getattr(item, "ts_ns")),
                cmd=str(getattr(item, "cmd", "")),
                key=str(getattr(item, "key", "")),
            )

        stamps.append(act)

    stamps.sort(key=lambda a: a.ts_ns)
    return stamps


def compute_action_delay_ns_list(actions: Sequence[ActionStamp], cfg: TrackSimplifyConfig) -> List[int]:
    """计算每个动作建议的后置延迟（ns），用于将 wait 吸收进动作。"""
    if not actions:
        return []
    if not cfg.enable_action_delay_embedding:
        return [0 for _ in actions]

    delays: List[int] = []
    base_ns = max(0, int(cfg.action_embed_delay_ms * 1_000_000.0))

    next_press_idx = len(actions) - 1
    next_press_pos = [-1] * len(actions)
    for i in range(len(actions) - 1, -1, -1):
        if actions[i].cmd in ("kd", "md"):
            next_press_idx = i
        next_press_pos[i] = next_press_idx

    for i, act in enumerate(actions):
        delay_ns = base_ns
        j = next_press_pos[i + 1] if i + 1 < len(actions) else -1
        if j >= 0:
            gap_ns = actions[j].ts_ns - act.ts_ns
            cap_ns = int(max(0.0, gap_ns) * max(0.0, min(1.0, cfg.action_embed_max_ratio_to_next_press)))
            delay_ns = min(delay_ns, cap_ns)
        delays.append(max(0, delay_ns))
    return delays


def _slice_track_linear(tr: TrackSegment, a_ns: int, b_ns: int) -> Optional[TrackSegment]:
    total_ns = tr.end_ns - tr.start_ns
    if total_ns <= 0:
        return None
    a = max(tr.start_ns, min(a_ns, tr.end_ns))
    b = max(tr.start_ns, min(b_ns, tr.end_ns))
    if b <= a:
        return None
    ratio = (b - a) / float(total_ns)
    dx = tr.dx * ratio
    dy = tr.dy * ratio
    if abs(dx) <= 0 and abs(dy) <= 0:
        return None
    return TrackSegment(start_ns=a, end_ns=b, dx=dx, dy=dy)


def split_tracks_with_action_embedding(
    tracks: Sequence[TrackSegment],
    actions: Sequence[ActionStamp],
    cfg: TrackSimplifyConfig,
) -> List[TrackSegment]:
    """
    按动作时间线切分轨迹；若启用动作嵌入延迟，则在动作后挖去微小时间窗，
    便于后续把 wait 合并进动作 delay，同时保持时间线不变。
    """
    if not tracks:
        return []

    action_delays = compute_action_delay_ns_list(actions, cfg)
    action_events = [(a.ts_ns, d) for a, d in zip(actions, action_delays)]
    action_events.sort(key=lambda x: x[0])

    result: List[TrackSegment] = []
    for tr in tracks:
        cursor = tr.start_ns
        for ts, hole_ns in action_events:
            if ts <= cursor or ts >= tr.end_ns:
                continue

            left = _slice_track_linear(tr, cursor, ts)
            if left is not None:
                result.append(left)

            cursor = min(tr.end_ns, ts + max(0, hole_ns))
        tail = _slice_track_linear(tr, cursor, tr.end_ns)
        if tail is not None:
            result.append(tail)
    return result


def split_tracks_by_actions(tracks: Sequence[TrackSegment], action_ts: Sequence[int]) -> List[TrackSegment]:
    """按动作时间点切分轨迹，保证动作可插入轨迹且时间线不变。"""
    if not tracks:
        return []

    action_sorted = sorted(int(ts) for ts in action_ts)
    result: List[TrackSegment] = []

    for tr in tracks:
        total_ns = tr.end_ns - tr.start_ns
        if total_ns <= 0:
            continue

        points = [tr.start_ns]
        for ts in action_sorted:
            if tr.start_ns < ts < tr.end_ns:
                points.append(ts)
        points.append(tr.end_ns)
        points = sorted(set(points))

        if len(points) <= 1:
            continue

        remaining_dx = tr.dx
        remaining_dy = tr.dy
        remaining_ns = float(total_ns)

        for idx in range(len(points) - 1):
            a = points[idx]
            b = points[idx + 1]
            seg_ns = b - a
            if seg_ns <= 0:
                continue

            if idx == len(points) - 2:
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
                result.append(TrackSegment(start_ns=a, end_ns=b, dx=seg_dx, dy=seg_dy))

    return result


def _angle_deg(dx: float, dy: float) -> float:
    return degrees(atan2(dy, dx))


def _duration_ms(seg: TrackSegment) -> float:
    return max(0.0, (seg.end_ns - seg.start_ns) / 1_000_000.0)


def _speed(seg: TrackSegment) -> float:
    dt = max(1e-9, (seg.end_ns - seg.start_ns) / 1_000_000_000.0)
    return hypot(seg.dx, seg.dy) / dt


def _build_hard_boundary_set(action_ts: Sequence[int]) -> set[int]:
    return {int(ts) for ts in action_ts}


def _split_by_hard_boundaries(tracks: Sequence[TrackSegment], hard_boundaries: set[int]) -> List[List[TrackSegment]]:
    if not tracks:
        return []

    chunks: List[List[TrackSegment]] = []
    cur: List[TrackSegment] = [tracks[0]]

    for prev, nxt in zip(tracks, tracks[1:]):
        # 只要切点上有动作，就阻止跨界合并。
        if prev.end_ns in hard_boundaries or nxt.start_ns in hard_boundaries:
            chunks.append(cur)
            cur = [nxt]
        else:
            cur.append(nxt)

    chunks.append(cur)
    return chunks


def apply_sliding_window_filter(tracks: Sequence[TrackSegment], window_size: int) -> List[TrackSegment]:
    if len(tracks) <= 2:
        return list(tracks)

    w = max(1, int(window_size))
    if w % 2 == 0:
        w += 1
    if w <= 1:
        return list(tracks)

    half = w // 2
    out: List[TrackSegment] = []

    for i, seg in enumerate(tracks):
        lo = max(0, i - half)
        hi = min(len(tracks), i + half + 1)
        span = tracks[lo:hi]
        dx = sum(s.dx for s in span) / len(span)
        dy = sum(s.dy for s in span) / len(span)
        out.append(TrackSegment(start_ns=seg.start_ns, end_ns=seg.end_ns, dx=dx, dy=dy))

    return out


def apply_intent_preserve_simplify(
    tracks: Sequence[TrackSegment],
    angle_threshold_deg: float,
    speed_ratio_threshold: float,
    min_dt_ms: float,
    merge_gap_ms: float,
) -> List[TrackSegment]:
    if not tracks:
        return []

    merged: List[TrackSegment] = []
    cur = tracks[0]

    for nxt in tracks[1:]:
        gap_ms = (nxt.start_ns - cur.end_ns) / 1_000_000.0
        if gap_ms < 0 or gap_ms > merge_gap_ms:
            merged.append(cur)
            cur = nxt
            continue

        cur_dt_ms = _duration_ms(cur)
        nxt_dt_ms = _duration_ms(nxt)
        if cur_dt_ms < min_dt_ms or nxt_dt_ms < min_dt_ms:
            # 微小段优先吞并，减少噪点
            cur = TrackSegment(cur.start_ns, nxt.end_ns, cur.dx + nxt.dx, cur.dy + nxt.dy)
            continue

        a1 = _angle_deg(cur.dx, cur.dy)
        a2 = _angle_deg(nxt.dx, nxt.dy)
        ad = abs(a1 - a2)
        ad = 360.0 - ad if ad > 180.0 else ad

        s1 = max(1e-9, _speed(cur))
        s2 = max(1e-9, _speed(nxt))
        speed_ratio = max(s1, s2) / min(s1, s2)

        keep_corner = ad > angle_threshold_deg
        keep_speed_break = speed_ratio > speed_ratio_threshold

        if keep_corner or keep_speed_break:
            merged.append(cur)
            cur = nxt
        else:
            cur = TrackSegment(cur.start_ns, nxt.end_ns, cur.dx + nxt.dx, cur.dy + nxt.dy)

    merged.append(cur)
    return merged


def _point_line_distance_sq(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    vx = x2 - x1
    vy = y2 - y1
    wx = px - x1
    wy = py - y1

    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        dx = px - x1
        dy = py - y1
        return dx * dx + dy * dy

    t = (wx * vx + wy * vy) / denom
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * vx
    proj_y = y1 + t * vy
    dx = px - proj_x
    dy = py - proj_y
    return dx * dx + dy * dy


def _rdp_indices(points: Sequence[tuple[float, float]], epsilon: float) -> List[int]:
    if len(points) <= 2:
        return list(range(len(points)))

    eps2 = max(0.0, epsilon) ** 2
    keep = {0, len(points) - 1}

    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        x1, y1 = points[i]
        x2, y2 = points[j]

        max_dist = -1.0
        max_idx = -1
        for k in range(i + 1, j):
            px, py = points[k]
            d2 = _point_line_distance_sq(px, py, x1, y1, x2, y2)
            if d2 > max_dist:
                max_dist = d2
                max_idx = k

        if max_idx >= 0 and max_dist > eps2:
            keep.add(max_idx)
            stack.append((i, max_idx))
            stack.append((max_idx, j))

    return sorted(keep)


def apply_rdp_geometric_simplify(tracks: Sequence[TrackSegment], epsilon: float) -> List[TrackSegment]:
    if len(tracks) <= 2:
        return list(tracks)

    # 段 -> 折线点（相对坐标）
    points: List[tuple[float, float]] = [(0.0, 0.0)]
    point_ts: List[int] = [tracks[0].start_ns]

    x, y = 0.0, 0.0
    for seg in tracks:
        x += seg.dx
        y += seg.dy
        points.append((x, y))
        point_ts.append(seg.end_ns)

    keep_idx = _rdp_indices(points, epsilon)
    if len(keep_idx) <= 1:
        return list(tracks)

    out: List[TrackSegment] = []
    for i in range(len(keep_idx) - 1):
        a = keep_idx[i]
        b = keep_idx[i + 1]

        x1, y1 = points[a]
        x2, y2 = points[b]
        start_ns = point_ts[a]
        end_ns = point_ts[b]
        if end_ns <= start_ns:
            continue

        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) <= 0 and abs(dy) <= 0:
            continue

        out.append(TrackSegment(start_ns=start_ns, end_ns=end_ns, dx=dx, dy=dy))

    return out if out else list(tracks)


def _drop_tiny_segments(tracks: Iterable[TrackSegment], min_manhattan: float) -> List[TrackSegment]:
    return [
        t for t in tracks
        if (abs(t.dx) + abs(t.dy)) >= max(0.0, min_manhattan) and t.end_ns > t.start_ns
    ]


def simplify_tracks_pipeline(
    tracks: Sequence[TrackSegment],
    action_ts: Sequence[int],
    config: TrackSimplifyConfig,
) -> List[TrackSegment]:
    if not tracks:
        return []

    if not config.enabled:
        return _drop_tiny_segments(tracks, config.min_manhattan_after_simplify)

    if config.allow_cross_action_merge:
        chunks = [list(tracks)]
    else:
        hard_boundaries = _build_hard_boundary_set(action_ts)
        chunks = _split_by_hard_boundaries(tracks, hard_boundaries)
    result: List[TrackSegment] = []

    for chunk in chunks:
        cur = list(chunk)
        for step in config.pipeline:
            name = step.strip().lower()
            if not name:
                continue
            if name in ("sliding", "sliding_window", "window"):
                cur = apply_sliding_window_filter(cur, config.sliding_window_size)
            elif name in ("intent", "intent_preserve", "intent-preserve"):
                cur = apply_intent_preserve_simplify(
                    cur,
                    angle_threshold_deg=config.intent_angle_threshold_deg,
                    speed_ratio_threshold=config.intent_speed_ratio_threshold,
                    min_dt_ms=config.intent_min_dt_ms,
                    merge_gap_ms=config.merge_gap_ms,
                )
            elif name == "rdp":
                cur = apply_rdp_geometric_simplify(cur, config.rdp_epsilon)
            else:
                raise ValueError(f"未知轨迹化简步骤: {step}")

        result.extend(cur)

    result.sort(key=lambda t: (t.start_ns, t.end_ns))
    return _drop_tiny_segments(result, config.min_manhattan_after_simplify)


def merge_and_simplify_tracks(
    raw_tracks: Sequence[Any],
    raw_actions: Sequence[Any],
    config: Optional[TrackSimplifyConfig] = None,
) -> List[TrackSegment]:
    """
    外部入口：
    1) 接受外部轨迹/动作数据（dict、dataclass、具同名属性对象）
    2) 先按动作切分轨迹
    3) 再执行可组合化简 pipeline
    """
    cfg = config or TrackSimplifyConfig()
    tracks = normalize_track_segments(raw_tracks)
    actions = normalize_action_stamps(raw_actions)
    action_ts = [a.ts_ns for a in actions]

    split_tracks = split_tracks_with_action_embedding(tracks, actions, cfg)
    return simplify_tracks_pipeline(split_tracks, action_ts, cfg)


def simplify_and_merge_external_payload(
    payload: Dict[str, Any],
    config: Optional[TrackSimplifyConfig] = None,
) -> Dict[str, Any]:
    """
    外部数据接口示例：
    payload = {
        "tracks": [{"start_ns":..., "end_ns":..., "dx":..., "dy":...}, ...],
        "actions": [{"ts_ns":..., "cmd":"kd", "key":"w"}, ...]
    }
    """
    tracks_raw = payload.get("tracks", []) if isinstance(payload, dict) else []
    actions_raw = payload.get("actions", []) if isinstance(payload, dict) else []

    merged_tracks = merge_and_simplify_tracks(tracks_raw, actions_raw, config=config)
    return {
        "tracks": [
            {
                "start_ns": t.start_ns,
                "end_ns": t.end_ns,
                "dx": t.dx,
                "dy": t.dy,
            }
            for t in merged_tracks
        ],
        "meta": {
            "count": len(merged_tracks),
            "pipeline": (config.pipeline if config else TrackSimplifyConfig().pipeline),
            "enabled": (config.enabled if config else TrackSimplifyConfig().enabled),
        },
    }
