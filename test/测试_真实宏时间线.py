#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
真实宏时间线测试 — 用项目中的真实宏检验时间线精度波动

工作流程:
  1. 加载一个真实宏文件 → 编译 → 提取完整延迟序列
  2. 生成键盘版测试宏（F13键，保持相同延迟序列）
  3. 保存预期时间轴 JSON
  4. 启动探针 + 执行宏 → 在黑盒层面测量每个动作的实际时间点
  5. 对比实际 vs 预期 → 输出漂移报告

用法:
  # 第一步：预处理真实宏，生成测试宏和预期时间轴
  python 测试_真实宏时间线.py --macro "..\宏\预设宏\魔导火-大轮.json" --preprocess-only

  # 第二步：终端1 — 启动探针
  cd test
  python 调试_RawInput探针.py --expected-timeline artifacts\expected_timeline.json --filter-vk F13 --events N
  
  # 第三步：终端2 — 执行宏
  cd test
  python 运行测试宏.py --macro "..\宏\RawInput真实宏测试.json"
"""

import argparse
import importlib.util
import json
import os
import sys
import math
import statistics


def load_framework(framework_path: str):
    """与 运行测试宏.py 一致的框架加载方式。"""
    framework_dir = os.path.dirname(os.path.abspath(framework_path))
    if framework_dir not in sys.path:
        sys.path.insert(0, framework_dir)
    spec = importlib.util.spec_from_file_location("macro_framework", framework_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载框架: {framework_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_delays(compiled_macro):
    """从编译后的宏中提取延迟序列（微秒）。

    compiled_macro 格式: [(func, delay_s, action_type, action_desc, raw_info), ...]
    返回: [delay_us, ...]
    """
    delays_us = []
    for item in compiled_macro:
        delay_s = item[1]  # 第二个元素是延迟（秒）
        delay_us = delay_s * 1_000_000.0
        delays_us.append(delay_us)
    return delays_us


def generate_keyboard_test_macro(delays_us, output_path: str):
    """根据延迟序列生成键盘测试宏（扁平列表）。

    交替发送 F13 down/up，每个延迟值对应一个事件。
    输出格式是扁平 JSON 数组，每条指令独立。
    """
    lines = ["["]
    lines.append(f'    // 从真实宏提取的延迟序列测试宏')
    lines.append(f'    // 步数: {len(delays_us)}')
    total_ms = sum(delays_us) / 1000.0
    lines.append(f'    // 总时长: {total_ms:.1f}ms ({total_ms/1000:.3f}s)')
    lines.append(f'    // 每步: F13↓/↑ 交替')

    for i, delay_us in enumerate(delays_us):
        delay_ms = delay_us / 1000.0
        key = "F13"
        action = "kd" if i % 2 == 0 else "ku"
        comma = "," if i < len(delays_us) - 1 else ""
        delay_str = f"{delay_ms:.6f}" if delay_ms != int(delay_ms) else str(int(delay_ms))
        lines.append(f'    ["{action}", "{key}", {delay_str}]{comma}')

    lines.append(']')

    content = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    n_events = len(delays_us)
    print(f"[生成] 键盘测试宏: {output_path}")
    print(f"       动作数: {n_events}")
    print(f"       总时长: {total_ms:.1f}ms ({total_ms/1000:.3f}s)")


def save_expected_timeline(delays_us, output_path: str):
    """保存预期时间轴 JSON（微秒间隔列表）。"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(delays_us, f, ensure_ascii=False)
    print(f"[生成] 预期时间轴: {output_path} ({len(delays_us)} 步)")


def print_delay_statistics(delays_us):
    """打印延迟统计信息。"""
    n = len(delays_us)
    if n == 0:
        return
    s = sorted(delays_us)
    p50 = s[int(n * 0.50)] if n > 1 else s[0]
    p95 = s[int(n * 0.95)] if n > 1 else s[0]
    p99 = s[int(n * 0.99)] if n > 1 else s[0]
    mean = sum(s) / n
    print()
    print("=" * 60)
    print("真实宏 — 延迟分析")
    print("=" * 60)
    print(f"  总步数:          {n}")
    print(f"  总时长:          {sum(delays_us)/1e6:.3f}s")
    print(f"  平均延迟:        {mean:.1f}us ({mean/1000:.3f}ms)")
    print(f"  最小延迟:        {s[0]:.1f}us ({s[0]/1000:.3f}ms)")
    print(f"  最大延迟:        {s[-1]:.1f}us ({s[-1]/1000:.3f}ms)")
    print(f"  P50:             {p50:.1f}us ({p50/1000:.3f}ms)")
    print(f"  P95:             {p95:.1f}us ({p95/1000:.3f}ms)")
    print(f"  P99:             {p99:.1f}us ({p99/1000:.3f}ms)")

    # 分段统计
    buckets = [(0, 1000, "1ms以下"), (1000, 5000, "1-5ms"), (5000, 20000, "5-20ms"),
               (20000, 50000, "20-50ms"), (50000, 100000, "50-100ms"),
               (100000, 300000, "100-300ms"), (300000, 1000000, "300-1000ms"),
               (1000000, float("inf"), "1000ms以上")]
    print()
    print("  延迟分布:")
    for lo, hi, label in buckets:
        count = sum(1 for v in delays_us if lo <= v < hi)
        if count > 0:
            bar = "#" * max(1, int(count / n * 80))
            print(f"    {label:>12}: {count:>5} ({count*100/n:5.1f}%) {bar}")


