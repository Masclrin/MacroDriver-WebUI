#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
运行测试宏 — 配合 调试_RawInput探针.py 使用

加载并执行 Raw Input 探针生成的测试宏文件。
在探针脚本启动后，在新终端中运行此脚本。

用法:
  python 运行测试宏.py
  python 运行测试宏.py --macro "宏\RawInput探针测试宏.json"
  python 运行测试宏.py --interval-ms 1 --events 500
"""

import argparse
import importlib.util
import os
import sys
import threading
import time


def load_framework(framework_path: str):
    """加载宏执行框架模块。

    需要将框架所在目录加入 sys.path，以便框架内的 from engine.xxx 等导入能正常工作。
    """
    framework_dir = os.path.dirname(os.path.abspath(framework_path))
    if framework_dir not in sys.path:
        sys.path.insert(0, framework_dir)

    spec = importlib.util.spec_from_file_location("macro_framework", framework_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载框架: {framework_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def generate_test_macro_inline(output_path: str, interval_ms: float, total_events: int) -> str:
    """生成 F13/F14 交替的测试宏文件（与探针脚本中的逻辑一致）。"""
    loop_steps = 4
    if total_events % loop_steps != 0:
        total_events = (total_events // loop_steps) * loop_steps

    loop_count = total_events // loop_steps
    interval_str = str(interval_ms)

    lines = ["["]
    lines.append(f'    // 自动生成的 Raw Input 探针测试宏')
    lines.append(f'    // 按键: F13/F14 交替 | 间隔: {interval_ms}ms | 事件数: {total_events}')
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
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="运行测试宏（配合 Raw Input 探针使用）")
    parser.add_argument("--macro", type=str, default=None,
                        help="宏文件路径（默认 宏/RawInput探针测试宏.json）")
    parser.add_argument("--interval-ms", type=float, default=1.0,
                        help="如需要生成宏：事件间隔（毫秒），默认 1.0")
    parser.add_argument("--events", type=int, default=500,
                        help="如需要生成宏：事件数，默认 500")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="速度倍率，默认 1.0")
    parser.add_argument("--delay-before", type=float, default=3.0,
                        help="执行前等待秒数（给探针准备时间），默认 3.0")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    framework_path = os.path.join(project_dir, "宏执行框架3.2.py")

    if not os.path.exists(framework_path):
        # 尝试 test 目录下的框架
        framework_path = os.path.join(script_dir, "宏执行框架1.9.py")
    if not os.path.exists(framework_path):
        raise FileNotFoundError(f"未找到宏执行框架: {framework_path}")

    macro_path = args.macro or os.path.join(project_dir, "宏", "RawInput探针测试宏.json")

    # 如果宏文件不存在，自动生成
    if not os.path.exists(macro_path):
        print(f"[宏运行] 宏文件不存在，自动生成: {macro_path}")
        generate_test_macro_inline(macro_path, args.interval_ms, args.events)
    else:
        print(f"[宏运行] 使用现有宏文件: {macro_path}")

    print(f"[宏运行] 加载框架: {framework_path}")
    framework = load_framework(framework_path)

    print(f"[宏运行] 加载宏文件...")
    script = framework.load_macro_from_file(macro_path)
    print(f"[宏运行] 原始指令: {len(script)} 条")

    print(f"[宏运行] 编译宏...")
    compiled = framework.compile_macro(script)
    print(f"[宏运行] 编译后动作: {len(compiled)} 个")

    delay = args.delay_before
    print(f"[宏运行] {delay} 秒后开始执行... (请确保探针已启动)")
    for i in range(int(delay), 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    print(f"[宏运行] 开始执行宏! (速度倍率: {args.speed}x)")
    stop_event = threading.Event()
    pause_event = threading.Event()

    options = {"speed_factor": args.speed}
    try:
        framework.execute_macro_once(compiled, stop_event, pause_event, "RawInput探针测试宏", options)
    except KeyboardInterrupt:
        print("\n[宏运行] 用户中断")
        stop_event.set()
    except Exception as e:
        print(f"[宏运行] 执行出错: {e}")

    print("[宏运行] 完成")


if __name__ == "__main__":
    main()