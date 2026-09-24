# -*- coding: utf-8 -*-
#
# 作者 / Author : 龙雨灿 Long Yucan (GitHub: yuna138)
# 仓库 / Repo   : https://github.com/yuna138/medical-logistics-simulation
# 版权 / License: MIT (c) 2026 Long Yucan. 保留署名权，转载请注明出处。
#
"""
结果可视化：从 results/*.csv 生成论文级图表（SVG）。

运行：python make_figures.py（需先跑完 run_simulation.py）
输出：results/fig1..fig4
"""

import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "results")
os.makedirs(OUT, exist_ok=True)

C_RED, C_BLUE, C_GRAY = "#C0392B", "#2471A3", "#7F8C8D"
CLASS_NAME = {"critical": "致命类", "emergency": "突发类",
              "seasonal": "季节类", "routine": "常规类"}


def read_csv(name):
    with open(os.path.join(OUT, name), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fig1_demand_profile():
    """图1：四类药品的 30 天订单量与全天需求强度曲线"""
    recs = read_csv("records_baseline_5_7.csv")
    daily = defaultdict(lambda: [0] * 30)
    for r in recs:
        daily[r["class"]][int(float(r["t"]) // 24)] += 1

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.8))
    for key in ("critical", "emergency", "seasonal", "routine"):
        ax1.plot(range(1, 31), daily[key], label=CLASS_NAME[key], lw=1.4)
    ax1.set_xlabel("仿真天数"); ax1.set_ylabel("订单量（单/天）")
    ax1.set_title("(a) 30 天订单量（基准情景）"); ax1.legend(fontsize=8)
    ax1.spines[["top", "right"]].set_visible(False)

    from simulation.network import HOUR_PROFILE
    ax2.bar(range(24), HOUR_PROFILE, color=C_BLUE, alpha=0.85)
    ax2.set_xlabel("小时"); ax2.set_ylabel("需求强度系数")
    ax2.set_title("(b) 全天需求强度曲线（非齐次泊松）")
    ax2.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig1_demand_profile.png"), dpi=150)
    plt.close(fig)


def fig2_response_dist():
    """图2：高时效订单响应时间分布 —— 基准 vs 突发（5+7 被击穿）"""
    base = [r for r in read_csv("records_baseline_5_7.csv")
            if r["class"] in ("critical", "emergency")]
    surge = [r for r in read_csv("records_surge_5_7.csv")
             if r["class"] in ("critical", "emergency")]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bins = [i * 0.25 for i in range(0, 41)]
    ax.hist([float(r["response_h"]) for r in base], bins=bins,
            alpha=0.65, label="基准需求 5+7", color=C_BLUE, density=True)
    ax.hist([min(float(r["response_h"]), 10.0) for r in surge], bins=bins,
            alpha=0.65, label="突发4倍 5+7（被击穿）", color=C_RED, density=True)
    ax.axvline(2.0, color="k", ls="--", lw=1.2)
    ax.text(2.1, ax.get_ylim()[1] * 0.9, "致命类 SLA = 2h", fontsize=9)
    ax.set_xlabel("响应时间（小时）"); ax.set_ylabel("密度")
    ax.set_title("温控车订单响应时间分布：突发需求下 5+7 配置被击穿")
    ax.legend(); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig2_response_dist.png"), dpi=150)
    plt.close(fig)


def fig3_fleet_sweep():
    """图3（核心图）：红线超时率随温控车数量的变化 —— 16 辆实现零超时"""
    sweep = read_csv("fleet_sweep.csv")
    xs = [int(r["n_red"]) for r in sweep]
    ot = [float(r["overtime_rate_red"]) * 100 for r in sweep]
    util = [float(r["red_util"]) * 100 for r in sweep]
    fig, ax1 = plt.subplots(figsize=(7.2, 4.4))
    ax1.plot(xs, ot, "o-", color=C_RED, lw=2, label="红线（致命+突发）超时率")
    ax1.axhline(0.5, color=C_GRAY, ls=":", lw=1)
    ax1.text(5.2, 1.2, "近零超时线", fontsize=8, color=C_GRAY)
    ax1.set_xlabel("温控车数量（辆，普冷车固定 7 辆）")
    ax1.set_ylabel("超时率（%）", color=C_RED)
    ax1.tick_params(axis="y", labelcolor=C_RED)
    ax1.spines[["top"]].set_visible(False)
    ax2 = ax1.twinx()
    ax2.plot(xs, util, "s--", color=C_BLUE, lw=1.4, label="温控车利用率")
    ax2.set_ylabel("利用率（%）", color=C_BLUE)
    ax2.tick_params(axis="y", labelcolor=C_BLUE)
    ax2.spines[["top"]].set_visible(False)
    # 标注 16 辆
    i16 = xs.index(16) if 16 in xs else None
    if i16 is not None:
        ax1.annotate("16 辆：零超时安全配置",
                     xy=(16, ot[i16]), xytext=(10.5, max(ot) * 0.55),
                     arrowprops=dict(arrowstyle="->", color="k"),
                     fontsize=10, fontweight="bold")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper right")
    ax1.set_title("突发情景下运力扫描：超时率与利用率的权衡")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig3_fleet_sweep.png"), dpi=150)
    plt.close(fig)


def fig4_scenario_compare():
    """图4：三情景核心指标对比（堆叠柱状）"""
    rows = read_csv("scenario_summary.csv")
    scen = [("baseline_5_7", "基准 5+7"), ("surge_5_7", "突发4x 5+7"),
            ("surge_16_7", "突发4x 16+7")]
    labels = [s[1] for s in scen]
    crit_ot, emer_ot = [], []
    for key, _ in scen:
        c = next(r for r in rows if r["scenario"] == key and r["drug_class"] == "critical")
        e = next(r for r in rows if r["scenario"] == key and r["drug_class"] == "emergency")
        crit_ot.append(float(c["overtime_rate"]) * 100)
        emer_ot.append(float(e["overtime_rate"]) * 100)
    import numpy as np
    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(x - 0.18, crit_ot, 0.36, label="致命类超时率", color=C_RED)
    ax.bar(x + 0.18, emer_ot, 0.36, label="突发类超时率", color="#E67E22")
    for xi, (a, b) in enumerate(zip(crit_ot, emer_ot)):
        ax.text(xi - 0.18, a + 0.4, f"{a:.1f}%", ha="center", fontsize=9)
        ax.text(xi + 0.18, b + 0.4, f"{b:.1f}%", ha="center", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("超时率（%）")
    ax.set_title("三情景高时效订单超时率对比")
    ax.legend(); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig4_scenario_compare.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(HERE, ".."))
    fig1_demand_profile()
    fig2_response_dist()
    fig3_fleet_sweep()
    fig4_scenario_compare()
    print("figures saved to", os.path.abspath(OUT))
