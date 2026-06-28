# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

RAZER_VK_CODE: dict[int, str] = {
    0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x10: "shift",
    0x11: "ctrl", 0x12: "alt", 0x13: "pause", 0x14: "caps_lock",
    0x1B: "esc", 0x20: "space",
    0x21: "page_up", 0x22: "page_down", 0x23: "end", 0x24: "home",
    0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
    0x2D: "insert", 0x2E: "delete",
    0x30: "0", 0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4",
    0x35: "5", 0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9",
    0x41: "a", 0x42: "b", 0x43: "c", 0x44: "d", 0x45: "e",
    0x46: "f", 0x47: "g", 0x48: "h", 0x49: "i", 0x4A: "j",
    0x4B: "k", 0x4C: "l", 0x4D: "m", 0x4E: "n", 0x4F: "o",
    0x50: "p", 0x51: "q", 0x52: "r", 0x53: "s", 0x54: "t",
    0x55: "u", 0x56: "v", 0x57: "w", 0x58: "x", 0x59: "y",
    0x5A: "z",
    0x5B: "lwin", 0x5C: "rwin",
    0x60: "numpad0", 0x61: "numpad1", 0x62: "numpad2", 0x63: "numpad3",
    0x64: "numpad4", 0x65: "numpad5", 0x66: "numpad6", 0x67: "numpad7",
    0x68: "numpad8", 0x69: "numpad9",
    0x6A: "multiply", 0x6B: "add", 0x6D: "subtract", 0x6E: "decimal", 0x6F: "divide",
    0x70: "f1", 0x71: "f2", 0x72: "f3", 0x73: "f4",
    0x74: "f5", 0x75: "f6", 0x76: "f7", 0x77: "f8",
    0x78: "f9", 0x79: "f10", 0x7A: "f11", 0x7B: "f12",
    0x90: "num_lock", 0x91: "scroll_lock",
    0xA0: "shift_l", 0xA1: "shift_r", 0xA2: "ctrl_l", 0xA3: "ctrl_r",
    0xA4: "alt_l", 0xA5: "alt_r",
    0xBA: "semicolon", 0xBB: "equals", 0xBC: "comma", 0xBD: "minus",
    0xBE: "period", 0xBF: "slash", 0xC0: "backtick",
    0xDB: "bracket_left", 0xDC: "backslash", 0xDD: "bracket_right",
    0xDE: "quote",
}

RAZER_MOUSE_BUTTON: dict[int, str] = {
    0: "left", 1: "right", 2: "middle",
}

LOGITECH_KEY_MAP: dict[str, str] = {
    "spacebar": "space",
    "capslock": "caps_lock",
    "lshift": "shift_l", "rshift": "shift_r",
    "lctrl": "ctrl_l", "rctrl": "ctrl_r",
    "lalt": "alt_l", "ralt": "alt_r",
    "uparrow": "up", "downarrow": "down",
    "leftarrow": "left", "rightarrow": "right",
    "pageup": "page_up", "pagedown": "page_down",
    "scrolllock": "scroll_lock", "numlock": "num_lock",
    "enter": "enter", "return": "enter",
    "tab": "tab", "esc": "esc", "escape": "esc",
    "backspace": "backspace", "delete": "delete",
    "insert": "insert", "home": "home", "end": "end",
}

AHK_SPECIAL_KEYS: dict[str, str] = {
    "enter": "enter", "tab": "tab", "space": "space",
    "esc": "esc", "escape": "esc", "backspace": "backspace",
    "delete": "delete", "insert": "insert",
    "home": "home", "end": "end",
    "pgup": "page_up", "pgdn": "page_down",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "ctrl": "ctrl", "shift": "shift", "alt": "alt",
    "lwin": "lwin", "rwin": "rwin",
    "lbutton": "__mouse_left", "rbutton": "__mouse_right", "mbutton": "__mouse_middle",
    "wheelup": "__scroll_up", "wheeldown": "__scroll_down",
}

AHK_MODIFIER_MAP: dict[str, str] = {
    "^": "ctrl", "+": "shift", "!": "alt", "#": "lwin",
}

XMBC_SPECIAL_KEYS: dict[str, str] = {
    "ENTER": "enter", "TAB": "tab", "ESC": "esc", "ESCAPE": "esc",
    "BACKSPACE": "backspace", "BACK": "backspace",
    "DELETE": "delete", "DEL": "delete",
    "INSERT": "insert", "INS": "insert",
    "HOME": "home", "END": "end",
    "PGUP": "page_up", "PGDN": "page_down",
    "UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right",
    "CTRL": "ctrl", "SHIFT": "shift", "ALT": "alt",
    "LWIN": "lwin", "RWIN": "rwin",
    "LCTRL": "ctrl_l", "RCTRL": "ctrl_r",
    "LSHIFT": "shift_l", "RSHIFT": "shift_r",
    "LALT": "alt_l", "RALT": "alt_r",
    "SPACE": "space",
    "CAPSLOCK": "caps_lock",
    "SCROLLLOCK": "scroll_lock", "NUMLOCK": "num_lock",
    "WHEELUP": "__scroll_up", "WHEELDOWN": "__scroll_down",
    "LBUTTON": "__mouse_left", "RBUTTON": "__mouse_right", "MBUTTON": "__mouse_middle",
    "LMB": "__mouse_left", "RMB": "__mouse_right", "MBB": "__mouse_middle",
    "NUMPAD0": "numpad_0", "NUMPAD1": "numpad_1", "NUMPAD2": "numpad_2",
    "NUMPAD3": "numpad_3", "NUMPAD4": "numpad_4", "NUMPAD5": "numpad_5",
    "NUMPAD6": "numpad_6", "NUMPAD7": "numpad_7", "NUMPAD8": "numpad_8",
    "NUMPAD9": "numpad_9",
}

EXT_FORMAT_MAP: dict[str, str] = {
    ".xml": "razer",
    ".lua": "logitech",
    ".ahk": "ahk",
    ".xmbcs": "xmouse",
    ".txt": "auto_content",
    "": "auto_content",
}

KEY_TO_RAZER_VK: dict[str, int] = {v: k for k, v in RAZER_VK_CODE.items()}
KEY_TO_RAZER_VK.update({
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12,
})

RAZER_MOUSE_NAME_TO_BUTTON: dict[str, int] = {v: k for k, v in RAZER_MOUSE_BUTTON.items()}

RAZER_VK_TO_SCAN: dict[int, int] = {
    0x08: 14, 0x09: 15, 0x0D: 28, 0x10: 42, 0x11: 29, 0x12: 56,
    0x14: 58, 0x1B: 1, 0x20: 57,
    0x30: 11, 0x31: 2, 0x32: 3, 0x33: 4, 0x34: 5,
    0x35: 6, 0x36: 7, 0x37: 8, 0x38: 9, 0x39: 10,
    0x41: 30, 0x42: 48, 0x43: 46, 0x44: 32, 0x45: 18,
    0x46: 33, 0x47: 34, 0x48: 35, 0x49: 23, 0x4A: 36,
    0x4B: 37, 0x4C: 38, 0x4D: 50, 0x4E: 49, 0x4F: 24,
    0x50: 25, 0x51: 16, 0x52: 19, 0x53: 31, 0x54: 20,
    0x55: 22, 0x56: 47, 0x57: 17, 0x58: 45, 0x59: 21,
    0x5A: 44,
    0x70: 59, 0x71: 60, 0x72: 61, 0x73: 62,
    0x74: 63, 0x75: 64, 0x76: 65, 0x77: 66,
    0x78: 67, 0x79: 68, 0x7A: 87, 0x7B: 88,
    0xBA: 39, 0xBB: 13, 0xBC: 51, 0xBD: 12,
    0xBE: 52, 0xBF: 53, 0xC0: 41,
    0xDB: 26, 0xDC: 43, 0xDD: 27, 0xDE: 40,
}

KEY_TO_LOGITECH: dict[str, str] = {}
for _logi_name, _internal_name in LOGITECH_KEY_MAP.items():
    if _internal_name not in KEY_TO_LOGITECH:
        KEY_TO_LOGITECH[_internal_name] = _logi_name
for _ch in "abcdefghijklmnopqrstuvwxyz0123456789":
    KEY_TO_LOGITECH[_ch] = _ch
for _i in range(1, 13):
    KEY_TO_LOGITECH[f"f{_i}"] = f"f{_i}"
KEY_TO_LOGITECH.update({
    "ctrl": "lctrl", "shift": "lshift", "alt": "lalt",
})

KEY_TO_XMBC: dict[str, str] = {}
for _xmbc_token, _internal_name in XMBC_SPECIAL_KEYS.items():
    if not _internal_name.startswith("__"):
        if _internal_name not in KEY_TO_XMBC:
            KEY_TO_XMBC[_internal_name] = _xmbc_token

KEY_TO_AHK_BRACED: dict[str, str] = {
    "space": "Space", "enter": "Enter", "tab": "Tab",
    "esc": "Esc", "escape": "Esc", "backspace": "Backspace",
    "delete": "Delete", "insert": "Insert",
    "home": "Home", "end": "End",
    "page_up": "PgUp", "page_down": "PgDn",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "ctrl": "Ctrl", "ctrl_l": "LCtrl", "ctrl_r": "RCtrl",
    "shift": "Shift", "shift_l": "LShift", "shift_r": "RShift",
    "alt": "Alt", "alt_l": "LAlt", "alt_r": "RAlt",
    "lwin": "LWin", "rwin": "RWin",
    "caps_lock": "CapsLock",
    "scroll_lock": "ScrollLock", "num_lock": "NumLock",
}

_EXPORT_EXT_MAP: dict[str, str] = {
    "razer": ".xml",
    "logitech": ".lua",
    "ahk": ".ahk",
    "xmouse": ".xmbcs",
}


def detect_format_by_content(source: str) -> str | None:
    stripped = source.strip()
    if not stripped:
        return None

    if stripped.startswith("<?xml") or stripped.startswith("<Macro"):
        if "MacroEvent" in source or "Makecode" in source or "KeyEvent" in source:
            return "razer"

    if "function OnEvent" in source or "PressKey(" in source or "ReleaseKey(" in source:
        if "MoveMouseRelative" in source or "Sleep(" in source or "PressMouseButton" in source:
            return "logitech"

    if re.search(r"#Requires\s+AutoHotkey", source, re.I):
        return "ahk"
    if re.search(r"::\s*(\{|$)", source, re.M):
        if re.search(r"\bSend\b", source, re.I) or re.search(r"\bClick\b", source, re.I):
            return "ahk"
    if re.search(r"^\w+::", source, re.M) and re.search(r"\bSleep\b", source, re.I):
        return "ahk"

    if re.search(r"\[Default\]", source, re.I) and "SimKey" in source:
        return "xmouse"
    if re.search(r"Button\d+SimKey", source, re.I):
        return "xmouse"
    if re.search(r"\{CTRL\}|\{SHIFT\}|\{ALT\}|\{ENTER\}", source, re.I):
        if not re.search(r"Send|Click|Sleep|function", source, re.I):
            return "xmouse"

    return None


