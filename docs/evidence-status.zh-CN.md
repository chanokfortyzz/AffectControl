# 证据状态

[English](evidence-status.md)

## 当前可主张的级别

AffectControl 目前是一个**工程与实验框架**，不是已经验证的情感控制理论。

当前已经具备：
- 按 task/goal 隔离的持续 affective state；
- 可配置控制策略与任务生命周期调度器；
- 规则、Mock、System-One/Jev 类 appraisal adapter；
- 单机多进程安全的 JSON 持久化；
- interruption / deadline / resume 的合成诊断；
- policy threshold 的敏感性分析工具。

当前尚未具备：
- 控制策略参数标定；
- 有统计效力的实证结果；
- 与强 affective / motivational baseline 的正式对比；
- 在真实或半真实 long-horizon workload 上的验证；
- 外部控制平面相对 representation-level / learned mechanism 的优势证据；
- 同行评审论文。

## 证据阶梯

| 级别 | 含义 | 当前状态 |
|---|---|---|
| E0 | API/单元正确性 | 已完成 |
| E1 | 合成调度诊断 | 部分完成 |
| E2 | 标定后的合成/半合成实验 | 未完成 |
| E3 | 半真实长时程 benchmark 验证 | 未完成 |
| E4 | 真实工作负载外部效度 | 未完成 |
| E5 | 同行评审的机制/理论主张 | 未完成 |

仓库中的任何表述都不应该超过当前证据等级。
