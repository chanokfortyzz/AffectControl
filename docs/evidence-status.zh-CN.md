# 证据状态

[English](evidence-status.md)

## 当前可主张的级别

AffectControl 目前是一个**工程与实验框架**，不是已经验证的情感控制理论。

当前已经具备：
- 按 task/goal 隔离的持续 affective state；
- 可配置控制策略与任务生命周期调度器；
- 规则、Mock、结构化/Jev 类 appraisal adapter；
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

## 2026-09-27 更强的合成 baseline

E1 现在加入了工作流形态的事件轨迹，以及 static priority、EDF、urgency-only、integrated affect 四种 scheduler baseline。首轮 200 episode 诊断在 deadline miss 上**并不支持** affective policy：urgency-only 更好。这提高了可证伪性，但仍不足以升级为 E2，因为策略没有标定，轨迹分布也仍由本项目自行设计。

## 当前负面诊断结果

当前半合成 workload 应被当作证伪工具，而不是展示项目优势的样例。在 held-out 200-seed 诊断中：

| 策略 | Deadline miss | Wrong preemption | Thrashing | Override compliance |
|---|---:|---:|---:|---:|
| static | 0.400 | 0.000 | 0.000 | 0.000 |
| urgency-only | **0.200** | 0.000 | 0.000 | 1.000 |
| learned logistic interruption | 0.222 | 0.000 | 0.000 | 1.000 |
| EDF | 0.222 | 0.613 | 0.675 | 1.000 |
| affective reference policy | **0.299** | 0.000 | 0.000 | 1.000 |

因此，当前 affective reference policy 在 deadline miss 上**没有**超过简单 urgency baseline。

特征消融也给出了负面结果：在当前 synthetic distribution 下，最小候选特征集与完整 10 维配置几乎相同，大多数 leave-one-feature-out 配置也没有明显变化。当前没有证据证明 10 个候选状态变量都必要。

这些仍然只是 E1，因为 workload 与标签来自本项目自身，reference policy 也没有标定。