class BaseConverter(ABC):
    def __init__(self) -> None:
        self.rows: list[list[Any]] = []
        self.converted_count = 0
        self.skipped_count = 0

    def _add(self, row: list[Any]) -> None:
        self.rows.append(row)
        self.converted_count += 1

    def _skip(self, desc: str) -> None:
        self.rows.append(["note", f"跳过: {desc}"])
        self.skipped_count += 1

    @abstractmethod
    def convert(self, source: str) -> list[list[Any]]: ...

    def summary(self) -> str:
        total = self.converted_count + self.skipped_count
        return f"总指令数: {total}, 转换成功: {self.converted_count}, 跳过: {self.skipped_count}"


class RazerConverter(BaseConverter):
    def convert(self, source: str) -> list[list[Any]]:
        self.rows = []
        self.converted_count = 0
        self.skipped_count = 0

        root = ET.fromstring(source)
        events = root.find("MacroEvents")
        if events is None:
            return self.rows

        raw_events: list[tuple[str, dict[str, Any]]] = []
        for event in events.findall("MacroEvent"):
            parsed = self._parse_event(event)
            if parsed is not None:
                raw_events.append(parsed)

        # Detect Synapse 3 format: action events have <Delay> element
        # In v3, <Delay> on action = the action's own delay (no separate <Type>0> events)
        # In v4, action events don't have <Delay>, delays are separate <Type>0> events
        has_v3_delay = any(
            evt[0] not in ("wait", "note") and evt[1].get("_delay", 0) > 0
            for evt in raw_events
        )

        i = 0
        n = len(raw_events)

        # In v3 format, leading <Type>0> events don't exist (delays are on actions)
        # In v4 format, leading <Type>0> events are explicit waits
        if not has_v3_delay:
            while i < n and raw_events[i][0] == "wait":
                self._add(["wait", raw_events[i][1]["_delay"]])
                i += 1

        while i < n:
            evt_type, evt_data = raw_events[i]

            if evt_type == "wait":
                if has_v3_delay:
                    # In v3, <Type>0> events shouldn't appear, but if they do,
                    # treat them as leading waits or append to previous action
                    if self.rows and self.rows[-1][0] not in ("note", "wait"):
                        self.rows[-1][-1] += evt_data["_delay"]
                    else:
                        self._add(["wait", evt_data["_delay"]])
                else:
                    if self.rows and self.rows[-1][0] not in ("note", "wait"):
                        self.rows[-1][-1] += evt_data["_delay"]
                    else:
                        self._add(["wait", evt_data["_delay"]])
                i += 1
                continue

            delay = 0
            j = i + 1
            while j < n and raw_events[j][0] == "wait":
                delay += raw_events[j][1]["_delay"]
                j += 1

            if not any(raw_events[k][0] != "wait" for k in range(i + 1, j)):
                delay += evt_data.get("_delay", 0)

            if evt_type == "kd":
                self._add(["kd", evt_data["key"], delay])
            elif evt_type == "ku":
                self._add(["ku", evt_data["key"], delay])
            elif evt_type == "md":
                self._add(["md", evt_data["btn"], delay])
            elif evt_type == "mu":
                self._add(["mu", evt_data["btn"], delay])
            elif evt_type == "move_to":
                self._add(["move_to", evt_data["x"], evt_data["y"], delay])
                for dx, dy in evt_data.get("view_points", []):
                    self._add(["view", [dx, dy], 0])

            i = j

        return self.rows

    def _parse_event(self, event: ET.Element) -> tuple[str, dict[str, Any]] | None:
        type_text = self._text(event, "Type")

        if type_text in ("actionBar", "repeat", "comment"):
            return None

        delay = int(self._text(event, "Delay") or "0")

        if type_text == "0":
            number_text = self._text(event, "Number")
            if number_text is not None:
                ms = int(float(number_text) * 1000)
                return ("wait", {"_delay": ms})
            return ("wait", {"_delay": delay})

        if type_text == "1":
            ke = event.find("KeyEvent")
            if ke is None:
                self._skip("键盘事件缺少KeyEvent")
                return None
            makecode = int(self._text(ke, "Makecode") or "0")
            state = int(self._text(ke, "State") or "0")

            key_name = RAZER_VK_CODE.get(makecode)
            if key_name is None:
                self._skip(f"未知Razer VK码 {makecode}")
                return None

            if state in (0, 2):
                return ("kd", {"key": key_name, "_delay": delay})
            elif state in (1, 3):
                return ("ku", {"key": key_name, "_delay": delay})
            else:
                self._skip(f"未知键盘状态 {state} (VK码 {makecode})")
                return None

        elif type_text == "2":
            me = event.find("MouseEvent")
            if me is None:
                self._skip("鼠标事件缺少MouseEvent")
                return None
            button_text = self._text(me, "MouseButton") or self._text(me, "Button") or "0"
            button_num = int(button_text)
            state = int(self._text(me, "State") or "0")

            btn_name = RAZER_MOUSE_BUTTON.get(button_num)
            if btn_name is None:
                self._skip(f"未知鼠标按钮 {button_num}")
                return None

            if state == 0:
                return ("md", {"btn": btn_name, "_delay": delay})
            elif state == 1:
                return ("mu", {"btn": btn_name, "_delay": delay})
            else:
                self._skip(f"未知鼠标按钮状态 {state} (按钮 {button_num})")
                return None

        elif type_text == "3":
            mm = event.find("MouseMovement")
            if mm is None:
                self._skip("鼠标移动事件缺少MouseMovement")
                return None
            move_events = mm.findall("MouseMovementEvent")
            if not move_events:
                return None

            points: list[tuple[int, int]] = []
            for me in move_events:
                x = int(self._text(me, "X") or "0")
                y = int(self._text(me, "Y") or "0")
                points.append((x, y))

            result: dict[str, Any] = {"x": points[0][0], "y": points[0][1], "_delay": delay}
            if len(points) >= 2:
                view_points = []
                for i in range(1, len(points)):
                    dx = points[i][0] - points[i - 1][0]
                    dy = points[i][1] - points[i - 1][1]
                    view_points.append((dx, dy))
                result["view_points"] = view_points
            return ("move_to", result)
        else:
            self._skip(f"未知Razer事件类型 {type_text}")
            return None

    @staticmethod
    def _text(element: ET.Element, tag: str) -> str | None:
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return None


class LogitechConverter(BaseConverter):
    _RE_PRESS_KEY = re.compile(r'PressKey\s*\(\s*["\']([^"\']+)["\']\s*\)', re.I)
    _RE_RELEASE_KEY = re.compile(r'ReleaseKey\s*\(\s*["\']([^"\']+)["\']\s*\)', re.I)
    _RE_PRESS_MOUSE = re.compile(r'PressMouseButton\s*\(\s*(\d+)\s*\)', re.I)
    _RE_RELEASE_MOUSE = re.compile(r'ReleaseMouseButton\s*\(\s*(\d+)\s*\)', re.I)
    _RE_MOVE_REL = re.compile(r'MoveMouseRelative\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)', re.I)
    _RE_MOVE_TO = re.compile(r'MoveMouseTo\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)', re.I)
    _RE_SLEEP = re.compile(r'Sleep\s*\(\s*(\d+)\s*\)', re.I)
    _RE_OUTPUT_LOG = re.compile(r'OutputLogMessage\s*\(', re.I)
    _RE_GET_KEY = re.compile(r'GetKeyState\s*\(', re.I)
    _RE_GET_TIME = re.compile(r'GetRunningTime\s*\(', re.I)
    _RE_MOVE_MOUSE_WHEEL = re.compile(r'MoveMouseWheel\s*\(\s*(-?\d+)\s*\)', re.I)

    def convert(self, source: str) -> list[list[Any]]:
        self.rows = []
        self.converted_count = 0
        self.skipped_count = 0

        for line in source.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--") or stripped.startswith("//"):
                continue
            self._parse_line(stripped)

        return self.rows

    def _map_key(self, raw: str) -> str | None:
        key = raw.strip().lower()
        if key in LOGITECH_KEY_MAP:
            return LOGITECH_KEY_MAP[key]
        if re.fullmatch(r"[a-z]", key):
            return key
        if re.fullmatch(r"[0-9]", key):
            return key
        if re.fullmatch(r"f\d{1,2}", key):
            return key
        return None

    def _map_mouse_button(self, num: int) -> str | None:
        mapping = {1: "left", 2: "right", 3: "middle"}
        return mapping.get(num)

    def _parse_line(self, line: str) -> None:
        segments = self._split_lua_statements(line)
        for seg in segments:
            self._parse_single_statement(seg)

    def _split_lua_statements(self, line: str) -> list[str]:
        segments: list[str] = []
        depth = 0
        current: list[str] = []
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth = max(0, depth - 1)
                current.append(ch)
            elif depth == 0 and (ch == ';' or ch == ' '):
                token = ''.join(current)
                if token:
                    segments.append(token)
                current = []
            else:
                current.append(ch)
            i += 1
        token = ''.join(current)
        if token:
            segments.append(token)
        return segments

    def _parse_single_statement(self, stmt: str) -> None:
        if m := self._RE_PRESS_KEY.search(stmt):
            key = self._map_key(m.group(1))
            if key:
                self._add(["kd", key, 0])
            else:
                self._skip(f"未知Logitech按键 '{m.group(1)}'")
            return

        if m := self._RE_RELEASE_KEY.search(stmt):
            key = self._map_key(m.group(1))
            if key:
                self._add(["ku", key, 0])
            else:
                self._skip(f"未知Logitech按键 '{m.group(1)}'")
            return

        if m := self._RE_PRESS_MOUSE.search(stmt):
            btn = self._map_mouse_button(int(m.group(1)))
            if btn:
                self._add(["md", btn, 0])
            else:
                self._skip(f"不支持Logitech鼠标按钮 {m.group(1)}")
            return

        if m := self._RE_RELEASE_MOUSE.search(stmt):
            btn = self._map_mouse_button(int(m.group(1)))
            if btn:
                self._add(["mu", btn, 0])
            else:
                self._skip(f"不支持Logitech鼠标按钮 {m.group(1)}")
            return

        if m := self._RE_MOVE_REL.search(stmt):
            dx, dy = int(m.group(1)), int(m.group(2))
            self._add(["view", [dx, dy], 0])
            return

        if m := self._RE_MOVE_TO.search(stmt):
            x, y = int(m.group(1)), int(m.group(2))
            if x > 1000 or y > 1000:
                x = int(x / 65535 * 1920)
                y = int(y / 65535 * 1080)
            self._add(["move_to", x, y, 0])
            return

        if m := self._RE_MOVE_MOUSE_WHEEL.search(stmt):
            amount = int(m.group(1))
            self._add(["scroll", amount])
            return

        if m := self._RE_SLEEP.search(stmt):
            ms = int(m.group(1))
            self._add(["wait", ms])
            return

        if self._RE_OUTPUT_LOG.search(stmt):
            self._skip("OutputLogMessage (日志输出)")
            return

        if self._RE_GET_KEY.search(stmt):
            self._skip("GetKeyState (条件判断)")
            return

        if self._RE_GET_TIME.search(stmt):
            self._skip("GetRunningTime (时间获取)")
            return

        structural = {
            "function", "if", "then", "else", "elseif", "end", "do",
            "for", "while", "repeat", "until", "return", "local",
        }
        first_word = stmt.split()[0].lower() if stmt.split() else ""
        if first_word not in structural and not stmt.startswith("//"):
            pass


