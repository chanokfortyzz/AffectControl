# 失败模式

[English](failure-modes.md)

AffectControl 是实验性控制/评估 Harness。下面这些失败属于应主动研究的问题，而不是应该隐藏的边角情况。

## 模型 / appraisal 失败

- 传输失败、返回结构错误或字段缺失；
- 分布漂移下概率失去标定；
- 关键词 baseline 被否定作用域、讽刺、多语言或多任务上下文误导；
- appraisal 输出高度相关，导致名义上不同的状态维度实际上冗余。

`JevProvider` / `StructuredAppraisalProvider` 会区分 transport、response-shape 与 missing-field 错误；fallback 必须显式选择。

## 控制失败

- 状态过强持续或 interrupt 阈值过高导致错过 deadline；
- 阈值过激导致无谓抢占和 thrashing；
- 低 salience 任务长期饥饿；
- 连续失败后出现滞回或任务固着；
- 未标定权重造成虚假的“精确感”；
- 多个相关特征增加复杂度，却没有独立贡献。

## 状态动力学失败

仓库中的指数衰减和简单加/乘法 outcome update 只是 reference baseline。遇到突发事件密度、任务依赖、延迟反馈、非平稳目标或不同恢复动力学时，它们都可能失效。

## 跨任务失败

按 task 隔离可以防止意外状态污染，但不能自动解决全局资源竞争。`GlobalControlContext` 与 affect state 分离，目的是让跨任务竞争可以被显式建模和单独消融。

## 存储 / runtime 失败

- `JsonStateStore` 只适用于单机，并且会重写整个状态文档；
- `SQLiteStateStore` 在单机上事务化，但不是分布式一致性系统；
- 外部副作用与控制状态更新之间崩溃，需要宿主自己保证幂等与恢复；
- 可选框架 helper 不承担工具授权或不可逆动作安全。

## immediate 硬覆盖风险

`explicit_user_immediate=True` 是控制不变量，不是授权。它会强制 P0/interrupt bias，并写结构化审计事件；权限、安全门、审批以及不可抢占关键区仍必须由宿主系统执行。

## 研究失败判据

如果简单 baseline 在冻结的 held-out workload 上持平或更好、收益在小幅参数扰动后消失、消融显示维度冗余、或结果无法在外部轨迹复现，就应把相应假设视为未获支持。
