#!/usr/bin/env python3
"""
暴击率优化模拟器
目标：找到使"成功完成所有轮次"的平均总耗时最少的暴击率

规则：
  启动轮：前N次不暴击，后M次至少暴击K次
  后续轮：每轮若干次攻击，至少暴击K次
  失败后从第1轮重开，浪费的时间累加
"""

import numpy as np
from math import comb

# ============================================================
#  参数配置区（在这里修改你的游戏参数）
# ============================================================
PARAMS = {
    # 启动轮
    "start_round_time": 15,           # 启动轮耗时(s)
    "start_round_no_crit_first": 1,   # 启动轮 前N次必须不暴击
    "start_round_after_attacks": 2,   # 启动轮 后M次攻击
    "start_round_need_crit_after": 1, # 启动轮 后M次中至少暴击K次

    # 后续轮
    "subsequent_round_time": 19,      # 后续每轮耗时(s)
    "subsequent_attacks": 3,          # 后续每轮攻击次数
    "subsequent_need_crit": 1,        # 后续每轮至少暴击次数
    "n_subsequent_rounds": 5,         # 后续轮数
}


# ============================================================
#  方法1：精确计算（瞬间完成，推荐）
# ============================================================
def compute_expected_time(crit_rate, **kw):
    """用递推公式精确计算期望总耗时"""
    p = crit_rate
    cfg = {**PARAMS, **kw}

    # 启动轮通过概率
    no_crit_first = (1 - p) ** cfg["start_round_no_crit_first"]
    at_least_k_after = sum(
        comb(cfg["start_round_after_attacks"], i)
        * p ** i * (1 - p) ** (cfg["start_round_after_attacks"] - i)
        for i in range(cfg["start_round_need_crit_after"], cfg["start_round_after_attacks"] + 1)
    )
    q1 = no_crit_first * at_least_k_after

    # 后续轮通过概率
    q_sub = sum(
        comb(cfg["subsequent_attacks"], i)
        * p ** i * (1 - p) ** (cfg["subsequent_attacks"] - i)
        for i in range(cfg["subsequent_need_crit"], cfg["subsequent_attacks"] + 1)
    )

    n_total = 1 + cfg["n_subsequent_rounds"]
    qs = [q1] + [q_sub] * cfg["n_subsequent_rounds"]
    ts = [cfg["start_round_time"]] + [cfg["subsequent_round_time"]] * cfg["n_subsequent_rounds"]

    # E = sum(t_k * prod(q_j, j<k)) / prod(q_j)
    numerator = 0.0
    prefix_q = 1.0
    for i in range(n_total):
        numerator += prefix_q * ts[i]
        prefix_q *= qs[i]

    Q_total = prefix_q
    if Q_total < 1e-15:
        return float("inf")
    return numerator / Q_total


# ============================================================
#  方法2：蒙特卡洛模拟（验证用）
# ============================================================
def simulate_total_time(crit_rate, n_simulations=50000, **kw):
    """蒙特卡洛模拟，返回(均值, 标准误)"""
    p = crit_rate
    cfg = {**PARAMS, **kw}

    total_times = []
    for _ in range(n_simulations):
        acc = 0.0
        while True:
            # 启动轮
            acc += cfg["start_round_time"]
            ok = True
            for i in range(cfg["start_round_no_crit_first"]):
                if np.random.random() < p:
                    ok = False
                    break
            if ok:
                crit_cnt = sum(1 for _ in range(cfg["start_round_after_attacks"])
                               if np.random.random() < p)
                if crit_cnt < cfg["start_round_need_crit_after"]:
                    ok = False
            if not ok:
                continue

            # 后续轮
            all_ok = True
            for _ in range(cfg["n_subsequent_rounds"]):
                acc += cfg["subsequent_round_time"]
                crit_cnt = sum(1 for _ in range(cfg["subsequent_attacks"])
                               if np.random.random() < p)
                if crit_cnt < cfg["subsequent_need_crit"]:
                    all_ok = False
                    break
            if all_ok:
                total_times.append(acc)
                break

    arr = np.array(total_times)
    return np.mean(arr), np.std(arr) / np.sqrt(len(arr))