def post_analyze_csv(csv_path: str, expected_timeline_path: str, top_n_errors: int = 10):
    """对探针 CSV 输出进行后分析：漂移趋势分析。"""
    print()
    print("=" * 60)
    print("漂移后分析")
    print("=" * 60)

    # 加载预期时间轴
    with open(expected_timeline_path, "r", encoding="utf-8") as f:
        expected_intervals_us = json.load(f)

    # 读取 CSV
    import csv
    events = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(row)

    if not events:
        print("CSV 为空，无法分析。")
        return

    macro_events = [e for e in events if e["stepIndex"] != ""]
    n_expected = len(expected_intervals_us)
    n_actual = len(macro_events)

    print(f"  预期事件数: {n_expected}")
    print(f"  捕获事件数: {n_actual}")
    print(f"  捕获完整度: {n_actual * 100.0 / n_expected:.1f}%" if n_expected > 0 else "  N/A")

    if n_actual < 2:
        print("  事件数不足，跳过漂移分析。")
        return

    # 解析漂移值
    drifts_us = []
    for ev in macro_events:
        try:
            drift = float(ev["cumulativeDriftUs"])
            drifts_us.append(drift)
        except (ValueError, KeyError):
            continue

    if not drifts_us:
        print("  无漂移数据。")
        return

    # 漂移统计
    s = sorted(drifts_us)
    n = len(s)
    print()
    print("  累积漂移统计（带符号，正=滞后，负=提前）:")
    print(f"    最小:     {s[0]:+.3f}us")
    print(f"    最大:     {s[-1]:+.3f}us")
    print(f"    平均:     {sum(s)/n:+.3f}us")
    print(f"    P50:      {s[int(n*0.50)]:+.3f}us")
    print(f"    P95:      {s[int(n*0.95)]:+.3f}us")
    print(f"    P99:      {s[int(n*0.99)]:+.3f}us")
    print(f"    范围:     {s[-1]-s[0]:.3f}us")

    # 漂移绝对值
    abs_drifts = [abs(d) for d in drifts_us]
    sa = sorted(abs_drifts)
    print()
    print("  漂移绝对值统计:")
    print(f"    P50:      {sa[int(n*0.50)]:.3f}us")
    print(f"    P95:      {sa[int(n*0.95)]:.3f}us")
    print(f"    P99:      {sa[int(n*0.99)]:.3f}us")
    print(f"    最大:     {sa[-1]:.3f}us")

    # 间隔误差分析
    print()
    print("  步间误差分析:")
    interval_errors = []
    for i in range(1, len(macro_events)):
        try:
            prev_relative = float(macro_events[i - 1].get("relativeUs", 0))
            curr_relative = float(macro_events[i].get("relativeUs", 0))
            actual_interval = curr_relative - prev_relative
            expected_interval = expected_intervals_us[i] if i < len(expected_intervals_us) else expected_intervals_us[-1]
            error = actual_interval - expected_interval
            interval_errors.append(abs(error))
        except (ValueError, KeyError, IndexError):
            continue

    if interval_errors:
        se = sorted(interval_errors)
        print(f"    数量:     {len(se)}")
        print(f"    平均:     {sum(se)/len(se):.3f}us")
        print(f"    P50:      {se[int(len(se)*0.50)]:.3f}us")
        print(f"    P95:      {se[int(len(se)*0.95)]:.3f}us")
        print(f"    P99:      {se[int(len(se)*0.99)]:.3f}us")
        print(f"    最大:     {se[-1]:.3f}us")

    # 趋势分析：将漂移按窗口分段，看变化趋势
    window_size = max(10, n_actual // 20)
    print()
    print(f"  漂移趋势（每{window_size}步平均）:")
    for start in range(0, n_actual, window_size):
        end = min(start + window_size, n_actual)
        window_drifts = drifts_us[start:end]
        if window_drifts:
            avg = sum(window_drifts) / len(window_drifts)
            bar_len = max(1, int(abs(avg) / 500))
            direction = "+" if avg > 0 else "-"
            print(f"    步 {start:>5}-{end:>5}: avg={avg:+.1f}us {'#' * bar_len}{direction}")

    # 找出最大漂移的步骤
    if top_n_errors > 0:
        worst = sorted(enumerate(drifts_us), key=lambda x: abs(x[1]), reverse=True)[:top_n_errors]
        print()
        print(f"  最大漂移 TOP{top_n_errors}:")
        for step_idx, drift in worst:
            expected_int = expected_intervals_us[step_idx] / 1000.0 if step_idx < len(expected_intervals_us) else 0
            print(f"    步 {step_idx:>5}: {drift:+.1f}us  (预期间隔={expected_int:.2f}ms)")


def main():
    parser = argparse.ArgumentParser(
        description="真实宏时间线测试 — 用项目中的真实宏检验时间线精度波动",
    )
    parser.add_argument("--macro", type=str, default=None,
                        help="真实宏文件路径（相对于项目根目录或绝对路径）")
    parser.add_argument("--preprocess-only", action="store_true",
                        help="仅预处理（编译+生成测试宏+时间轴），不运行测试")
    parser.add_argument("--framework", type=str, default=None,
                        help="宏执行框架路径（默认 宏执行框架3.2.py）")
    parser.add_argument("--output-macro", type=str, default=None,
                        help="生成的测试宏路径（默认 宏/RawInput真实宏测试.json）")
    parser.add_argument("--output-timeline", type=str, default=None,
                        help="预期时间轴 JSON 路径（默认 test/artifacts/expected_timeline.json）")
    parser.add_argument("--post-analyze", type=str, default=None,
                        help="后分析模式：指定 CSV 路径进行分析")
    parser.add_argument("--expected-timeline", type=str, default=None,
                        help="后分析模式：指定预期时间轴 JSON 路径")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    # ── 后分析模式 ──
    if args.post_analyze:
        expected_timeline = args.expected_timeline or os.path.join(script_dir, "artifacts", "expected_timeline.json")
        if not os.path.exists(expected_timeline):
            print(f"[错误] 预期时间轴文件不存在: {expected_timeline}")
            return
        post_analyze_csv(args.post_analyze, expected_timeline)
        return

    # ── 预处理模式 ──
    if not args.macro:
        parser.print_help()
        print("\n[错误] 预处理模式需要 --macro 参数")
        return
    # 确定宏文件路径
    macro_path = args.macro
    if not os.path.isabs(macro_path):
        macro_path = os.path.join(project_dir, macro_path)
    if not os.path.exists(macro_path):
        print(f"[错误] 宏文件不存在: {macro_path}")
        return

    # 加载框架
    framework_path = args.framework or os.path.join(project_dir, "宏执行框架3.2.py")
    if not os.path.exists(framework_path):
        framework_path = os.path.join(project_dir, "宏执行框架1.9.py")
    if not os.path.exists(framework_path):
        print(f"[错误] 框架不存在: {framework_path}")
        return

    print(f"[加载] 宏: {macro_path}")
    print(f"[加载] 框架: {framework_path}")
    framework = load_framework(framework_path)

    # 加载宏
    print("[编译] 正在加载宏（递归展开 import 和 loop）...")
    try:
        script = framework.load_macro_from_file(macro_path)
    except AttributeError:
        # 尝试旧版 API
        script = framework.load_macro_recursive(macro_path)
        
    print(f"[编译] 原始指令: {len(script)} 条")

    print("[编译] 编译宏...")
    compiled = framework.compile_macro(script)
    print(f"[编译] 编译后动作: {len(compiled)} 个")

    # 提取延迟序列
    delays_us = extract_delays(compiled)
    print(f"[分析] 提取延迟序列: {len(delays_us)} 步")

    # 打印延迟统计
    print_delay_statistics(delays_us)

    # 输出路径
    macro_name = os.path.splitext(os.path.basename(macro_path))[0]
    output_macro = args.output_macro or os.path.join(project_dir, "宏", "RawInput真实宏测试.json")
    output_timeline = args.output_timeline or os.path.join(script_dir, "artifacts", "expected_timeline.json")

    # 生成键盘测试宏
    generate_keyboard_test_macro(delays_us, output_macro)

    # 保存预期时间轴
    save_expected_timeline(delays_us, output_timeline)

    if args.preprocess_only:
        print()
        print("=" * 60)
        print("预处理完成! 运行测试:")
        print("=" * 60)
        print()
        print("  终端1 (探针):")
        print(f"    cd \"{script_dir}\"")
        print(f"    python 调试_RawInput探针.py --expected-timeline \"{output_timeline}\" --filter-vk F13 --events {len(delays_us)}")
        print()
        print(f"  终端2 (宏执行):")
        print(f"    cd \"{script_dir}\"")
        print(f"    python 运行测试宏.py --macro \"{output_macro}\" --delay-before 3")
        print()
        print("  后分析:")
        print(f"    python 测试_真实宏时间线.py --post-analyze \"{script_dir}\\artifacts\\rawinput_probe_1ms.csv\" --expected-timeline \"{output_timeline}\"")
        print()
    else:
        print()
        print("[信息] 默认仅预处理。使用 --preprocess-only 查看运行命令。")
        print()


if __name__ == "__main__":
    main()
