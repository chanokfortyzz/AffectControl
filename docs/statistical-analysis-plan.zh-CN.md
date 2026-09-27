# 统计分析计划

[English](statistical-analysis-plan.md)

这是一份面向未来 confirmatory study 的前置计划，不会把当前 E0–E1 证据自动升级。

## 实验单位

Scheduler 对比以 workload/session 作为主要实验单位，不能把每个 scheduler tick、每次 state update 都当成独立样本。

同一项目、同一天或同一 trajectory 的重复任务应保留 cluster 标识，并使用 cluster-aware resampling 或层级分析。

## Appraisal 主指标

针对冻结的人类 interruption 标签，预先指定 Brier score 作为主要概率指标；ECE、AUROC、固定阈值混淆指标、延迟和成本作为次要指标。

阈值必须在 train/validation 数据上选择，并在最终 test 前冻结。

## Scheduler 主指标

正式实验前只预先指定一个主要 operational endpoint，例如 deadline miss rate 或 binary task completion。Preemption latency、wrong preemption、resume success、starvation、thrashing、token cost 和 wall time 作为次要结果。

条件允许时，所有策略应在完全相同的 matched traces 上运行。
## 推断方法

对 matched 的连续/比率指标，以 session 为重采样单位报告 paired effect difference 与置信区间。对于成对二元结果，应使用 paired binary 分析（例如基于 discordant pairs 的 McNemar 类方法），而不是把两组当独立比例。

不能只给 p-value，必须同时报告 effect size 与 interval。

## 多重比较

预先指定一个 primary baseline；如果同时比较多个 provider/strategy，则使用预先声明的 Holm 等校正。不能看完结果后再挑最有利的比较。

## 防止数据泄漏

当相邻 event 共享上下文时，应按 task lineage/session/project 划分，而不是随机拆 event row。Provider calibration、policy fitting 与 threshold selection 都不能看到最终 test labels。

## Power planning

不能用当前很小的 operational pilot 直接估正式实验 power。应先定义具有实际意义的最小效应，再只使用 pilot 估计方差/discordance，并按预定的 paired design 模拟所需 session 数。

在收集 confirmatory test set 前记录假设、流失率、聚类结构与 power 计算流程。

## 负结果

即使 affective/controller 假设输给简单 baseline，也必须报告预先指定的主指标。根据 test-set 失败重新调参，属于下一轮新实验，不能回写成原实验的“修正版结果”。
