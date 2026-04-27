# -*- coding: utf-8 -*-
"""
Windows 键盘急救修复脚本（不修改原宏执行框架）

用途：
1. 终止可能占用输入链路的宏相关 Python 进程
2. 强制解除 BlockInput
3. 批量发送 KeyUp/MouseUp，清理卡键与按住态

运行方式：
- 直接双击运行，或命令行执行：python 键盘急救修复.py
"""

import ctypes
import json
import os
import subprocess
import sys
import time
from typing import Dict, List


user32 = ctypes.windll.user32

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XUP = 0x0100
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", _INPUT_UNION),
    ]


def send_key_up(vk: int) -> None:
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, None)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def send_mouse_up(flags: int, mouse_data: int = 0) -> None:
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi = MOUSEINPUT(0, 0, mouse_data, flags, 0, None)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def unblock_input() -> None:
    # 若曾被 BlockInput(True) 锁定，这里尝试解除。
    try:
        user32.BlockInput(False)
    except Exception:
        pass


def release_common_keys() -> None:
    common_vks = [
        0x10, 0xA0, 0xA1,  # Shift / LShift / RShift
        0x11, 0xA2, 0xA3,  # Ctrl / LCtrl / RCtrl
        0x12, 0xA4, 0xA5,  # Alt / LAlt / RAlt
        0x5B, 0x5C,        # Win
        0x14, 0x90, 0x91,  # Caps/Num/Scroll Lock
        0x1B,              # Esc
    ]
    for vk in common_vks:
        send_key_up(vk)


def release_all_virtual_keys() -> None:
    # 通用清理：发送全范围 KeyUp，尽量消除“按下态遗留”。
    for vk in range(1, 255):
        send_key_up(vk)


def release_mouse_buttons() -> None:
    send_mouse_up(MOUSEEVENTF_LEFTUP)
    send_mouse_up(MOUSEEVENTF_RIGHTUP)
    send_mouse_up(MOUSEEVENTF_MIDDLEUP)
    send_mouse_up(MOUSEEVENTF_XUP, XBUTTON1)
    send_mouse_up(MOUSEEVENTF_XUP, XBUTTON2)


def _parse_json_safe(text: str):
    text = (text or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    return []


def kill_macro_python_processes() -> List[Dict[str, str]]:
    """终止命令行中包含宏脚本关键字的 python/pythonw 进程（不杀当前进程）。"""
    ps = r"""
$ErrorActionPreference = 'SilentlyContinue'
$rows = Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -match '^python(w)?\.exe$' -and
    $_.CommandLine -match '宏执行框架|webui_app\.py|interception_input_v2'
  } |
  Select-Object ProcessId, Name, CommandLine
$rows | ConvertTo-Json -Compress
"""

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=15,
            check=False,
        )
    except Exception:
        return []

    rows = _parse_json_safe(result.stdout)
    killed = []
    me = os.getpid()

    for row in rows:
        try:
            pid = int(row.get("ProcessId", 0))
        except Exception:
            continue
        if pid <= 0 or pid == me:
            continue

        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            killed.append({
                "pid": str(pid),
                "name": str(row.get("Name", "")),
                "cmd": str(row.get("CommandLine", ""))[:200],
            })
        except Exception:
            continue

    return killed


def run_recovery_round(round_idx: int) -> None:
    print(f"[急救] 执行恢复轮次 {round_idx} ...")
    unblock_input()
    release_common_keys()
    release_all_virtual_keys()
    release_mouse_buttons()


def main() -> int:
    print("=" * 56)
    print("[急救] 键盘输入恢复脚本启动")
    print("[急救] 将尝试终止宏进程 + 释放卡键 + 解除输入锁")
    print("=" * 56)

    killed = kill_macro_python_processes()
    if killed:
        print(f"[急救] 已终止可疑宏进程 {len(killed)} 个：")
        for item in killed:
            print(f"  PID={item['pid']} | {item['name']} | {item['cmd']}")
    else:
        print("[急救] 未发现可疑宏 Python 进程")

    for i in range(1, 4):
        run_recovery_round(i)
        time.sleep(0.15)

    print("[急救] 已完成。请立即测试外接键盘输入。")
    print("[急救] 若仍无效：请以管理员身份运行本脚本，再考虑重装 Interception 驱动。")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
