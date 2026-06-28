#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""快速测试单个宏的探针捕获"""

import os, sys, subprocess, time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(PROJECT_DIR, "test")
ARTIFACTS_DIR = os.path.join(TEST_DIR, "artifacts")

name = "魔导火-大轮"
timeline = os.path.join(ARTIFACTS_DIR, "expected_timeline_魔导火大轮.json")
macro = os.path.join(PROJECT_DIR, "宏", "RawInput_魔导火大轮.json")
csv_path = os.path.join(ARTIFACTS_DIR, f"probe_result_{name}.csv")

# 清理旧CSV
if os.path.exists(csv_path):
    os.remove(csv_path)

# 启动探针（不过滤VK，接收所有事件）
probe_cmd = [
    sys.executable,
    os.path.join(TEST_DIR, "调试_RawInput探针.py"),
    "--expected-timeline", timeline,
    "--events", "83",
    "--timeout-sec", "60",
    "--csv", csv_path,
]

print("[1] 启动探针...")
probe = subprocess.Popen(probe_cmd, cwd=TEST_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

time.sleep(4)

# 运行宏
runner_cmd = [
    sys.executable,
    os.path.join(TEST_DIR, "运行测试宏.py"),
    "--macro", macro,
    "--delay-before", "1",
]
print("[2] 执行宏...")
runner = subprocess.run(runner_cmd, cwd=TEST_DIR, capture_output=True, text=True)
print(runner.stdout[-1500:] if len(runner.stdout) > 1500 else runner.stdout)

# 等待探针完成
print("[3] 等待探针完成...")
try:
    out, _ = probe.communicate(timeout=60)
except subprocess.TimeoutExpired:
    probe.kill()
    out, _ = probe.communicate()

# 保存日志
log_path = os.path.join(ARTIFACTS_DIR, f"probe_log_{name}.txt")
with open(log_path, "w", encoding="utf-8") as f:
    f.write(out)

# 打印探针输出
print("\n=== 探针输出 ===")
print(out[-2000:] if len(out) > 2000 else out)

# 检查CSV
if os.path.exists(csv_path):
    with open(csv_path, "r") as f:
        lines = f.readlines()
    print(f"\n=== CSV 前5行 ===")
    for line in lines[:5]:
        print(line.strip())
    print(f"... 共 {len(lines)-1} 条事件记录")
else:
    print("\n[!] CSV未生成!")