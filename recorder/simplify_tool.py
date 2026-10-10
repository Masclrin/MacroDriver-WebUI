# -*- coding: utf-8 -*-
"""
离线轨迹化简/合并工具

能力：
1) 对未化简轨迹宏做离线化简
2) 将动作宏 + 轨迹宏按不变时间线合并
3) 可同时做“合并 + 化简”
4) 支持 // 与 /* */ 注释 JSON

使用方式：
- 直接修改下面的配置区并运行本脚本。
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from recorder.trajectory_lib import (
    ActionStamp,
    TrackSegment,
    TrackSimplifyConfig,
    compute_action_delay_ns_list,
    merge_and_simplify_tracks,
)


# ==============================================================================
# 用户配置
# ==============================================================================
MODE = "both"  # "simplify_track" | "merge" | "both"

TRACK_MACRO_PATH = "宏/录制宏/3d宏_仅轨迹.json"
ACTION_MACRO_PATH = "宏/录制宏/3d宏_仅按键.json"
OUTPUT_TRACK_SIMPLIFIED_PATH = "宏/录制宏/3d宏_轨迹化简.json"
OUTPUT_MERGED_PATH = "宏/录制宏/3d宏_离线合并.json"

# 场景预设: "fps" | "desktop" | "rpg3d" | "custom"
SCENE_PRESET = "rpg3d"

# custom 参数（当 SCENE_PRESET="custom" 时生效）
CUSTOM_CFG = TrackSimplifyConfig(
    enabled=True,
    pipeline=["intent", "rdp"],
    rdp_epsilon=1.2,
    intent_angle_threshold_deg=16.0,
    intent_speed_ratio_threshold=1.5,
    intent_min_dt_ms=1.0,
    sliding_window_size=5,
    merge_gap_ms=1.0,
    min_manhattan_after_simplify=0.001,
    allow_cross_action_merge=False,
    enable_action_delay_embedding=True,
    action_embed_delay_ms=0.2,
    action_embed_max_ratio_to_next_press=0.9,
)

ROUND_DELAY_MS_DIGITS = 3
ROUND_DURATION_MS_DIGITS = 3
ROUND_DELTA_DIGITS = 3


# ==============================================================================
# 注释 JSON 读取
# ==============================================================================
_COMMENT_PATTERN = re.compile(
    r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\\"])*"',
    re.DOTALL | re.MULTILINE,
)


def _remove_comments(json_text: str) -> str:
    def _replacer(match):
        s = match.group(0)
        return " " if s.startswith("/") else s

    return _COMMENT_PATTERN.sub(_replacer, json_text)


def load_macro(path: str) -> List[List]:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    cleaned = _remove_comments(raw)
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError(f"宏文件格式错误（应为列表）: {path}")
    return data


def save_macro(path: str, rows: Sequence[List]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    content = "[\n" + ",\n".join(f"    {json.dumps(r, ensure_ascii=False)}" for r in rows) + "\n]"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ==============================================================================
# 宏解析与构建
# ==============================================================================

def _ms_to_ns(ms: float) -> int:
    return int(max(0.0, float(ms)) * 1_000_000.0)


def _ns_to_ms(ns: int, digits: int = ROUND_DELAY_MS_DIGITS) -> float:
    return round(ns / 1_000_000.0, digits)


def _is_action_cmd(cmd: str) -> bool:
    return cmd in ("kd", "ku", "md", "mu")


@dataclass
class ParsedMacro:
    actions: List[ActionStamp]
    tracks: List[TrackSegment]


def parse_macro_to_events(rows: Sequence[List]) -> ParsedMacro:
    t_ns = 0
    actions: List[ActionStamp] = []
    tracks: List[TrackSegment] = []

    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        cmd = str(row[0]).lower()

        if cmd == "wait":
            t_ns += _ms_to_ns(float(row[1]))
            continue

        if cmd == "view":
            dx, dy = float(row[1][0]), float(row[1][1])
            dur_ns = _ms_to_ns(float(row[2]))
            if dur_ns > 0 and (abs(dx) > 0 or abs(dy) > 0):
                tracks.append(TrackSegment(start_ns=t_ns, end_ns=t_ns + dur_ns, dx=dx, dy=dy))
            t_ns += dur_ns
            continue

        if _is_action_cmd(cmd):
            key = str(row[1]) if len(row) >= 2 else ""
            delay_ms = float(row[2]) if len(row) >= 3 else 0.0
            actions.append(ActionStamp(ts_ns=t_ns, cmd=cmd, key=key))
            t_ns += _ms_to_ns(delay_ms)

    return ParsedMacro(actions=actions, tracks=tracks)


def _build_event_stream(
    actions: Sequence[ActionStamp],
    tracks: Sequence[TrackSegment],
    action_delay_ns_list: Optional[Sequence[int]] = None,
) -> List[Tuple[int, int, Dict]]:
    stream: List[Tuple[int, int, Dict]] = []

    for i, a in enumerate(actions):
        d_ns = 0
        if action_delay_ns_list is not None and i < len(action_delay_ns_list):
            d_ns = max(0, int(action_delay_ns_list[i]))
        stream.append((
            a.ts_ns,
            0,
            {
                "type": "action",
                "cmd": a.cmd,
                "key": a.key,
                "post_delay_ms": _ns_to_ms(d_ns, ROUND_DELAY_MS_DIGITS),
            },
        ))

    for tr in tracks:
        stream.append((
            tr.start_ns,
            1,
            {
                "type": "view",
                "start_ns": tr.start_ns,
                "end_ns": tr.end_ns,
                "dx": tr.dx,
                "dy": tr.dy,
            },
        ))

    stream.sort(key=lambda x: (x[0], x[1]))
    return stream


def _merge_wait_into_action_delay(rows: Sequence[List]) -> List[List]:
    out: List[List] = []
    for row in rows:
        if not row:
            continue
        if row[0] == "wait" and out and _is_action_cmd(str(out[-1][0])) and len(out[-1]) >= 3:
            out[-1][2] = round(float(out[-1][2]) + float(row[1]), ROUND_DELAY_MS_DIGITS)
            continue
        out.append(list(row))
    return out


def build_macro_from_events(
    actions: Sequence[ActionStamp],
    tracks: Sequence[TrackSegment],
    anchor_ns: int,
    action_delay_ns_list: Optional[Sequence[int]] = None,
) -> List[List]:
    stream = _build_event_stream(actions, tracks, action_delay_ns_list)
    rows: List[List] = []
    prev_ns = anchor_ns

    for ts, _, payload in stream:
        if ts > prev_ns:
            rows.append(["wait", _ns_to_ms(ts - prev_ns, ROUND_DELAY_MS_DIGITS)])

        if payload["type"] == "action":
            rows.append([payload["cmd"], payload["key"], payload.get("post_delay_ms", 0)])
            prev_ns = ts
        else:
            dur_ns = max(0, int(payload["end_ns"] - payload["start_ns"]))
            dur_ms = _ns_to_ms(dur_ns, ROUND_DURATION_MS_DIGITS)
            dx = round(float(payload["dx"]), ROUND_DELTA_DIGITS)
            dy = round(float(payload["dy"]), ROUND_DELTA_DIGITS)
            if dur_ms > 0:
                if abs(dx) > 0 or abs(dy) > 0:
                    rows.append(["view", [dx, dy], dur_ms])
                else:
                    rows.append(["wait", dur_ms])
            prev_ns = int(payload["end_ns"])

    return _merge_wait_into_action_delay(rows)


# ==============================================================================
# 预设
# ==============================================================================

def get_preset_config(name: str) -> TrackSimplifyConfig:
    p = name.strip().lower()
    if p == "fps":
        return TrackSimplifyConfig(
            enabled=True,
            pipeline=["intent", "rdp"],
            rdp_epsilon=0.9,
            intent_angle_threshold_deg=14.0,
            intent_speed_ratio_threshold=1.4,
            intent_min_dt_ms=0.7,
            sliding_window_size=3,
            merge_gap_ms=0.5,
            min_manhattan_after_simplify=0.0005,
            allow_cross_action_merge=True,
            enable_action_delay_embedding=True,
            action_embed_delay_ms=0.15,
            action_embed_max_ratio_to_next_press=0.75,
        )
    if p == "desktop":
        return TrackSimplifyConfig(
            enabled=True,
            pipeline=["sliding_window", "rdp"],
            rdp_epsilon=2.2,
            intent_angle_threshold_deg=22.0,
            intent_speed_ratio_threshold=1.8,
            intent_min_dt_ms=1.2,
            sliding_window_size=7,
            merge_gap_ms=1.5,
            min_manhattan_after_simplify=0.002,
            allow_cross_action_merge=True,
            enable_action_delay_embedding=True,
            action_embed_delay_ms=0.35,
            action_embed_max_ratio_to_next_press=0.85,
        )
    if p == "rpg3d":
        return TrackSimplifyConfig(
            enabled=True,
            pipeline=["intent", "rdp"],
            rdp_epsilon=1.3,
            intent_angle_threshold_deg=17.0,
            intent_speed_ratio_threshold=1.5,
            intent_min_dt_ms=1.0,
            sliding_window_size=5,
            merge_gap_ms=1.0,
            min_manhattan_after_simplify=0.001,
            allow_cross_action_merge=True,
            enable_action_delay_embedding=True,
            action_embed_delay_ms=0.2,
            action_embed_max_ratio_to_next_press=0.85,
        )
    if p == "custom":
        return CUSTOM_CFG
    raise ValueError(f"未知场景预设: {name}")


# ==============================================================================
# 执行
# ==============================================================================

def run_simplify_track_only(cfg: TrackSimplifyConfig) -> None:
    rows = load_macro(TRACK_MACRO_PATH)
    parsed = parse_macro_to_events(rows)
    simplified = merge_and_simplify_tracks(parsed.tracks, [], cfg)
    anchor_ns = min((t.start_ns for t in simplified), default=0)
    out_rows = build_macro_from_events([], simplified, anchor_ns)
    save_macro(OUTPUT_TRACK_SIMPLIFIED_PATH, out_rows)
    print(f"[完成] 轨迹化简输出: {OUTPUT_TRACK_SIMPLIFIED_PATH} | 指令数={len(out_rows)}")


def run_merge_or_both(cfg: TrackSimplifyConfig, simplify_after_merge: bool) -> None:
    action_rows = load_macro(ACTION_MACRO_PATH)
    track_rows = load_macro(TRACK_MACRO_PATH)

    a = parse_macro_to_events(action_rows)
    t = parse_macro_to_events(track_rows)

    if simplify_after_merge:
        merged_tracks = merge_and_simplify_tracks(t.tracks, a.actions, cfg)
    else:
        cfg_no_simplify = TrackSimplifyConfig(
            enabled=False,
            pipeline=list(cfg.pipeline),
            rdp_epsilon=cfg.rdp_epsilon,
            intent_angle_threshold_deg=cfg.intent_angle_threshold_deg,
            intent_speed_ratio_threshold=cfg.intent_speed_ratio_threshold,
            intent_min_dt_ms=cfg.intent_min_dt_ms,
            sliding_window_size=cfg.sliding_window_size,
            merge_gap_ms=cfg.merge_gap_ms,
            min_manhattan_after_simplify=cfg.min_manhattan_after_simplify,
            allow_cross_action_merge=cfg.allow_cross_action_merge,
            enable_action_delay_embedding=cfg.enable_action_delay_embedding,
            action_embed_delay_ms=cfg.action_embed_delay_ms,
            action_embed_max_ratio_to_next_press=cfg.action_embed_max_ratio_to_next_press,
        )
        merged_tracks = merge_and_simplify_tracks(t.tracks, a.actions, cfg_no_simplify)

    action_delays = compute_action_delay_ns_list(a.actions, cfg)

    anchor_candidates = []
    if a.actions:
        anchor_candidates.append(min(x.ts_ns for x in a.actions))
    if merged_tracks:
        anchor_candidates.append(min(x.start_ns for x in merged_tracks))
    anchor_ns = min(anchor_candidates) if anchor_candidates else 0

    out_rows = build_macro_from_events(a.actions, merged_tracks, anchor_ns, action_delays)
    save_macro(OUTPUT_MERGED_PATH, out_rows)
    print(f"[完成] 合并输出: {OUTPUT_MERGED_PATH} | 指令数={len(out_rows)}")


def main() -> None:
    cfg = get_preset_config(SCENE_PRESET)

    mode = MODE.strip().lower()
    if mode == "simplify_track":
        run_simplify_track_only(cfg)
    elif mode == "merge":
        run_merge_or_both(cfg, simplify_after_merge=False)
    elif mode == "both":
        run_merge_or_both(cfg, simplify_after_merge=True)
    else:
        raise ValueError(f"未知 MODE: {MODE}")


if __name__ == "__main__":
    main()
