# -*- coding: utf-8 -*-
#
# 作者 / Author : 龙雨灿 Long Yucan (GitHub: yuna138)
# 仓库 / Repo   : https://github.com/yuna138/medical-logistics-simulation
# 版权 / License: MIT (c) 2026 Long Yucan. 保留署名权，转载请注明出处。
#
"""
实验入口：三个核心情景 + 温控车数量扫描。

情景设计（与项目结论一致）：
1. baseline   —— 基准需求，5 温控 + 7 普冷：够用（近零超时）
2. surge      —— 突发类需求放大 4 倍且成簇到达，5 + 7：被击穿
3. recommended—— 突发情景下温控车增至 16 辆：零超时安全冗余配置

运行：python run_simulation.py
输出：results/*.csv
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dispatch import run_simulation
from network import FLEET_PARAMS, SIM_DAYS

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
SEEDS = [42, 43, 44, 45, 46]   # 多种子取均值，保证结论稳定


def ensure_out():
    os.makedirs(OUT_DIR, exist_ok=True)


def avg_result(n_red, n_blue, surge):
    """多种子运行取平均（逐单记录取第一个种子的，用于画分布图）"""
    runs = [run_simulation(n_red, n_blue, surge=surge, seed=s) for s in SEEDS]
    agg = {
        "n_red": n_red, "n_blue": n_blue, "surge": surge,
        "by_class": {}, "records": runs[0]["records"],
        "red_util": sum(r["red_util"] for r in runs) / len(runs),
        "blue_util": sum(r["blue_util"] for r in runs) / len(runs),
    }
    for key in runs[0]["by_class"]:
        agg["by_class"][key] = {
            k: sum(r["by_class"][key][k] for r in runs) / len(runs)
            for k in ("orders", "overtime", "overtime_rate",
                      "resp_mean", "resp_p95", "resp_max")
        }
    return agg


def main():
    ensure_out()
    r_red, r_blue_rec = FLEET_PARAMS["red_recommended"], FLEET_PARAMS["blue_base"]

    # ---------- 情景 1：基准 5+7 ----------
    base = avg_result(FLEET_PARAMS["red_base"], FLEET_PARAMS["blue_base"], surge=False)
    # ---------- 情景 2：突发 4 倍 5+7 ----------
    surge = avg_result(FLEET_PARAMS["red_base"], FLEET_PARAMS["blue_base"], surge=True)
    # ---------- 情景 3：突发 4 倍 16+7 ----------
    rec = avg_result(r_red, r_blue_rec, surge=True)

    # ---------- 温控车数量扫描（突发情景） ----------
    sweep = []
    for c in range(5, 19):
        res = avg_result(c, FLEET_PARAMS["blue_base"], surge=True)
        red_ot = (res["by_class"]["critical"]["overtime"]
                  + res["by_class"]["emergency"]["overtime"])
        red_n = (res["by_class"]["critical"]["orders"]
                 + res["by_class"]["emergency"]["orders"])
        sweep.append({
            "n_red": c,
            "overtime_rate_red": red_ot / red_n,
            "critical_ot_rate": res["by_class"]["critical"]["overtime_rate"],
            "emergency_ot_rate": res["by_class"]["emergency"]["overtime_rate"],
            "red_util": res["red_util"],
            "resp_p95_critical": res["by_class"]["critical"]["resp_p95"],
        })
        print(f"红车 {c:2d} 辆 | 红线超时率 {sweep[-1]['overtime_rate_red']:.2%}"
              f" | 利用率 {res['red_util']:.0%}")

    # ---------- 写 CSV ----------
    def flat(res, scenario):
        rows = []
        for key, s in res["by_class"].items():
            rows.append({
                "scenario": scenario, "drug_class": key,
                "orders": round(s["orders"], 1),
                "overtime": round(s["overtime"], 1),
                "overtime_rate": round(s["overtime_rate"], 4),
                "sla_h": {"critical": 2.0, "emergency": 4.0,
                          "seasonal": 12.0, "routine": 24.0}[key],
                "resp_mean_h": round(s["resp_mean"], 3),
                "resp_p95_h": round(s["resp_p95"], 3),
                "resp_max_h": round(s["resp_max"], 3),
                "red_util": round(res["red_util"], 3),
            })
        return rows

    rows = (flat(base, "baseline_5_7")
            + flat(surge, "surge_5_7")
            + flat(rec, "surge_16_7"))
    with open(os.path.join(OUT_DIR, "scenario_summary.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    with open(os.path.join(OUT_DIR, "fleet_sweep.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(sweep[0].keys()))
        w.writeheader()
        w.writerows([{k: round(v, 4) for k, v in r.items()} for r in sweep])

    # 逐单明细（基准 5+7 与突发 5+7，供分布图复现）
    for res, name in ((base, "records_baseline_5_7"),
                      (surge, "records_surge_5_7"),
                      (rec, "records_surge_16_7")):
        with open(os.path.join(OUT_DIR, f"{name}.csv"), "w", newline="",
                  encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(res["records"][0].keys()))
            w.writeheader()
            w.writerows(res["records"])

    print("\n=== 情景汇总（5 种子均值） ===")
    for rows_, name in ((base, "基准 5+7"), (surge, "突发4x 5+7"),
                        (rec, "突发4x 16+7")):
        c = rows_["by_class"]["critical"]
        print(f"{name}: 致命类超时率 {c['overtime_rate']:.2%}, "
              f"响应均值 {c['resp_mean']:.2f}h, P95 {c['resp_p95']:.2f}h")


if __name__ == "__main__":
    main()