class AhkConverter(BaseConverter):
    def __init__(self) -> None:
        super().__init__()
        self.is_v2 = False

    def convert(self, source: str) -> list[list[Any]]:
        self.rows = []
        self.converted_count = 0
        self.skipped_count = 0
        self.is_v2 = self._detect_v2(source)

        lines = source.splitlines()
        body_lines = self._extract_body(lines)
        self._parse_body(body_lines)

        return self.rows

    def _detect_v2(self, source: str) -> bool:
        if re.search(r"#Requires\s+AutoHotkey\s+v?2", source, re.I):
            return True
        if re.search(r"#Requires\s+AutoHotkey\s+v?1", source, re.I):
            return False
        if re.search(r"::\s*\{", source):
            return True
        if re.search(r"Send\s+[^,\n]", source) and not re.search(r"Send\s*,", source):
            return True
        return False

    def _extract_body(self, lines: list[str]) -> list[str]:
        body: list[str] = []
        in_hotkey = False
        brace_depth = 0
        v1_style = False

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("#"):
                continue

            if not in_hotkey:
                if "::" in stripped:
                    hotkey_part = stripped.split("::")[0].strip()
                    if hotkey_part and not hotkey_part.startswith(";"):
                        in_hotkey = True
                        after = stripped.split("::", 1)[1].strip()
                        if after.startswith("{"):
                            brace_depth = 1
                            inner = after[1:].strip()
                            if inner and inner != "}":
                                body.append(inner)
                        else:
                            body.append(after)
                            if not after:
                                v1_style = True
                            else:
                                in_hotkey = False
                continue

            if v1_style:
                if stripped.lower() == "return":
                    in_hotkey = False
                    v1_style = False
                    continue
                body.append(stripped)
            else:
                for ch in stripped:
                    if ch == "{":
                        brace_depth += 1
                    elif ch == "}":
                        brace_depth -= 1

                if brace_depth <= 0 and "}" in stripped:
                    in_hotkey = False
                    before_brace = stripped.rsplit("}", 1)[0].strip()
                    if before_brace:
                        body.append(before_brace)
                    continue

                body.append(stripped)

        return body

    def _parse_body(self, lines: list[str]) -> None:
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith(";"):
                i += 1
                continue

            if self._try_loop(lines, i) is not None:
                loop_count, loop_body, consumed = self._try_loop(lines, i)
                inner_rows = self._parse_body_return(loop_body)
                self._add(["loop", loop_count, inner_rows])
                i += consumed
                continue

            self._parse_statement(line)
            i += 1

    def _parse_body_return(self, lines: list[str]) -> list[list[Any]]:
        saved_rows = self.rows
        saved_converted = self.converted_count
        saved_skipped = self.skipped_count

        self.rows = []
        self.converted_count = 0
        self.skipped_count = 0
        self._parse_body(lines)
        result = self.rows

        self.rows = saved_rows
        self.converted_count = saved_converted
        self.skipped_count = saved_skipped
        return result

    def _try_loop(self, lines: list[str], start: int) -> tuple[int, list[str], int] | None:
        line = lines[start].strip()
        if self.is_v2:
            m = re.match(r'Loop\s+(\d+)\s*\{', line, re.I)
        else:
            m = re.match(r'Loop\s*,\s*(\d+)\s*\{', line, re.I)
            if not m:
                m = re.match(r'Loop\s+(\d+)\s*\{', line, re.I)

        if not m:
            if self.is_v2:
                m = re.match(r'Loop\s+(\d+)\s*$', line, re.I)
            else:
                m = re.match(r'Loop\s*,\s*(\d+)\s*$', line, re.I)
                if not m:
                    m = re.match(r'Loop\s+(\d+)\s*$', line, re.I)
            if not m:
                return None

            count = int(m.group(1))
            body_lines: list[str] = []
            consumed = 1
            if start + 1 < len(lines):
                next_line = lines[start + 1].strip()
                if next_line:
                    body_lines.append(next_line)
                    consumed = 2
            return count, body_lines, consumed

        count = int(m.group(1))
        depth = 1
        body_lines: list[str] = []
        i = start + 1
        while i < len(lines) and depth > 0:
            l = lines[i].strip()
            depth += l.count("{") - l.count("}")
            if depth > 0:
                body_lines.append(l)
            else:
                before = l.rsplit("}", 1)[0].strip()
                if before:
                    body_lines.append(before)
            i += 1

        return count, body_lines, i - start

    def _parse_statement(self, line: str) -> None:
        if self.is_v2:
            self._parse_v2_statement(line)
        else:
            self._parse_v1_statement(line)

    def _parse_v1_statement(self, line: str) -> None:
        if m := re.match(r'SendRaw\s*,\s*(.+)', line, re.I):
            self._parse_send_literal(m.group(1).strip())
            return

        if m := re.match(r'Send(?:Input|Event|Play)?\s*,\s*(.+)', line, re.I):
            self._parse_send(m.group(1).strip())
            return

        if m := re.match(r'Sleep\s*,\s*(\d+)', line, re.I):
            self._add(["wait", int(m.group(1))])
            return

        if re.match(r'Click\s*$', line, re.I):
            self._add(["md", "left", 0])
            self._add(["mu", "left", 0])
            return

        if m := re.match(r'Click\s*,?\s*(right|middle|left)\b', line, re.I):
            btn_raw = m.group(1).strip().lower()
            btn = self._map_ahk_mouse_button(btn_raw)
            if btn:
                self._add(["md", btn, 0])
                self._add(["mu", btn, 0])
            return

        if m := re.match(r'Click\s*,?\s*(-?\d+)\s*,?\s*(-?\d+)', line, re.I):
            x, y = int(m.group(1)), int(m.group(2))
            self._add(["move_to", x, y, 0])
            self._add(["md", "left", 0])
            self._add(["mu", "left", 0])
            return

        if m := re.match(r'MouseMove\s*,\s*(-?\d+)\s*,\s*(-?\d+)(?:\s*,\s*\d+)?(?:\s*,\s*["\']?(\w+)["\']?)?', line, re.I):
            x, y = int(m.group(1)), int(m.group(2))
            mode = (m.group(3) or "").strip().upper()
            if mode == "R":
                self._add(["view", [x, y], 0])
            else:
                self._add(["move_to", x, y, 0])
            return

        if m := re.match(r'MouseClick\s*,\s*(\w+)\s*,?\s*(-?\d+)?\s*,?\s*(-?\d+)?', line, re.I):
            btn_raw = m.group(1).strip().lower()
            x_str, y_str = m.group(2), m.group(3)
            btn = self._map_ahk_mouse_button(btn_raw)
            if btn is None:
                self._skip(f"未知AHK鼠标按钮 '{btn_raw}'")
                return
            if x_str is not None and y_str is not None:
                self._add(["move_to", int(x_str), int(y_str), 0])
            self._add(["md", btn, 0])
            self._add(["mu", btn, 0])
            return

        self._try_common_skip(line)

    def _parse_v2_statement(self, line: str) -> None:
        if m := re.match(r'Send(?:Input|Event|Play)?\s+(.+)', line, re.I):
            self._parse_send(m.group(1).strip())
            return

        if m := re.match(r'Sleep\s+(\d+)', line, re.I):
            self._add(["wait", int(m.group(1))])
            return

        if re.match(r'Click\s*$', line, re.I):
            self._add(["md", "left", 0])
            self._add(["mu", "left", 0])
            return

        if m := re.match(r'Click\s+"?(Right|Middle|Left)"?', line, re.I):
            btn_raw = m.group(1).strip().lower()
            btn = self._map_ahk_mouse_button(btn_raw)
            if btn:
                self._add(["md", btn, 0])
                self._add(["mu", btn, 0])
            return

        if m := re.match(r'Click\s+(-?\d+)\s*,?\s*(-?\d+)', line, re.I):
            x, y = int(m.group(1)), int(m.group(2))
            self._add(["move_to", x, y, 0])
            self._add(["md", "left", 0])
            self._add(["mu", "left", 0])
            return

        if m := re.match(r'MouseMove\s+(-?\d+)\s*,?\s*(-?\d+)(?:\s*,?\s*\d+)?(?:\s*,?\s*["\']?(\w+)["\']?)?', line, re.I):
            x, y = int(m.group(1)), int(m.group(2))
            mode = (m.group(3) or "").strip().upper()
            if mode == "R":
                self._add(["view", [x, y], 0])
            else:
                self._add(["move_to", x, y, 0])
            return

        if m := re.match(r'MouseClick\s+"(\w+)"(?:\s*,?\s*(-?\d+))?(?:\s*,?\s*(-?\d+))?', line, re.I):
            btn_raw = m.group(1).strip().lower()
            x_str, y_str = m.group(2), m.group(3)
            btn = self._map_ahk_mouse_button(btn_raw)
            if btn is None:
                self._skip(f"未知AHK鼠标按钮 '{btn_raw}'")
                return
            if x_str is not None and y_str is not None:
                self._add(["move_to", int(x_str), int(y_str), 0])
            self._add(["md", btn, 0])
            self._add(["mu", btn, 0])
            return

        self._try_common_skip(line)

    def _parse_send(self, keys_str: str) -> None:
        active_mods: list[str] = []
        i = 0
        n = len(keys_str)

        while i < n:
            if keys_str[i] in AHK_MODIFIER_MAP:
                mod_key = AHK_MODIFIER_MAP[keys_str[i]]
                active_mods.append(mod_key)
                self._add(["kd", mod_key, 0])
                i += 1
                continue

            if keys_str[i] == "{":
                end = keys_str.find("}", i)
                if end < 0:
                    i += 1
                    continue
                inner = keys_str[i + 1:end].strip()
                self._parse_braced_key(inner)
                i = end + 1
                continue

            if keys_str[i] == "~":
                i += 1
                continue

            ch = keys_str[i].lower()
            if ch.isalpha() or ch.isdigit():
                self._add(["kd", ch, 0])
                self._add(["ku", ch, 0])
            i += 1

        for mod_key in reversed(active_mods):
            self._add(["ku", mod_key, 0])

    def _parse_send_literal(self, keys_str: str) -> None:
        for ch in keys_str:
            if ch.isspace():
                continue
            ch_lower = ch.lower()
            if ch_lower.isalpha() or ch_lower.isdigit():
                self._add(["kd", ch_lower, 0])
                self._add(["ku", ch_lower, 0])
            else:
                self._skip(f"SendRaw符号 '{ch}' 无法映射")

    def _parse_braced_key(self, inner: str) -> None:
        lower = inner.lower().strip()

        if lower in ("blind", "text", "raw"):
            return

        if lower.endswith(" down"):
            key_part = lower[:-5].strip()
            mapped = self._map_ahk_key(key_part)
            if mapped:
                self._add(["kd", mapped, 0])
            else:
                self._skip(f"未知AHK按键 '{{{inner}}}'")
            return

        if lower.endswith(" up"):
            key_part = lower[:-3].strip()
            mapped = self._map_ahk_key(key_part)
            if mapped:
                self._add(["ku", mapped, 0])
            else:
                self._skip(f"未知AHK按键 '{{{inner}}}'")
            return

        mapped = self._map_ahk_key(lower)
        if mapped is None:
            self._skip(f"未知AHK按键 '{{{inner}}}'")
            return

        if mapped.startswith("__mouse_"):
            btn = mapped.replace("__mouse_", "")
            self._add(["md", btn, 0])
            self._add(["mu", btn, 0])
        elif mapped.startswith("__scroll_"):
            direction = mapped.replace("__scroll_", "")
            amount = 3 if direction == "up" else -3
            self._add(["scroll", amount])
        else:
            self._add(["kd", mapped, 0])
            self._add(["ku", mapped, 0])

    def _map_ahk_key(self, key: str) -> str | None:
        if key in AHK_SPECIAL_KEYS:
            return AHK_SPECIAL_KEYS[key]
        if re.fullmatch(r"f\d{1,2}", key):
            return key
        if re.fullmatch(r"[a-z]", key):
            return key
        if re.fullmatch(r"[0-9]", key):
            return key
        if key.startswith("numpad"):
            digit = key.replace("numpad", "").strip()
            if digit.isdigit():
                return f"numpad_{digit}"
        return None

    def _map_ahk_mouse_button(self, btn: str) -> str | None:
        mapping = {"left": "left", "l": "left", "right": "right", "r": "right",
                    "middle": "middle", "m": "middle"}
        return mapping.get(btn)

    def _try_common_skip(self, line: str) -> None:
        skip_prefixes = [
            "if", "winactivate", "winwait", "winwaitactive", "winclose",
            "settimer", "setkeydelay", "setmousedelay", "coordmode",
            "return", "exit", "exitapp", "reload", "msgbox", "tooltip",
            "progress", "splashimage", "guicontrol", "menu", "gosub",
            "critical", "thread", "break", "continue",
        ]
        first = line.split()[0].lower() if line.split() else ""
        if first in skip_prefixes:
            self._skip(f"{first} (不支持的操作)")
        elif first:
            self._skip(f"未识别的AHK语句: {line[:60]}")


