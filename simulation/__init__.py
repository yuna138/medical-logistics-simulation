# -*- coding: utf-8 -*-
"""
medical-logistics-simulation
医疗药品配送网络运力配置仿真（SimPy 复现版）

背景：某医疗物流企业为 D 市医院与药房配送四类药品
（致命 / 突发 / 季节 / 常规），最严时效 2 小时。

原项目使用 FlexSim（可视化建模）+ Gurobi（运力求解）完成；
本仓库用 SimPy 将核心「红蓝分流」调度逻辑重新实现，
以便独立验证 FlexSim 模型的结论。

模块：
- network    网络拓扑、药品分类、需求与车队参数
- dispatch   SimPy 离散事件仿真引擎（订单生成 + 红蓝分流调度）
- run_simulation 实验入口：三情景对比 + 温控车数量扫描
- make_figures   结果可视化
"""

from .network import NODES, DEPOT, DRUG_CLASSES, FLEET_PARAMS
from .dispatch import run_simulation
