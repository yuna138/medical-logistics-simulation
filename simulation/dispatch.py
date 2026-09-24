# -*- coding: utf-8 -*-
#
# 作者 / Author : 龙雨灿 Long Yucan (GitHub: yuna138)
# 仓库 / Repo   : https://github.com/yuna138/medical-logistics-simulation
# 版权 / License: MIT (c) 2026 Long Yucan. 保留署名权，转载请注明出处。
#
"""
红蓝分流调度仿真引擎（SimPy 离散事件仿真）。

调度逻辑（与 FlexSim 模型一致）：
1. 订单按药品类别到达，服从非齐次泊松过程（白天高、傍晚高峰）；
2. 「红蓝分流」：温控车只跑致命/突发，普冷车只跑季节/常规，
   两类车队互不支援，保证高时效订单资源独占；
3. 同一车队内按订单时效优先级排队（致命 > 突发 > 季节 > 常规）；
4. 响应时间 = 排队等待 + 在途行驶；超过 SLA 记为一次超时。

实现方式：预生成全部订单到达时刻 -> SimPy 逐事件调度。
"""

import collections
import random

import simpy

try:
    from .network import (
        NODES, DRUG_CLASSES, HOUR_PROFILE, HANDLING_H,
        SIM_DAYS, SURGE_FACTOR, travel_hours,
    )
except ImportError:  # 直接以脚本方式运行时
    from network import (
        NODES, DRUG_CLASSES, HOUR_PROFILE, HANDLING_H,
        SIM_DAYS, SURGE_FACTOR, travel_hours,
    )

# 订单优先级：数字越小越优先
PRIORITY = {"critical": 0, "emergency": 1, "seasonal": 2, "routine": 3}


# 突发需求的「成簇」概率与簇内订单数（事故/疫情式爆发，非均匀放大）
BURST_PROB = 0.35      # 每张突发订单引发簇的概率
BURST_SIZE = (2, 5)    # 簇内追加订单数
BURST_WINDOW_H = (0.1, 0.5)   # 簇内到达时间窗（小时）


def generate_orders(rng, days, surge=False):
    """预生成全部订单：按到达时刻排序的事件列表 [(t_hour, class_key), ...]

    基础流：非齐次泊松过程（按小时切片，段内到达率 = 日均单量/24 * 时段强度）。
    突发情景（surge）：在基础流之上「叠加」需求簇——每张突发类订单以
    BURST_PROB 的概率在短时间窗内追加 BURST_SIZE 张订单。
    簇不推动基础流的泊松时钟（否则会挤掉基础订单，总需求量不升反降）。
    """
    orders = []
    end = days * 24.0
    for key, cfg in DRUG_CLASSES.items():
        is_surge_cls = key == "emergency" and surge
        lam = cfg["lambda_base"] * (SURGE_FACTOR if is_surge_cls else 1.0)

        # ---- 基础泊松流（只由 dt 推进时钟）----
        base_times = []
        t = 0.0
        while t < end:
            h_abs = int(t)                    # 绝对小时（0..days*24-1）
            hour = h_abs % 24                 # 时段曲线索引
            t_seg_end = min(h_abs + 1.0, end) # 段末：绝对小时边界
            lam_h = lam / 24.0 * HOUR_PROFILE[hour]
            if lam_h <= 0 or t >= t_seg_end:
                t = t_seg_end
                continue
            dt = rng.expovariate(lam_h)
            if dt > t_seg_end - t:      # 本时段不再来单
                t = t_seg_end
                continue
            t += dt
            base_times.append(t)

        # ---- 突发情景：在基础流上叠加需求簇 ----
        if is_surge_cls:
            for t0 in base_times:
                if rng.random() < BURST_PROB:
                    cur = t0
                    for _ in range(rng.randint(*BURST_SIZE)):
                        cur += rng.uniform(*BURST_WINDOW_H)
                        if cur < end:
                            orders.append((cur, key))

        orders.extend((t0, key) for t0 in base_times)
    orders.sort(key=lambda x: x[0])
    return orders


def run_simulation(n_red, n_blue, surge=False, seed=42, days=SIM_DAYS):
    """运行一次 days 天仿真，返回汇总结果（含逐单明细）。"""
    rng = random.Random(seed)
    orders = generate_orders(rng, days, surge)

    env = simpy.Environment()
    red = simpy.PriorityResource(env, capacity=n_red)
    blue = simpy.PriorityResource(env, capacity=n_blue)
    red_busy = 0.0
    blue_busy = 0.0
    records = []
    node_w = [1.0 if i < 5 else 0.6 for i in range(len(NODES))]

    def serve(order_t, key):
        nonlocal red_busy, blue_busy
        # 先推进到订单到达时刻，再参与排队（保证队列公平与时序正确）
        yield env.timeout(order_t - env.now)
        cfg = DRUG_CLASSES[key]
        is_red = cfg["fleet"] == "red"
        fleet_res = red if is_red else blue
        node = rng.choices(NODES, weights=node_w, k=1)[0]
        travel = travel_hours(node)
        handling = rng.uniform(*HANDLING_H)
        req = fleet_res.request(PRIORITY[key])
        yield req
        wait = env.now - order_t
        t_service_start = env.now
        service = travel + handling
        yield env.timeout(service)
        # 利用率只统计仿真期内的占用（超出截止时刻的部分不计）
        horizon = days * 24.0
        busy_seg = min(env.now, horizon) - t_service_start
        if is_red:
            red_busy += max(busy_seg, 0.0)
        else:
            blue_busy += max(busy_seg, 0.0)
        fleet_res.release(req)
        response = wait + travel
        records.append({
            "t": order_t, "class": key, "wait_h": wait,
            "travel_h": travel, "response_h": response,
            "sla_h": cfg["sla_h"], "overtime": int(response > cfg["sla_h"]),
        })

    for t, key in orders:
        env.process(serve(t, key))
    env.run()

    # ---------- 统计 ----------
    ot = collections.Counter(r["class"] for r in records if r["overtime"])
    cnt = collections.Counter(r["class"] for r in records)
    by_class = {}
    for key, cfg in DRUG_CLASSES.items():
        rs = [r for r in records if r["class"] == key]
        if not rs:
            continue
        resp = sorted(r["response_h"] for r in rs)
        by_class[key] = {
            "orders": cnt[key],
            "overtime": ot[key],
            "overtime_rate": ot[key] / cnt[key],
            "sla_h": cfg["sla_h"],
            "resp_mean": sum(resp) / len(resp),
            "resp_p95": resp[max(int(len(resp) * 0.95) - 1, 0)],
            "resp_max": resp[-1],
        }
    return {
        "n_red": n_red, "n_blue": n_blue, "surge": surge,
        "orders": len(records), "by_class": by_class,
        "red_util": red_busy / (n_red * days * 24),
        "blue_util": blue_busy / (n_blue * days * 24),
        "records": records,
    }