class XmouseConverter(BaseConverter):
    def convert(self, source: str) -> list[list[Any]]:
        self.rows = []
        self.converted_count = 0
        self.skipped_count = 0

        has_ini_section = any(
            line.strip().startswith("[") for line in source.splitlines()
        )
        if has_ini_section:
            self._parse_ini_style(source)
        else:
            sim_keys = self._extract_sim_keys(source)
            if sim_keys:
                self._parse_sim_keys(sim_keys)

        return self.rows

    def _extract_sim_keys(self, source: str) -> str | None:
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("button") and "simkey" in stripped.lower():
                idx = stripped.find("=")
                if idx >= 0:
                    return stripped[idx + 1:].strip()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") or (stripped and not stripped.startswith("[") and "=" not in stripped):
                return stripped
        return None

    def _parse_ini_style(self, source: str) -> None:
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("#"):
                continue
            if stripped.startswith("["):
                continue
            if "=" not in stripped:
                continue

            key, _, value = stripped.partition("=")
            key = key.strip().lower()
            value = value.strip()

            if "simkey" in key and value:
                self._parse_sim_keys(value)

    def _parse_sim_keys(self, text: str) -> None:
        tokens = self._tokenize_xmbc(text)
        i = 0
        active_mods: list[str] = []
        pressed_mods: set[str] = set()

        while i < len(tokens):
            token = tokens[i]

            if token.startswith("{") and token.endswith("}"):
                inner = token[1:-1].upper()
                if inner.startswith("WAIT:"):
                    try:
                        wait_ms = int(inner[5:])
                        self._add(["wait", wait_ms])
                    except ValueError:
                        self._add(["wait", 10])
                    i += 1
                    continue

                if inner.startswith("WAITMS:"):
                    try:
                        wait_ms = int(inner[7:])
                        self._add(["wait", wait_ms])
                    except ValueError:
                        self._add(["wait", 10])
                    i += 1
                    continue

                if inner.startswith("DELAY="):
                    try:
                        delay_ms = int(inner[6:])
                        self._add(["wait", delay_ms])
                    except ValueError:
                        self._add(["wait", 10])
                    i += 1
                    continue

                if inner in ("CTRL", "LCTRL", "RCTRL", "SHIFT", "LSHIFT", "RSHIFT",
                             "ALT", "LALT", "RALT", "LWIN", "RWIN"):
                    mapped = XMBC_SPECIAL_KEYS.get(inner)
                    if mapped:
                        if mapped in pressed_mods:
                            pressed_mods.remove(mapped)
                            active_mods.remove(mapped)
                            self._add(["ku", mapped, 0])
                        else:
                            pressed_mods.add(mapped)
                            active_mods.append(mapped)
                            self._add(["kd", mapped, 0])
                    i += 1
                    continue

                if inner == "WAIT":
                    if i + 1 < len(tokens) and tokens[i + 1].isdigit():
                        self._add(["wait", int(tokens[i + 1])])
                        i += 2
                    else:
                        self._add(["wait", 10])
                        i += 1
                    continue

                mapped = XMBC_SPECIAL_KEYS.get(inner)
                if mapped:
                    if mapped.startswith("__mouse_"):
                        btn = mapped.replace("__mouse_", "")
                        self._add(["md", btn, 0])
                        self._add(["mu", btn, 0])
                    elif mapped.startswith("__scroll_"):
                        direction = mapped.replace("__scroll_", "")
                        amount = 3 if direction == "up" else -3
                        self._add(["scroll", amount])
                    else:
                        self._add(["kd", mapped, 0])
                        self._add(["ku", mapped, 0])
                else:
                    if inner.startswith("F") and inner[1:].isdigit():
                        fnum = int(inner[1:])
                        if 1 <= fnum <= 24:
                            self._add(["kd", f"f{fnum}", 0])
                            self._add(["ku", f"f{fnum}", 0])
                        else:
                            self._skip(f"未知XMBC按键 {{{inner}}}")
                    else:
                        self._skip(f"未知XMBC按键 {{{inner}}}")
                i += 1
                continue

            ch = token.lower()
            if ch in ("{", "}"):
                i += 1
                continue

            if len(ch) == 1 and ch.isalpha():
                self._add(["kd", ch, 0])
                self._add(["ku", ch, 0])
            elif len(ch) == 1 and ch.isdigit():
                self._add(["kd", ch, 0])
                self._add(["ku", ch, 0])
            else:
                self._skip(f"未识别XMBC令牌 '{token}'")
            i += 1

        for mod_key in reversed(active_mods):
            self._add(["ku", mod_key, 0])

    def _tokenize_xmbc(self, text: str) -> list[str]:
        tokens: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i].isspace():
                i += 1
                continue
            if text[i] == "{":
                end = text.find("}", i)
                if end < 0:
                    end = n - 1
                tokens.append(text[i:end + 1])
                i = end + 1
                continue
            tokens.append(text[i])
            i += 1
        return tokens


class BaseExporter(ABC):
    def __init__(self, rows: list[list[Any]]):
        self.rows = rows
        self.warnings: list[str] = []

    @abstractmethod
    def export(self) -> str: ...

    def _warn(self, msg: str) -> None:
        self.warnings.append(msg)


