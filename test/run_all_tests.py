#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
自动化宏精度测试编排 — 对多个真实宏运行探针+执行+后分析
"""

import json
import os
import subprocess
import sys
import time
import threading

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(PROJECT_DIR, "test")
ARTIFACTS_DIR = os.path.join(TEST_DIR, "artifacts")
PROBE_SCRIPT = os.path.join(TEST_DIR, "调试_RawInput探针.py")
RUNNER_SCRIPT = os.path.join(TEST_DIR, "运行测试宏.py")
ANALYZE_SCRIPT = os.path.join(TEST_DIR, "测试_真实宏时间线.py")

TESTS = [
    {
        "name": "魔导火-大轮",
        "macro": os.path.join(PROJECT_DIR, "宏", "RawInput_魔导火大轮.json"),
        "timeline": os.path.join(ARTIFACTS_DIR, "expected_timeline_魔导火大轮.json"),
        "events": 83,
    },
    {
        "name": "魔导火首轮",
        "macro": os.path.join(PROJECT_DIR, "宏", "RawInput_魔导火首轮.json"),
        "timeline": os.path.join(ARTIFACTS_DIR, "expected_timeline_魔导火首轮.json"),
        "events": 83,
    },
    {
        "name": "魔导火-2轮aesz",
        "macro": os.path.join(PROJECT_DIR, "宏", "RawInput_魔导火2轮aesz.json"),
        "timeline": os.path.join(ARTIFACTS_DIR, "expected_timeline_魔导火2轮aesz.json"),
        "events": 104,
    },
    {
        "name": "蒸火",
        "macro": os.path.join(PROJECT_DIR, "宏", "RawInput_蒸火.json"),
        "timeline": os.path.join(ARTIFACTS_DIR, "expected_timeline_蒸火.json"),
        "events": 76,
    },
]


def run_probe_and_macro(test, timeout_sec=90):
    """在一个函数内启动探针和执行宏，返回CSV路径和探针输出。"""
    name = test["name"]
    csv_path = os.path.join(ARTIFACTS_DIR, f"probe_result_{name}.csv")
    log_path = os.path.join(ARTIFACTS_DIR, f"probe_log_{name}.txt")

    # 清理旧CSV
    if os.path.exists(csv_path):
        os.remove(csv_path)

    # 构建探针命令
    probe_cmd = [
        sys.executable, PROBE_SCRIPT,
        "--expected-timeline", test["timeline"],
        "--events", str(test["events"]),
        "--timeout-sec", str(timeout_sec),
        "--csv", csv_path,
    ]

    # 构建宏运行命令
    runner_cmd = [
        sys.executable, RUNNER_SCRIPT,
        "--macro", test["macro"],
        "--delay-before", "1",
    ]

    print(f"\n{'='*60}")
    print(f"  测试: {name}")
    print(f"  宏: {test['macro']}")
    print(f"  事件数: {test['events']}")
    print(f"{'='*60}")

    # 启动探针 (子进程)
    print("[步骤1] 启动 RawInput 探针...")
    probe_proc = subprocess.Popen(
        probe_cmd,
        cwd=TEST_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # 等待探针初始化
    print("[步骤2] 等待 4 秒让探针初始化...")
    time.sleep(4)

    # 检查探针是否还在运行
    if probe_proc.poll() is not None:
        output = probe_proc.stdout.read()
        print(f"[错误] 探针提前退出:\n{output}")
        return None, None

    # 运行宏
    print("[步骤3] 执行宏...")
    runner_result = subprocess.run(
        runner_cmd,
        cwd=TEST_DIR,
        capture_output=True,
        text=True,
    )
    print(runner_result.stdout)
    if runner_result.stderr:
        print(f"[宏stderr]: {runner_result.stderr}")

    # 等待探针完成
    print("[步骤4] 等待探针完成...")
    try:
        probe_stdout, _ = probe_proc.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        print(f"[警告] 探针超时 ({timeout_sec}s)，强制终止")
        probe_proc.kill()
        probe_stdout, _ = probe_proc.communicate()

    # 保存探针日志
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(probe_stdout)
    print(f"[探针日志已保存: {log_path}]")

    # 检查CSV
    if os.path.exists(csv_path):
        print(f"[结果] CSV 已生成: {csv_path}")
    else:
        print(f"[警告] CSV 未生成!")
        # 打印探针输出最后几行
        lines = probe_stdout.strip().split("\n")
        for line in lines[-20:]:
            print(f"  {line}")

    return csv_path, log_path


def post_analyze(csv_path, timeline_path):
    """运行后分析。"""
    if not csv_path or not os.path.exists(csv_path):
        print("[后分析] CSV 不可用，跳过")
        return ""

    cmd = [
        sys.executable, ANALYZE_SCRIPT,
        "--post-analyze", csv_path,
        "--expected-timeline", timeline_path,
    ]
    result = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True)
    output = result.stdout
    if result.stderr:
        output += f"\n[stderr]\n{result.stderr}"
    print(output)
    return output


def main():
    all_results = []

    for test in TESTS:
        # 检查文件是否存在
        if not os.path.exists(test["timeline"]):
            print(f"[跳过] 预期时间轴不存在: {test['timeline']}")
            continue
        if not os.path.exists(test["macro"]):
            print(f"[跳过] 宏文件不存在: {test['macro']}")
            continue

        csv_path, log_path = run_probe_and_macro(test)

        # 后分析
        print(f"[步骤5] 运行后分析...")
        analysis = post_analyze(csv_path, test["timeline"])

        all_results.append({
            "name": test["name"],
            "csv": csv_path,
            "log": log_path,
            "analysis": analysis,
        })

        time.sleep(2)  # 间隔

    # 打印汇总
    print("\n")
    print("=" * 60)
    print("  全部测试完成! 汇总:")
    print("=" * 60)
    for r in all_results:
        print(f"  {r['name']}: CSV={r['csv']}, Log={r['log']}")


if __name__ == "__main__":
    main()