# ============================================================
#  主程序：扫描最优暴击率
# ============================================================
if __name__ == "__main__":
    # -------- 精确计算扫描 --------
    print("=" * 65)
    print("  暴击率优化器 — 精确计算")
    print("=" * 65)
    print(f"  启动轮: 前{PARAMS['start_round_no_crit_first']}次不暴击, "
          f"后{PARAMS['start_round_after_attacks']}次至少暴击{PARAMS['start_round_need_crit_after']}次, "
          f"耗时{PARAMS['start_round_time']}s")
    print(f"  后续轮: 每轮{PARAMS['subsequent_attacks']}次攻击, "
          f"至少暴击{PARAMS['subsequent_need_crit']}次, "
          f"每轮耗时{PARAMS['subsequent_round_time']}s, "
          f"共{PARAMS['n_subsequent_rounds']}轮")
    print()

    # 粗扫
    rates = np.arange(0.01, 0.99, 0.01)
    times = [compute_expected_time(p) for p in rates]
    times = np.array(times)
    best_idx = np.argmin(times)
    print(f"粗扫最优: 暴击率={rates[best_idx]:.2f}, 期望总耗时={times[best_idx]:.1f}s "
          f"(约{times[best_idx]/60:.1f}分钟)\n")

    # 细扫
    center = rates[best_idx]
    rates_fine = np.arange(max(0.001, center - 0.06), min(0.999, center + 0.06), 0.002)
    times_fine = [compute_expected_time(p) for p in rates_fine]
    times_fine = np.array(times_fine)
    best_idx2 = np.argmin(times_fine)
    best_p = rates_fine[best_idx2]
    best_t = times_fine[best_idx2]

    print(f"细扫最优: 暴击率={best_p:.3f}, 期望总耗时={best_t:.1f}s "
          f"(约{best_t/60:.1f}分钟)\n")

    # 打印附近数据表
    print("--- 暴击率 vs 期望总耗时 (附近) ---")
    print(f"{'暴击率':>8s}  {'期望耗时(s)':>12s}  {'(分钟)':>8s}  {'通过概率':>10s}")
    for i, p in enumerate(rates_fine):
        if abs(p - best_p) <= 0.04:
            Q_all = 1.0
            q1_p = (1-p)**2 * (1-(1-p)**2)
            q_sub_p = 1-(1-p)**4
            Q_all = q1_p * q_sub_p**5
            marker = " ◀ 最优" if p == best_p else ""
            print(f"  {p:6.3f}   {times_fine[i]:10.1f}   {times_fine[i]/60:6.1f}   {Q_all:8.4f}{marker}")

    # -------- 蒙特卡洛验证 --------
    print("\n" + "=" * 65)
    print("  蒙特卡洛验证 (20万次)")
    print("=" * 65)
    for p in [best_p - 0.04, best_p, best_p + 0.04]:
        if 0.01 <= p <= 0.98:
            m, se = simulate_total_time(p, n_simulations=200000)
            exact = compute_expected_time(p)
            print(f"  暴击率={p:.3f}  模拟={m:.1f}s  精确={exact:.1f}s  差异={abs(m-exact):.1f}s")

    # -------- 可视化 --------
    try:
        import matplotlib.pyplot as plt

        all_rates = np.arange(0.02, 0.98, 0.005)
        all_times = [compute_expected_time(p) for p in all_rates]

        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax1.plot(all_rates, all_times, "b-", linewidth=2)
        ax1.axvline(best_p, color="r", linestyle="--", label=f"最优暴击率={best_p:.3f}")
        ax1.axhline(best_t, color="gray", linestyle=":", alpha=0.5)
        ax1.set_xlabel("暴击率", fontsize=13)
        ax1.set_ylabel("期望总耗时 (秒)", fontsize=13)
        ax1.set_title("暴击率 vs 期望总耗时（含失败重开时间）", fontsize=14)
        ax1.legend(fontsize=12)
        ax1.grid(True, alpha=0.3)

        # 标注关键点
        ax1.annotate(f"最优: p={best_p:.3f}\n耗时={best_t:.0f}s",
                     xy=(best_p, best_t), xytext=(best_p + 0.1, best_t + 100),
                     arrowprops=dict(arrowstyle="->", color="red"),
                     fontsize=11, color="red")

        plt.tight_layout()
        plt.savefig("crit_rate_optimization.png", dpi=150)
        print("\n图表已保存: crit_rate_optimization.png")
    except ImportError:
        print("\n(未安装matplotlib，跳过绘图)")