class RazerXmlExporter(BaseExporter):
    def __init__(self, rows: list[list[Any]], synapse_version: int = 4) -> None:
        super().__init__(rows)
        self.synapse_version = synapse_version

    def export(self) -> str:
        self.warnings = []
        events = self._build_events(self.rows)
        if self.synapse_version == 3:
            return self._render_xml_v3(events)
        return self._render_xml_v4(events)

    def _build_events(self, rows: list[list[Any]]) -> list[dict[str, Any]]:
        raw_events: list[dict[str, Any]] = []
        pending_delay = 0
        id_counter = int(time.time() * 1000)
        active_ids: dict[str, str] = {}

        def flush_delay() -> None:
            nonlocal pending_delay
            if pending_delay > 0:
                raw_events.append({"Type": "0", "Number": f"{pending_delay / 1000:.3f}"})
                pending_delay = 0

        def next_id() -> str:
            nonlocal id_counter
            eid = str(id_counter)
            id_counter += 1
            return eid

        has_leading_wait = False
        for row in rows:
            if isinstance(row, list) and row:
                cmd = str(row[0]).strip().lower()
                if cmd == "note":
                    continue
                if cmd == "wait":
                    has_leading_wait = True
                break

        if not has_leading_wait:
            raw_events.append({"Type": "0", "Number": "0.000"})

        i = 0
        while i < len(rows):
            row = rows[i]
            if not isinstance(row, list) or not row:
                i += 1
                continue
            cmd = str(row[0]).strip().lower()

            if cmd == "note":
                i += 1
                continue

            if cmd == "wait":
                ms = max(0, int(float(row[1])) if len(row) >= 2 else 0)
                pending_delay += ms
                i += 1
                continue

            if cmd == "scroll":
                self._warn(f"Razer 不支持滚轮事件 (scroll {row[1] if len(row) >= 2 else '?'})，已跳过")
                i += 1
                continue

            if cmd == "loop":
                count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
                block = row[2] if len(row) >= 3 and isinstance(row[2], list) else []
                inner_events = self._build_events(block)
                for _ in range(count):
                    raw_events.extend(inner_events)
                i += 1
                continue

            if cmd in ("kd", "ku"):
                key = str(row[1]) if len(row) >= 2 else ""
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                sc = KEY_TO_RAZER_VK.get(key)
                if sc is None:
                    self._warn(f"Razer 未知VK码对应键 '{key}'，已跳过")
                    i += 1
                    continue
                state = 0 if cmd == "kd" else 1
                flush_delay()

                eid = None
                if cmd == "kd":
                    eid = next_id()
                    active_ids[key] = eid
                elif cmd == "ku" and key in active_ids:
                    eid = active_ids.pop(key)
                else:
                    eid = next_id()

                evt: dict[str, Any] = {"Type": "1", "KeyEvent": {"Makecode": str(sc), "State": str(state)}}
                if eid:
                    evt["_id"] = eid
                scan = RAZER_VK_TO_SCAN.get(sc)
                if scan is not None:
                    evt["ScanCode"] = str(scan)
                raw_events.append(evt)
                pending_delay = delay
                i += 1
                continue

            if cmd in ("md", "mu"):
                btn = str(row[1]) if len(row) >= 2 else ""
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                btn_num = RAZER_MOUSE_NAME_TO_BUTTON.get(btn)
                if btn_num is None:
                    self._warn(f"Razer 未知鼠标按钮 '{btn}'，已跳过")
                    i += 1
                    continue
                state = 0 if cmd == "md" else 1
                flush_delay()

                eid = None
                btn_key = f"mouse_{btn}"
                if cmd == "md":
                    eid = next_id()
                    active_ids[btn_key] = eid
                elif cmd == "mu" and btn_key in active_ids:
                    eid = active_ids.pop(btn_key)
                else:
                    eid = next_id()

                evt = {"Type": "2", "MouseEvent": {"MouseButton": str(btn_num), "State": str(state)}}
                if eid:
                    evt["_id"] = eid
                raw_events.append(evt)
                pending_delay = delay
                i += 1
                continue

            if cmd == "move_to":
                x = int(float(row[1])) if len(row) >= 2 else 0
                y = int(float(row[2])) if len(row) >= 3 else 0
                delay = max(0, int(float(row[3])) if len(row) >= 4 else 0)
                flush_delay()
                evt = {"Type": "3", "MouseMovement": {"Points": [{"X": str(x), "Y": str(y)}]}}
                raw_events.append(evt)
                pending_delay = delay
                i += 1
                continue

            if cmd == "view":
                if len(row) < 2 or not isinstance(row[1], list) or len(row[1]) < 2:
                    i += 1
                    continue
                dx, dy = int(float(row[1][0])), int(float(row[1][1]))
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                prev = raw_events[-1] if raw_events else None
                if prev and prev.get("Type") == "3":
                    prev_pts = prev["MouseMovement"]["Points"]
                    last = prev_pts[-1]
                    lx, ly = int(last["X"]), int(last["Y"])
                    prev_pts.append({"X": str(lx + dx), "Y": str(ly + dy)})
                    if delay > 0:
                        pending_delay += delay
                else:
                    flush_delay()
                    evt = {"Type": "3", "MouseMovement": {"Points": [
                        {"X": str(dx), "Y": str(dy)}
                    ]}}
                    raw_events.append(evt)
                    pending_delay = delay
                i += 1
                continue

            self._warn(f"未知内部指令 '{cmd}'，已跳过")
            i += 1

        flush_delay()
        return raw_events

    @staticmethod
    def _render_xml_v4(events: list[dict[str, Any]], macro_name: str = "ExportedMacro") -> str:
        import uuid
        import hashlib

        lines: list[str] = []
        lines.append('<Macro>')

        content_hash = hashlib.md5(str(events).encode()).hexdigest()[:12]
        lines.append(f'   <Name>{macro_name}_{content_hash}</Name>')
        lines.append('   <MacroEvents>')

        for evt in events:
            lines.append('      <MacroEvent>')
            lines.append(f'         <Type>{evt["Type"]}</Type>')

            if evt["Type"] == "0":
                lines.append(f'         <Number>{evt["Number"]}</Number>')
            elif evt["Type"] == "1":
                if "_id" in evt:
                    lines.append(f'         <Id>{evt["_id"]}</Id>')
                lines.append('         <KeyEvent>')
                lines.append(f'            <Makecode>{evt["KeyEvent"]["Makecode"]}</Makecode>')
                lines.append(f'            <State>{evt["KeyEvent"]["State"]}</State>')
                lines.append('         </KeyEvent>')
                lines.append('         <flag/>')
                lines.append('         <selected>false</selected>')
                lines.append('         <isPairing>false</isPairing>')
                if "ScanCode" in evt:
                    lines.append(f'         <ScanCode>{evt["ScanCode"]}</ScanCode>')
            elif evt["Type"] == "2":
                if "_id" in evt:
                    lines.append(f'         <Id>{evt["_id"]}</Id>')
                lines.append('         <MouseEvent>')
                lines.append(f'            <MouseButton>{evt["MouseEvent"]["MouseButton"]}</MouseButton>')
                lines.append(f'            <State>{evt["MouseEvent"]["State"]}</State>')
                lines.append('         </MouseEvent>')
                flag_val = evt.get("_flag")
                if flag_val is not None:
                    lines.append(f'         <flag>{flag_val}</flag>')
                else:
                    lines.append('         <flag/>')
                lines.append('         <selected>false</selected>')
                lines.append('         <isPairing>false</isPairing>')
            elif evt["Type"] == "3":
                lines.append('         <MouseMovement>')
                for pt in evt["MouseMovement"]["Points"]:
                    lines.append('            <MouseMovementEvent>')
                    lines.append(f'               <X>{pt["X"]}</X>')
                    lines.append(f'               <Y>{pt["Y"]}</Y>')
                    lines.append('            </MouseMovementEvent>')
                lines.append('         </MouseMovement>')
                lines.append('         <selected>false</selected>')

            if evt["Type"] == "0":
                lines.append('         <selected>false</selected>')

            lines.append('      </MacroEvent>')

        lines.append('   </MacroEvents>')
        namespace_uuid = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
        guid = str(uuid.uuid5(namespace_uuid, content_hash))
        lines.append(f'   <DelaySetting>0</DelaySetting>')
        lines.append(f'   <Guid>{guid}</Guid>')
        lines.append('   <Version>4</Version>')
        lines.append('   <MouseMoveType>none</MouseMoveType>')
        lines.append('</Macro>')
        return '\n'.join(lines)

    @staticmethod
    def _render_xml_v3(events: list[dict[str, Any]], macro_name: str = "ExportedMacro") -> str:
        import uuid
        import hashlib

        lines: list[str] = []
        lines.append('<?xml version="1.0" encoding="utf-8"?>')
        lines.append('<Macro xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">')

        content_hash = hashlib.md5(str(events).encode()).hexdigest()[:12]
        lines.append(f'  <Name>{macro_name}_{content_hash}</Name>')
        namespace_uuid = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
        guid = str(uuid.uuid5(namespace_uuid, content_hash))
        lines.append(f'  <Guid>{guid}</Guid>')
        lines.append('  <MacroEvents>')

        # v3 format: delays are on action events via <Delay>
        # Leading <Type>0> events are kept as-is for pre-action waits
        # Action delays = trailing <Type>0> events until next action
        i = 0
        while i < len(events):
            evt = events[i]

            if evt["Type"] == "0":
                # Leading wait event - output as <Type>0> in v3
                lines.append('    <MacroEvent>')
                lines.append(f'      <Type>0</Type>')
                lines.append(f'      <Number>{evt["Number"]}</Number>')
                lines.append('    </MacroEvent>')
                i += 1
                continue

            # Collect trailing delays until next non-wait event
            delay = 0
            j = i + 1
            while j < len(events) and events[j]["Type"] == "0":
                delay += int(float(events[j]["Number"]) * 1000)
                j += 1

            lines.append('    <MacroEvent>')
            lines.append(f'      <Type>{evt["Type"]}</Type>')

            if evt["Type"] == "1":
                lines.append(f'      <Delay>{delay}</Delay>')
                lines.append('      <KeyEvent>')
                lines.append(f'        <Makecode>{evt["KeyEvent"]["Makecode"]}</Makecode>')
                lines.append(f'        <State>{evt["KeyEvent"]["State"]}</State>')
                lines.append('      </KeyEvent>')
            elif evt["Type"] == "2":
                lines.append(f'      <Delay>{delay}</Delay>')
                lines.append('      <MouseEvent>')
                lines.append(f'        <MouseButton>{evt["MouseEvent"]["MouseButton"]}</MouseButton>')
                lines.append(f'        <State>{evt["MouseEvent"]["State"]}</State>')
                lines.append('      </MouseEvent>')
            elif evt["Type"] == "3":
                lines.append(f'      <Delay>{delay}</Delay>')
                lines.append('      <MouseMovement>')
                for pt in evt["MouseMovement"]["Points"]:
                    lines.append('        <MouseMovementEvent>')
                    lines.append(f'          <X>{pt["X"]}</X>')
                    lines.append(f'          <Y>{pt["Y"]}</Y>')
                    lines.append('        </MouseMovementEvent>')
                lines.append('      </MouseMovement>')

            lines.append('    </MacroEvent>')
            i = j

        lines.append('  </MacroEvents>')
        lines.append('  <IsFolder>false</IsFolder>')
        lines.append('  <FolderGuid>00000000-0000-0000-0000-000000000000</FolderGuid>')
        lines.append('</Macro>')
        return '\n'.join(lines)


