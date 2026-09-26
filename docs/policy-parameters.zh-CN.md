# 策略参数说明

[English](policy-parameters.md)

AffectControl 当前所有默认数值都定义为 **uncalibrated reference priors（未标定参考先验）**。它们的作用是让工程可以运行、测试和做实验，不代表任何已经验证的心理学常数或最优调度参数。

## 参数分组

### `RuleProviderConfig`

控制确定性 baseline 中 routine / urgent / immediate 的 urgency、salience、arousal、tension、interrupt value、memory value，以及感叹号等弱信号的贡献。

数值从实现逻辑中抽离，便于实验替换和消融。

### `StateConfig`

控制：

- appraisal 融合系数 `alpha`；
- 各状态维度独立半衰期；
- 成功 / 部分成功后的 tension 释放；
- 失败后的 tension / salience 增强；
- outcome 对 certainty / competence 的更新。

统一 half-life 只用于测试便利，正式实验应该记录每个维度的完整配置。

### `MemoryPolicyConfig`

包含：

- affect 对 memory salience 的权重；
- relevance / recency 权重；
- reflection trigger 权重；
- reflection threshold。

这些输出只由 `MemoryControl` 计算，不再在 `ControlPolicy` 中重复实现第二套公式。

### `ControlPolicyConfig`

包含：

- affective drive 各维度权重；
- interrupt appraisal 与 drive 的混合权重；
- interrupt threshold；
- 软优先级提升一级 / 两级的阈值；
- planning effort 阈值；
- attention 权重。

用户显式 `immediate` 不依赖这些软阈值，仍然是硬约束。

### `SchedulerConfig`

包含：

- 仿真时间 quantum；
- priority / affect / deadline 分数权重；
- deadline horizon；
- switch penalty；
- preemption margin；
- thrashing 时间窗与最小抢占次数。

它定义的是实验参考调度器，不是生产 SLA。

## 为什么不能把默认值当成结论

同一组参数会受到以下因素显著影响：

- 任务到达分布；
- deadline 松紧；
- appraisal provider 的校准质量；
- 任务持续时间；
- 稀疏/密集事件与状态衰减的交互；
- 不同 runtime 的真实抢占成本。

因此，不能因为代码里写了一个阈值就认为这个阈值“合理”。

## 做研究结论前至少需要

1. 扫描主要权重和阈值；
2. 报告结果对参数的敏感性；
3. 使用 hold-out 场景分布；
4. 把 provider calibration 与 control-policy tuning 分开；
5. 对比静态、无持久状态等 baseline；
6. 同时报告错误抢占和 task thrashing 成本，而不是只报告 deadline 改善。

当前可运行：

```bash
PYTHONPATH=src python benchmarks/sensitivity.py
```

它只是最小参数网格，不等同于完整标定流程。
