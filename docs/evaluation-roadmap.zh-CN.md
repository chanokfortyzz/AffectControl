# 评估路线图

[English](evaluation-roadmap.md)

## Phase 1 — 标定

- 构建带标签的 interruption / priority 数据集，并严格划分 train/validation/test。
- 对 appraisal 输出计算 Brier、ECE、reliability diagram，以及适用时的 AUROC/PR。
- 控制策略的权重和阈值只能在 train 上拟合；在 held-out 集上报告结果与敏感性曲面。
- 禁止针对最终 benchmark test set 调参。

## Phase 2 — 正式 baseline

至少比较：
1. 静态优先级调度器；
2. 规则 + task-scoped persistent state；
3. Jev/System-One appraisal + scoped state；
4. 生成式 LLM appraisal + scoped state；
5. 显式 VAD 一阶/二阶动力学；
6. affect 仅作为 metadata、完全不进入控制回路。

在允许访问 open-weight hidden states 的条件下，representation-level steering 应作为独立机制家族加入，而不是假装它与外部控制平面是同一种方法。

## Phase 3 — 半真实 long-horizon workload

优先在 OSWorld 2.0/2.1 或类似可自托管环境上叠加 interruption overlay：动态插入需求变更、deadline、过时/矛盾状态、恢复任务和并发任务。

主要终点：
- binary/partial completion；
- deadline miss；
- preemption latency；
- user override compliance；
- wrong preemption；
- resume success；
- starvation / thrashing；
- token、wall time、货币成本。

## Phase 4 — 外部效度

在真实或操作上高度接近真实的多小时工作负载中，用冻结协议和预先定义指标运行，并做隐私脱敏。报告 paired confidence interval / effect size，而不是单次案例。

## Phase 5 — 论文闸门

只有 Phase 1–3 产生可复现实证结果后，才进入论文撰写。若要主张机制或理论贡献，证据要求必须显著高于工程框架论文。