class LogitechLuaExporter(BaseExporter):
    _MODIFIER_KEYS = {"ctrl_l", "ctrl_r", "shift_l", "shift_r", "alt_l", "alt_r",
                       "ctrl", "shift", "alt", "lwin", "rwin"}

    def __init__(self, rows: list[list[Any]], *, ghub: bool = True,
                 screen_width: int = 1920, screen_height: int = 1080) -> None:
        super().__init__(rows)
        self.ghub = ghub
        self.screen_width = max(1, screen_width)
        self.screen_height = max(1, screen_height)

    def export(self) -> str:
        self.warnings = []
        body_lines = self._build_body(self.rows, indent=2)
        lines: list[str] = []
        lines.append('-- Logitech Lua Macro (generated by macro_converter)')
        lines.append(f'-- Screen resolution for MoveMouseTo: {self.screen_width}x{self.screen_height}')
        lines.append(f'-- MoveMouseTo uses 0-65535 normalized coordinates')
        lines.append(f'-- To convert pixel to logitech: x_logi = pixel_x / {self.screen_width} * 65535')
        lines.append('')
        lines.append('function OnEvent(event, arg)')
        if self.ghub:
            lines.append('    if (event == "PROFILE_ACTIVATED") then')
            lines.append('        EnablePrimaryMouseButtonEvents(true)')
            lines.append('    end')
            lines.append('')
        lines.append('    -- Choose trigger: uncomment the line you need')
        lines.append('    if (event == "MOUSE_BUTTON_PRESSED" and arg == 4) then  -- side button 1')
        lines.append('    -- if (event == "MOUSE_BUTTON_PRESSED" and arg == 5) then  -- side button 2')
        lines.append('    -- if (event == "MOUSE_BUTTON_PRESSED" and arg == 1) then  -- left button (EnablePrimaryMouseButtonEvents required)')
        lines.append('    -- if (event == "G_PRESSED" and arg == 1) then  -- G key 1')
        lines.extend(body_lines)
        lines.append('    end')
        lines.append('end')
        return '\n'.join(lines) + '\n'

    def _build_body(self, rows: list[list[Any]], indent: int) -> list[str]:
        pad = '    ' * indent
        lines: list[str] = []
        i = 0
        while i < len(rows):
            row = rows[i]
            if not isinstance(row, list) or not row:
                i += 1
                continue
            cmd = str(row[0]).strip().lower()

            if cmd == "note":
                text = str(row[1]).strip() if len(row) >= 2 else ""
                if text:
                    lines.append(f'{pad}-- {text}')
                i += 1
                continue

            if cmd == "wait":
                ms = max(0, int(float(row[1])) if len(row) >= 2 else 0)
                lines.append(f'{pad}Sleep({ms})')
                i += 1
                continue

            if cmd == "scroll":
                amount = int(float(row[1])) if len(row) >= 2 else 0
                lines.append(f'{pad}MoveMouseWheel({amount})')
                i += 1
                continue

            if cmd == "loop":
                count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
                block = row[2] if len(row) >= 3 and isinstance(row[2], list) else []
                inner = self._build_body(block, indent + 1)
                if not inner:
                    i += 1
                    continue
                lines.append(f'{pad}for i = 1, {count} do')
                lines.extend(inner)
                lines.append(f'{pad}end')
                i += 1
                continue

            if cmd in ("kd", "ku"):
                key = str(row[1]) if len(row) >= 2 else ""
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                logi_key = self._map_logitech_key(key)
                if logi_key is None:
                    self._warn(f"Logitech 未知按键 '{key}'，已跳过")
                    i += 1
                    continue
                if delay > 0:
                    lines.append(f'{pad}Sleep({delay})')
                func = "PressKey" if cmd == "kd" else "ReleaseKey"
                lines.append(f'{pad}{func}("{logi_key}")')
                i += 1
                continue

            if cmd in ("md", "mu"):
                btn = str(row[1]) if len(row) >= 2 else ""
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                btn_map = {"left": "1", "right": "2", "middle": "3"}
                btn_num = btn_map.get(btn)
                if btn_num is None:
                    self._warn(f"Logitech 未知鼠标按钮 '{btn}'，已跳过")
                    i += 1
                    continue
                if delay > 0:
                    lines.append(f'{pad}Sleep({delay})')
                func = "PressMouseButton" if cmd == "md" else "ReleaseMouseButton"
                lines.append(f'{pad}{func}({btn_num})')
                i += 1
                continue

            if cmd == "move_to":
                x = int(float(row[1])) if len(row) >= 2 else 0
                y = int(float(row[2])) if len(row) >= 3 else 0
                delay = max(0, int(float(row[3])) if len(row) >= 4 else 0)
                if delay > 0:
                    lines.append(f'{pad}Sleep({delay})')
                logi_x = int(x / self.screen_width * 65535)
                logi_y = int(y / self.screen_height * 65535)
                lines.append(f'{pad}MoveMouseTo({logi_x}, {logi_y})')
                i += 1
                continue

            if cmd == "view":
                if len(row) < 2 or not isinstance(row[1], list) or len(row[1]) < 2:
                    i += 1
                    continue
                dx, dy = int(float(row[1][0])), int(float(row[1][1]))
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                if delay > 0:
                    lines.append(f'{pad}Sleep({delay})')
                lines.append(f'{pad}MoveMouseRelative({dx}, {dy})')
                i += 1
                continue

            self._warn(f"未知内部指令 '{cmd}'，已跳过")
            i += 1

        return lines

    @staticmethod
    def _map_logitech_key(key: str) -> str | None:
        if key in KEY_TO_LOGITECH:
            return KEY_TO_LOGITECH[key]
        if key.startswith("numpad_"):
            digit = key[len("numpad_"):]
            if digit.isdigit():
                return f"numpad{digit}"
        return None


class AhkExporter(BaseExporter):
    MODIFIER_KEYS = {"ctrl", "ctrl_l", "ctrl_r", "shift", "shift_l", "shift_r",
                      "alt", "alt_l", "alt_r", "lwin", "rwin"}
    MODIFIER_SYMBOL = {"ctrl": "^", "ctrl_l": "^", "ctrl_r": "^",
                        "shift": "+", "shift_l": "+", "shift_r": "+",
                        "alt": "!", "alt_l": "!", "alt_r": "!",
                        "lwin": "#", "rwin": "#"}

    def __init__(self, rows: list[list[Any]], is_v2: bool = False) -> None:
        super().__init__(rows)
        self.is_v2 = is_v2

    def export(self) -> str:
        self.warnings = []
        hotkey = "F1"
        body_lines = self._build_body(self.rows, indent=1)

        lines: list[str] = []
        if self.is_v2:
            lines.append('#Requires AutoHotkey v2.0')
            lines.append(f'{hotkey}:: {{')
        else:
            lines.append('#Requires AutoHotkey v1.1')
            lines.append(f'{hotkey}::')
        lines.extend(body_lines)
        if self.is_v2:
            lines.append('}')
        else:
            lines.append('return')
        return '\n'.join(lines) + '\n'

    def _build_body(self, rows: list[list[Any]], indent: int) -> list[str]:
        pad = '    ' * indent
        lines: list[str] = []
        i = 0
        while i < len(rows):
            row = rows[i]
            if not isinstance(row, list) or not row:
                i += 1
                continue
            cmd = str(row[0]).strip().lower()

            if cmd == "note":
                text = str(row[1]).strip() if len(row) >= 2 else ""
                if text:
                    prefix = ';' if self.is_v2 else ';'
                    lines.append(f'{pad}{prefix} {text}')
                i += 1
                continue

            if cmd == "wait":
                ms = max(0, int(float(row[1])) if len(row) >= 2 else 0)
                if self.is_v2:
                    lines.append(f'{pad}Sleep {ms}')
                else:
                    lines.append(f'{pad}Sleep, {ms}')
                i += 1
                continue

            if cmd == "scroll":
                amount = int(float(row[1])) if len(row) >= 2 else 0
                if amount > 0:
                    key_token = "{WheelUp}"
                else:
                    key_token = "{WheelDown}"
                repeat = abs(amount)
                for _ in range(repeat):
                    if self.is_v2:
                        lines.append(f'{pad}Send "{key_token}"')
                    else:
                        lines.append(f'{pad}Send, {key_token}')
                i += 1
                continue

            if cmd == "loop":
                count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
                block = row[2] if len(row) >= 3 and isinstance(row[2], list) else []
                inner = self._build_body(block, indent + 1)
                if not inner:
                    i += 1
                    continue
                if self.is_v2:
                    lines.append(f'{pad}Loop {count} {{')
                else:
                    lines.append(f'{pad}Loop, {count} {{')
                lines.extend(inner)
                lines.append(f'{pad}}}')
                i += 1
                continue

            merged, consumed = self._try_merge_kdku(rows, i)
            if merged is not None:
                lines.extend(self._emit_merged(merged, pad))
                i += consumed
                continue

            merged_mouse, consumed = self._try_merge_mdmu(rows, i)
            if merged_mouse is not None:
                lines.extend(self._emit_mouse(merged_mouse, pad))
                i += consumed
                continue

            if cmd in ("kd", "ku", "md", "mu"):
                i += 1
                continue

            if cmd == "move_to":
                x = int(float(row[1])) if len(row) >= 2 else 0
                y = int(float(row[2])) if len(row) >= 3 else 0
                delay = max(0, int(float(row[3])) if len(row) >= 4 else 0)
                if delay > 0:
                    if self.is_v2:
                        lines.append(f'{pad}Sleep {delay}')
                    else:
                        lines.append(f'{pad}Sleep, {delay}')
                if self.is_v2:
                    lines.append(f'{pad}MouseMove {x}, {y}')
                else:
                    lines.append(f'{pad}MouseMove, {x}, {y}')
                i += 1
                continue

            if cmd == "view":
                if len(row) < 2 or not isinstance(row[1], list) or len(row[1]) < 2:
                    i += 1
                    continue
                dx, dy = int(float(row[1][0])), int(float(row[1][1]))
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                if delay > 0:
                    if self.is_v2:
                        lines.append(f'{pad}Sleep {delay}')
                    else:
                        lines.append(f'{pad}Sleep, {delay}')
                if self.is_v2:
                    lines.append(f'{pad}MouseMove {dx}, {dy}, 0, "R"')
                else:
                    lines.append(f'{pad}MouseMove, {dx}, {dy}, 0, R')
                i += 1
                continue

            if cmd in ("kd", "ku", "md", "mu"):
                i += 1
                continue

            self._warn(f"未知内部指令 '{cmd}'，已跳过")
            i += 1

        return lines

    def _try_merge_kdku(self, rows: list[list[Any]], start: int) -> tuple[list[dict[str, Any]], int] | None:
        i = start
        merged: list[dict[str, Any]] = []

        while i < len(rows):
            row = rows[i]
            if not isinstance(row, list) or not row:
                break
            cmd = str(row[0]).strip().lower()
            if cmd in ("kd", "ku"):
                key = str(row[1]) if len(row) >= 2 else ""
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                merged.append({"action": cmd, "key": key, "delay": delay})
                i += 1
            else:
                break

        if not merged:
            return None, 0
        return merged, i - start

    def _try_merge_mdmu(self, rows: list[list[Any]], start: int) -> tuple[list[dict[str, Any]], int] | None:
        i = start
        merged: list[dict[str, Any]] = []

        while i < len(rows):
            row = rows[i]
            if not isinstance(row, list) or not row:
                break
            cmd = str(row[0]).strip().lower()
            if cmd in ("md", "mu"):
                btn = str(row[1]) if len(row) >= 2 else ""
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)
                merged.append({"action": cmd, "key": btn, "delay": delay})
                i += 1
            else:
                break

        if not merged or merged[0]["action"] != "md":
            return None, 0
        return merged, i - start

    def _emit_merged(self, merged: list[dict[str, Any]], pad: str) -> list[str]:
        lines: list[str] = []
        if not merged:
            return lines

        active_set: set[str] = set()
        pending_mod_press: list[str] = []
        pending_mod_release: list[str] = []
        idx = 0

        while idx < len(merged):
            m = merged[idx]
            key = m["key"]
            delay = m["delay"]

            if delay > 0:
                lines.append(f'{pad}Sleep, {delay}' if not self.is_v2 else f'{pad}Sleep {delay}')

            if m["action"] == "kd":
                if key in self.MODIFIER_KEYS:
                    if key not in active_set:
                        active_set.add(key)
                        pending_mod_press.append(key)
                else:
                    syms = ''.join(self.MODIFIER_SYMBOL.get(m, m) for m in sorted(active_set))
                    ahk_key = self._ahk_key_name(key)
                    if ahk_key is None:
                        self._warn(f"AHK 未识别的按键 '{key}'，已跳过")
                    elif not syms:
                        if self.is_v2:
                            lines.append(f'{pad}Send "{ahk_key}"')
                        else:
                            lines.append(f'{pad}Send, {ahk_key}')
                    else:
                        if self.is_v2:
                            lines.append(f'{pad}Send "{syms}{ahk_key}"')
                        else:
                            lines.append(f'{pad}Send, {syms}{ahk_key}')
            elif m["action"] == "ku":
                if key in self.MODIFIER_KEYS:
                    if key in active_set:
                        active_set.remove(key)
                        pending_mod_release.append(key)
                else:
                    pass

            idx += 1

        if pending_mod_press:
            for mod in pending_mod_release:
                if mod in pending_mod_press:
                    pending_mod_press.remove(mod)
            for mod in pending_mod_press:
                ahk_mod = KEY_TO_AHK_BRACED.get(mod, mod)
                if self.is_v2:
                    lines.append(f'{pad}Send "{{{ahk_mod} up}}"')
                else:
                    lines.append(f'{pad}Send, {{{ahk_mod} up}}')

        return lines

    def _emit_mouse(self, merged: list[dict[str, Any]], pad: str) -> list[str]:
        lines: list[str] = []
        idx = 0
        while idx < len(merged):
            m = merged[idx]
            btn = m["key"]
            delay = m["delay"]
            action = m["action"]

            if delay > 0:
                if self.is_v2:
                    lines.append(f'{pad}Sleep {delay}')
                else:
                    lines.append(f'{pad}Sleep, {delay}')

            if action == "md":
                idx += 1
                continue

            if action == "mu":
                if btn == "left":
                    if self.is_v2:
                        lines.append(f'{pad}Click')
                    else:
                        lines.append(f'{pad}Click')
                elif btn in ("right", "middle"):
                    if self.is_v2:
                        lines.append(f'{pad}Click "{btn.capitalize()}"')
                    else:
                        lines.append(f'{pad}Click, {btn}')
                else:
                    self._warn(f"AHK 未知鼠标按钮 '{btn}'")
                idx += 1
                continue

            idx += 1
        return lines

    @staticmethod
    def _ahk_key_name(key: str) -> str:
        if key in KEY_TO_AHK_BRACED:
            return '{' + KEY_TO_AHK_BRACED[key] + '}'
        if key.startswith("numpad_"):
            digit = key[len("numpad_"):]
            return '{Numpad' + digit + '}'
        if len(key) == 1 and (key.isalpha() or key.isdigit()):
            return key
        if key.startswith("f") and key[1:].isdigit():
            return '{' + key.upper() + '}'
        return None


