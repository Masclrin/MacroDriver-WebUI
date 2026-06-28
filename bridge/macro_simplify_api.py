# -*- coding: utf-8 -*-
from __future__ import annotations

try:
    from macro_io.parser import macro_abs_from_rel
    _has_macro_io = True
except ImportError:
    _has_macro_io = False


class MacroSimplifyApiMixin:
    def _require_simplify_tool(self):
        if self.simplify_tool is None:
            raise RuntimeError("化简工具模块不可用")

    def simplify_macro_with_preset(self, input_rel_path: str, output_rel_path: str, preset: str = "rpg3d"):
        self._require_simplify_tool()
        if not _has_macro_io:
            return self._fail("宏文件模块不可用")
        try:
            in_path = macro_abs_from_rel(input_rel_path)
            out_path = macro_abs_from_rel(output_rel_path)
            if not in_path.exists():
                return self._fail("输入宏不存在")

            cfg = self.simplify_tool.get_preset_config(str(preset))
            rows = self.simplify_tool.load_macro(str(in_path))
            parsed = self.simplify_tool.parse_macro_to_events(rows)

            simplified_tracks = self.simplify_tool.merge_and_simplify_tracks(
                parsed.tracks,
                parsed.actions,
                config=cfg,
            )
            delays = self.simplify_tool.compute_action_delay_ns_list(parsed.actions, cfg)

            anchor_candidates = [a.ts_ns for a in parsed.actions] + [t.start_ns for t in parsed.tracks]
            anchor_ns = min(anchor_candidates) if anchor_candidates else 0

            out_rows = self.simplify_tool.build_macro_from_events(
                parsed.actions,
                simplified_tracks,
                anchor_ns=anchor_ns,
                action_delay_ns_list=delays,
            )

            out_path.parent.mkdir(parents=True, exist_ok=True)
            self.simplify_tool.save_macro(str(out_path), out_rows)

            return self._ok(path=out_path.relative_to(self.BASE_DIR).as_posix(), count=len(out_rows))
        except Exception as exc:
            return self._fail("轨迹化简失败", str(exc))

    def merge_action_track_with_preset(
        self,
        action_rel_path: str,
        track_rel_path: str,
        output_rel_path: str,
        preset: str = "rpg3d",
    ):
        self._require_simplify_tool()
        if not _has_macro_io:
            return self._fail("宏文件模块不可用")
        try:
            action_path = macro_abs_from_rel(action_rel_path)
            track_path = macro_abs_from_rel(track_rel_path)
            output_path = macro_abs_from_rel(output_rel_path)

            if not action_path.exists() or not track_path.exists():
                return self._fail("动作宏或轨迹宏不存在")

            cfg = self.simplify_tool.get_preset_config(str(preset))

            action_rows = self.simplify_tool.load_macro(str(action_path))
            track_rows = self.simplify_tool.load_macro(str(track_path))

            parsed_actions = self.simplify_tool.parse_macro_to_events(action_rows)
            parsed_tracks = self.simplify_tool.parse_macro_to_events(track_rows)

            actions = parsed_actions.actions
            tracks = parsed_tracks.tracks

            merged_tracks = self.simplify_tool.merge_and_simplify_tracks(tracks, actions, config=cfg)
            delays = self.simplify_tool.compute_action_delay_ns_list(actions, cfg)

            anchor_candidates = [a.ts_ns for a in actions] + [t.start_ns for t in merged_tracks]
            anchor_ns = min(anchor_candidates) if anchor_candidates else 0

            out_rows = self.simplify_tool.build_macro_from_events(
                actions,
                merged_tracks,
                anchor_ns=anchor_ns,
                action_delay_ns_list=delays,
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            self.simplify_tool.save_macro(str(output_path), out_rows)

            return self._ok(path=output_path.relative_to(self.BASE_DIR).as_posix(), count=len(out_rows))
        except Exception as exc:
            return self._fail("合并动作与轨迹失败", str(exc))