class XmbcsExporter(BaseExporter):
    def export(self) -> str:
        self.warnings = []
        simkey_tokens = self._build_simkey(self.rows)
        lines: list[str] = []
        lines.append('[Default]')
        lines.append('Button4=18')
        lines.append(f'Button4SimKey={simkey_tokens}')
        return '\n'.join(lines) + '\n'

    def _build_simkey(self, rows: list[list[Any]]) -> str:
        tokens: list[str] = []
        active_mods: list[str] = []
        i = 0

        while i < len(rows):
            row = rows[i]
            if not isinstance(row, list) or not row:
                i += 1
                continue
            cmd = str(row[0]).strip().lower()

            if cmd == "note":
                i += 1
                continue

            if cmd == "wait":
                ms = max(0, int(float(row[1])) if len(row) >= 2 else 0)
                if ms > 0:
                    tokens.append(f'{{WAIT:{ms}}}')
                i += 1
                continue

            if cmd == "scroll":
                amount = int(float(row[1])) if len(row) >= 2 else 0
                scroll_token = "{WHEELUP}" if amount > 0 else "{WHEELDOWN}"
                for _ in range(abs(amount)):
                    tokens.append(scroll_token)
                i += 1
                continue

            if cmd == "loop":
                count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
                block = row[2] if len(row) >= 3 and isinstance(row[2], list) else []
                inner = self._build_simkey(block)
                for _ in range(count):
                    tokens.append(inner)
                i += 1
                continue

            if cmd in ("move_to", "view"):
                coord_desc = ""
                if cmd == "move_to":
                    x = int(float(row[1])) if len(row) >= 2 else 0
                    y = int(float(row[2])) if len(row) >= 3 else 0
                    coord_desc = f"({x},{y})"
                elif len(row) >= 2 and isinstance(row[1], list) and len(row[1]) >= 2:
                    dx, dy = int(float(row[1][0])), int(float(row[1][1]))
                    coord_desc = f"({dx},{dy})"
                self._warn(f"XMBC 不支持鼠标移动 {coord_desc}，已跳过")
                i += 1
                continue

            if cmd in ("kd", "ku", "md", "mu"):
                key_or_btn = str(row[1]) if len(row) >= 2 else ""
                delay = max(0, int(float(row[2])) if len(row) >= 3 else 0)

                if cmd == "md":
                    xmbc_token = _XBC_MOUSE_MAP.get(key_or_btn)
                    if xmbc_token is None:
                        self._warn(f"XMBC 未知鼠标按钮 '{key_or_btn}'，已跳过")
                        i += 1
                        continue
                    if delay > 0:
                        tokens.append(f'{{WAIT:{delay}}}')
                    tokens.append(f'{{{xmbc_token}}}')
                    i += 1
                    continue

                if cmd == "mu":
                    xmbc_token = _XBC_MOUSE_MAP.get(key_or_btn)
                    if xmbc_token is None:
                        self._warn(f"XMBC 未知鼠标按钮 '{key_or_btn}'，已跳过")
                        i += 1
                        continue
                    if delay > 0:
                        tokens.append(f'{{WAIT:{delay}}}')
                    tokens.append(f'{{{xmbc_token}}}')
                    i += 1
                    continue

                is_mod = key_or_btn in ("ctrl", "ctrl_l", "ctrl_r", "shift", "shift_l",
                                          "shift_r", "alt", "alt_l", "alt_r", "lwin", "rwin")
                if cmd == "kd":
                    if is_mod:
                        xmbc_token = _XBC_MOD_MAP.get(key_or_btn)
                        if xmbc_token:
                            if delay > 0:
                                tokens.append(f'{{WAIT:{delay}}}')
                            tokens.append(f'{{{xmbc_token}}}')
                            active_mods.append(xmbc_token)
                        else:
                            self._warn(f"XMBC 未知修饰键 '{key_or_btn}'，已跳过")
                    else:
                        xmbc_token = self._map_xmbc_key(key_or_btn)
                        if xmbc_token is None:
                            self._warn(f"XMBC 未知按键 '{key_or_btn}'，已跳过")
                            i += 1
                            continue
                        if delay > 0:
                            tokens.append(f'{{WAIT:{delay}}}')
                        if len(xmbc_token) == 1 and (xmbc_token.isalpha() or xmbc_token.isdigit()):
                            tokens.append(xmbc_token)
                        else:
                            tokens.append(f'{{{xmbc_token}}}')
                    i += 1
                    continue

                if cmd == "ku":
                    if is_mod:
                        if delay > 0:
                            tokens.append(f'{{WAIT:{delay}}}')
                        for idx_mod in range(len(active_mods) - 1, -1, -1):
                            mod = active_mods[idx_mod]
                            xmbc_token = _XBC_MOD_MAP.get(key_or_btn)
                            if xmbc_token and mod == xmbc_token:
                                tokens.append(f'{{{mod}}}')
                                active_mods.pop(idx_mod)
                                break
                    i += 1
                    continue

            self._warn(f"未知内部指令 '{cmd}'，已跳过")
            i += 1

        for mod in reversed(active_mods):
            tokens.append(f'{{{mod}}}')

        return ''.join(tokens)

    @staticmethod
    def _map_xmbc_key(key: str) -> str | None:
        if key in KEY_TO_XMBC:
            return KEY_TO_XMBC[key]
        if len(key) == 1 and key.isalpha():
            return key.upper()
        if len(key) == 1 and key.isdigit():
            return key
        if key.startswith("f") and key[1:].isdigit():
            fnum = int(key[1:])
            if 1 <= fnum <= 24:
                return f'F{fnum}'
        if key.startswith("numpad_"):
            digit = key[len("numpad_"):]
            if digit.isdigit():
                return f'NUMPAD{digit}'
        return None


_XBC_MOD_MAP: dict[str, str] = {
    "ctrl": "CTRL", "ctrl_l": "LCTRL", "ctrl_r": "RCTRL",
    "shift": "SHIFT", "shift_l": "LSHIFT", "shift_r": "RSHIFT",
    "alt": "ALT", "alt_l": "LALT", "alt_r": "RALT",
    "lwin": "LWIN", "rwin": "RWIN",
}

_XBC_MOUSE_MAP: dict[str, str] = {
    "left": "LBUTTON", "right": "RBUTTON", "middle": "MBUTTON",
}


_FRAME_DELAY_RE = re.compile(r'^\d+f$', re.I)

# 各动作的延迟字段在 row 中的索引
_DELAY_INDEX: dict[str, int] = {
    "wait": 1,
    "kd": 2, "ku": 2, "md": 2, "mu": 2,
    "view": 2,
    "move_to": 3,
}


def _is_frame_delay_str(v) -> bool:
    """判断值是否为 "Nf" 帧延迟字符串。"""
    return isinstance(v, str) and bool(_FRAME_DELAY_RE.match(v.strip()))


def _frame_delay_to_ms(frame_str: str, fps: int) -> int:
    """将 "Nf" 帧延迟转为 ms（四舍五入）。"""
    n = int(frame_str.strip()[:-1])
    return round(n * 1000 / max(1, fps))


def _has_frame_delay(rows: list[list[Any]]) -> bool:
    """递归扫描 rows 是否含 f 帧延迟（含 loop 嵌套）。"""
    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        cmd = str(row[0]).strip().lower()
        if cmd == "loop" and len(row) >= 3 and isinstance(row[2], list):
            if _has_frame_delay(row[2]):
                return True
            continue
        idx = _DELAY_INDEX.get(cmd)
        if idx is not None and len(row) > idx and _is_frame_delay_str(row[idx]):
            return True
    return False


def _count_frame_delays(rows: list[list[Any]]) -> int:
    """递归统计 rows 中 f 帧延迟的数量（含 loop 嵌套）。"""
    count = 0
    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        cmd = str(row[0]).strip().lower()
        if cmd == "loop" and len(row) >= 3 and isinstance(row[2], list):
            count += _count_frame_delays(row[2])
            continue
        idx = _DELAY_INDEX.get(cmd)
        if idx is not None and len(row) > idx and _is_frame_delay_str(row[idx]):
            count += 1
    return count


def _convert_frame_delays(rows: list[list[Any]], fps: int) -> tuple[list[list[Any]], int]:
    """递归将 rows 中的 "Nf" 帧延迟转为 ms（四舍五入）。返回 (新rows, 转换数)。"""
    converted: list[list[Any]] = []
    count = 0
    for row in rows:
        if not isinstance(row, list) or not row:
            converted.append(row)
            continue
        cmd = str(row[0]).strip().lower()
        if cmd == "loop" and len(row) >= 3 and isinstance(row[2], list):
            new_block, sub_count = _convert_frame_delays(row[2], fps)
            converted.append([row[0], row[1], new_block])
            count += sub_count
            continue
        idx = _DELAY_INDEX.get(cmd)
        if idx is not None and len(row) > idx and _is_frame_delay_str(row[idx]):
            new_row = list(row)
            new_row[idx] = _frame_delay_to_ms(row[idx], fps)
            converted.append(new_row)
            count += 1
            continue
        converted.append(row)
    return converted, count


def _is_note_row(row: list[Any]) -> bool:
    return isinstance(row, list) and len(row) >= 1 and str(row[0]).strip().lower() == "note"


def _normalize_rows_for_save(rows: list[list[Any]]) -> list[list[Any]]:
    normalized: list[list[Any]] = []
    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        cmd = str(row[0]).strip().lower()
        if cmd == "note":
            text = str(row[1]).strip() if len(row) >= 2 else ""
            if text:
                normalized.append(["note", text])
            continue
        if cmd == "loop" and len(row) >= 3 and isinstance(row[2], list):
            count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
            block = _normalize_rows_for_save(row[2])
            normalized.append(["loop", count, block])
            continue
        normalized.append(row)
    return normalized


def _serialize_rows_with_notes(rows: list[list[Any]], indent_level: int = 1) -> list[str]:
    pad = "    " * indent_level
    lines: list[str] = []
    action_rows = [row for row in rows if not _is_note_row(row)]
    action_index = 0

    for row in rows:
        if _is_note_row(row):
            text = str(row[1]).strip() if len(row) >= 2 else ""
            if text:
                lines.append(f"{pad}// {text}")
            continue

        action_index += 1
        comma = "," if action_index < len(action_rows) else ""

        cmd = str(row[0]).strip().lower() if row else ""
        if cmd == "loop" and len(row) >= 3 and isinstance(row[2], list):
            count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
            block = row[2]
            if not block:
                lines.append(f"{pad}[\"loop\",{count},[]]{comma}")
            else:
                lines.append(f"{pad}[\"loop\",{count},[")
                lines.extend(_serialize_rows_with_notes(block, indent_level + 1))
                lines.append(f"{pad}]]{comma}")
            continue

        lines.append(f"{pad}{json.dumps(row, ensure_ascii=False, separators=(',', ':'))}{comma}")

    return lines


def save_macro_rows_with_notes(path: Path, rows: list[list[Any]]) -> None:
    normalized = _normalize_rows_for_save(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["["]
    lines.extend(_serialize_rows_with_notes(normalized, indent_level=1))
    lines.append("]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def detect_format(file_path: str, source: str | None = None) -> str | None:
    ext = Path(file_path).suffix.lower()
    ext_result = EXT_FORMAT_MAP.get(ext)

    if ext_result is not None and ext_result != "auto_content":
        return ext_result

    if source is not None:
        content_result = detect_format_by_content(source)
        if content_result is not None:
            return content_result

    return ext_result if ext_result != "auto_content" else None


def create_converter(fmt: str) -> BaseConverter:
    converters = {
        "razer": RazerConverter,
        "logitech": LogitechConverter,
        "ahk": AhkConverter,
        "xmouse": XmouseConverter,
    }
    cls = converters.get(fmt)
    if cls is None:
        raise ValueError(f"不支持的格式: {fmt} (支持: {', '.join(converters.keys())})")
    return cls()


def convert_file(source_path: str, fmt: str | None = None, output_path: str | None = None) -> Path:
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {source_path}")

    source_text = src.read_text(encoding="utf-8")

    if fmt is None or fmt == "auto":
        detected = detect_format(source_path, source_text)
        if detected is None:
            ext = src.suffix.lower() or "(无扩展名)"
            raise ValueError(f"无法自动检测格式 (扩展名 {ext}), 请用 --format 指定")
        fmt = detected

    converter = create_converter(fmt)
    rows = converter.convert(source_text)

    if output_path is None:
        script_dir = Path(__file__).resolve().parent
        output_dir = script_dir / "宏" / "导入宏"
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / f"{src.stem}.json"
    else:
        out = Path(output_path)

    save_macro_rows_with_notes(out, rows)

    print(f"格式: {fmt}")
    print(f"源文件: {src}")
    print(f"输出: {out}")
    print(converter.summary())

    return out


def resolve_macro_import_path(path_hint: str, base_dir: str) -> str:
    if os.path.isabs(path_hint):
        return path_hint

    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_roots = (
        base_dir,
        os.getcwd(),
        os.path.join(os.getcwd(), "宏"),
        script_dir,
        os.path.join(script_dir, "宏"),
    )

    for root in search_roots:
        candidate = os.path.abspath(os.path.join(root, path_hint))
        if os.path.exists(candidate):
            return candidate

    return os.path.abspath(os.path.join(base_dir, path_hint))


def resolve_imports(
    rows: list[list[Any]],
    base_dir: str,
    visited: set[str] | None = None,
    warnings: list[str] | None = None,
) -> list[list[Any]]:
    if visited is None:
        visited = set()
    if warnings is None:
        warnings = []

    resolved: list[list[Any]] = []
    for row in rows:
        if not isinstance(row, list) or not row:
            resolved.append(row)
            continue

        cmd = str(row[0]).strip().lower()

        if cmd == "import":
            if len(row) < 2:
                continue
            import_path = str(row[1])
            abs_path = resolve_macro_import_path(import_path, base_dir)

            if abs_path in visited:
                warnings.append(f"检测到宏文件循环引用，跳过：{import_path}")
                continue

            if not os.path.exists(abs_path):
                warnings.append(f"导入的宏文件不存在：{import_path}")
                continue

            visited.add(abs_path)
            try:
                imported_rows = _load_json_with_comments(Path(abs_path))
                import_base_dir = os.path.dirname(abs_path)
                resolved.extend(resolve_imports(
                    imported_rows, import_base_dir, visited, warnings
                ))
            except Exception as exc:
                warnings.append(f"加载导入宏失败 {import_path}: {exc}")
            finally:
                visited.discard(abs_path)

        elif cmd == "loop":
            count = max(1, int(float(row[1])) if len(row) >= 2 else 1)
            block = row[2] if len(row) >= 3 and isinstance(row[2], list) else []
            resolved_block = resolve_imports(block, base_dir, visited, warnings)
            resolved.append(["loop", count, resolved_block])

        else:
            resolved.append(row)

    return resolved


def create_exporter(fmt: str, rows: list[list[Any]], is_v2: bool = False, synapse_version: int = 4,
                     logitech_ghub: bool = True, screen_width: int = 1920, screen_height: int = 1080,
                     fps: int | None = None) -> BaseExporter:
    frame_convert_count = 0
    if fps is not None:
        rows, frame_convert_count = _convert_frame_delays(rows, fps)

    exporters: dict[str, type[BaseExporter]] = {
        "razer": RazerXmlExporter,
        "logitech": LogitechLuaExporter,
        "ahk": AhkExporter,
        "xmouse": XmbcsExporter,
    }
    cls = exporters.get(fmt)
    if cls is None:
        raise ValueError(f"不支持的导出格式: {fmt} (支持: {', '.join(exporters.keys())})")
    if fmt == "ahk":
        exporter = cls(rows, is_v2=is_v2)
    elif fmt == "razer":
        exporter = cls(rows, synapse_version=synapse_version)
    elif fmt == "logitech":
        exporter = cls(rows, ghub=logitech_ghub, screen_width=screen_width, screen_height=screen_height)
    else:
        exporter = cls(rows)

    if frame_convert_count > 0:
        exporter.warnings.append(
            f"{frame_convert_count}处帧延迟已按{fps}fps转为ms，失去帧同步精度"
        )
    return exporter


def _load_json_with_comments(path: Path) -> list[Any]:
    raw = path.read_text(encoding="utf-8")
    stripped_lines: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith('//'):
            continue
        comment_idx = line.find('//')
        if comment_idx >= 0:
            in_string = False
            for i, ch in enumerate(line[:comment_idx]):
                if ch == '"' and (i == 0 or line[i - 1] != '\\'):
                    in_string = not in_string
            if not in_string:
                line = line[:comment_idx]
        stripped_lines.append(line)
    clean = '\n'.join(stripped_lines)
    return json.loads(clean)


def export_file(source_path: str, fmt: str, output_path: str | None = None, is_v2: bool = False,
                synapse_version: int = 4, logitech_ghub: bool = True,
                screen_width: int = 1920, screen_height: int = 1080,
                fps: int | None = None) -> Path:
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {source_path}")

    try:
        parsed = _load_json_with_comments(src)
    except json.JSONDecodeError as exc:
        raise ValueError(f"无法解析JSON源文件: {exc}")

    if not isinstance(parsed, list):
        raise ValueError("JSON源文件顶层必须是数组")

    import_warnings: list[str] = []
    base_dir = os.path.dirname(os.path.abspath(str(src)))
    parsed = resolve_imports(parsed, base_dir, warnings=import_warnings)

    exporter = create_exporter(fmt, parsed, is_v2=is_v2, synapse_version=synapse_version,
                               logitech_ghub=logitech_ghub, screen_width=screen_width, screen_height=screen_height,
                               fps=fps)
    output_text = exporter.export()

    if output_path is None:
        ext = _EXPORT_EXT_MAP.get(fmt, ".txt")
        out = src.with_suffix(ext)
    else:
        out = Path(output_path)

    out.write_text(output_text, encoding="utf-8")

    version_tag = ""
    if is_v2:
        version_tag = " v2"
    elif fmt == "razer":
        version_tag = f" v{synapse_version}"
    elif fmt == "logitech":
        version_tag = " G HUB" if logitech_ghub else " LGS"
    print(f"导出格式: {fmt}{version_tag}")
    print(f"源文件: {src}")
    print(f"输出: {out}")
    if import_warnings:
        for w in import_warnings:
            print(f"  Import警告: {w}")
    if exporter.warnings:
        for w in exporter.warnings:
            print(f"  警告: {w}")

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="宏格式转换器 - 支持导入/导出多种宏格式"
    )
    parser.add_argument("source_file", help="源宏文件路径")
    parser.add_argument(
        "--format",
        choices=["auto", "razer", "logitech", "ahk", "xmouse"],
        default="auto",
        help="源格式 (默认: auto, 根据文件扩展名自动检测)",
    )
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument(
        "--export",
        choices=["razer", "logitech", "ahk", "xmouse"],
        help="导出模式: 将项目JSON宏导出为指定外部格式",
    )
    parser.add_argument(
        "--ahk-v2",
        action="store_true",
        help="导出AHK时使用v2语法 (默认v1)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=60,
        help="导出时帧延迟(Nf)转ms的目标帧率 (默认: 60)",
    )

    args = parser.parse_args()

    try:
        if args.export:
            is_v2 = args.ahk_v2 if args.export == "ahk" else False
            # 检查是否含帧延迟，用默认fps时警告
            try:
                src = Path(args.source_file)
                if src.exists():
                    parsed = _load_json_with_comments(src)
                    if isinstance(parsed, list) and _has_frame_delay(parsed) and args.fps == 60:
                        print(f"警告: 宏含帧延迟，使用默认 {args.fps}fps 转换，可用 --fps 指定实际帧率")
            except Exception:
                pass
            export_file(args.source_file, args.export, args.output, is_v2=is_v2, fps=args.fps)
        else:
            fmt = args.format if args.format != "auto" else None
            convert_file(args.source_file, fmt, args.output)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
