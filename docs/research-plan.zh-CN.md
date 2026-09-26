# 研究计划

[English](research-plan.md)

## 当前状态

目前已经实现：

- task / goal scoped 持久状态；
- 衰减与 outcome reappraisal；
- 可配置的 rule / memory / control / scheduler policy；
- 显式 appraisal failure policy；
- 单机多进程事务式状态更新；
- 确定性任务生命周期 scheduler；
- scheduler 指标与 Brier/ECE 工具；
- 随机场景 scheduler benchmark 和基础敏感性扫描。

目前**没有**证明：

- 默认参数已经标定；
- 优于其他 Agent 控制架构；
- 在自然真实工作负载上具有外部有效性；
- 对所有相邻研究都具有 novelty；
- 多 provider calibration 已经充分；
- 内置 scheduler 是生产级分布式调度器。

## 主研究问题

当 appraisal 更新的是**按 task / goal 隔离的持续状态**，并真正进入 scheduling、attention、memory 和 reflection 时，相比只把 affect 保存成 metadata，是否能改善长时程 Agent 控制？

## 为什么 scope 隔离本身就是研究设计的一部分

如果只有一个 agent-global affect vector，A 任务的高 arousal/salience 会无条件改变 B 任务的调度分数，导致实验混淆。

因此主要实验单位应是 task/goal scoped state trajectory，而不是一个全局“情绪值”。

未来可以额外研究“显式全局 context/mood 层是否有增益”，但它必须作为独立变量建模，不能由状态泄漏偷偷产生。

## 假设

H1：scoped integrated state 相比 metadata-only affect 能减少 deadline miss 或 user override latency，同时 wrong preemption / thrashing 成本仍可接受。

H2：unfinished tension 只有在配合 decay 和 outcome reappraisal 时，才可能改善 task resumption / reflection。

H3：快速、可校准的 appraisal 层相比生成式 appraisal 能降低 control-plane latency/cost，同时保留足够决策质量。

H4：在 provider failure 和 distribution shift 下，用户显式意图必须比 learned appraisal 更可靠。

H5：部分“收益”会对阈值/权重高度敏感，因此必须同时报告 sensitivity surface，不能只报单点最好结果。

## Baseline 矩阵

| ID | Appraisal | scoped 持久状态 | Scheduler coupling |
|---|---|---:|---|
| A | 静态优先级 | 否 | 静态/不可抢占 |
| B | Rule / Fast | 否 | 仅优先级 |
| C | 生成式 appraisal | 是 | Integrated |
| D | Fast/System-One | 是 | Integrated |
| E | 任意 appraisal | 是 | 仅 metadata |
| F | Integrated state | 是 | 仅 memory，不接 scheduler |
| G | Integrated state | 是 | 仅 scheduler，不接 memory/reflection |

D vs E 用于区分 affect-as-control 与 affect-as-representation；F/G 用于拆解 scheduler 和 memory 的贡献。

## Scheduler benchmark

内置参考 scheduler 给关键指标提供了可执行定义：

- **preemption latency**：提出 interrupt 请求到真正抢占之间的时间；
- **deadline miss**：deadline 后任务仍未完成；
- **wrong preemption**：合成场景真值标记“不需要抢占”，scheduler 却执行了抢占；
- **thrashing**：配置时间窗内出现多次抢占；
- **resume success**：被暂停任务后续恢复并最终完成；
- **switch count**：runtime 总任务切换数。

合成 ground truth 只是 fixture 定义，不能说成“真实人类偏好”。

## 状态实验

### Persistence / isolation

- A 任务高激活不得无关联地改变 B；
- A 的重复事件只在 A 内累积；
- 无 scope 事件保持瞬态。

### Decay

在不同 half-life 和事件密度下观察完整状态轨迹，报告稳定性和恢复，而不是只看最后一个值。

### Outcome reappraisal

比较 success、partial success、failure、unresolved；测 tension 释放、失败增强以及错误 carry-over。

### Memory / reflection

开关 memory coupling，测 retrieval utility 与 reflection precision/recall。

## Calibration

必须把 provider calibration 与 control-policy tuning 分开。

### Provider calibration

使用 Brier Score、ECE、reliability diagram 以及任务相关 discrimination 指标。

### Control-policy tuning

使用 sensitivity surface、hold-out 场景，最好采用嵌套 tuning/evaluation split。禁止在同一组 episode 上调阈值，然后把调出的最优结果当泛化结论。

## 参数敏感性

每个正式实验至少保存：

- 所有 config dataclass；
- random seed；
- scenario generator 版本；
- duration / deadline 分布；
- provider 版本与 question schema；
- fallback mode；
- 原始 appraisal、最终控制决策和 outcome。

主要阈值与权重必须先扫描，再解释默认配置。

## 并发实验

内置 JSON store 只承诺单机多进程安全，应至少测试：

- 两个 writer 更新不同 scope；
- 两个 writer 更新同一 scope；
- 高竞争重复更新；
- 写入过程中进程崩溃；
- 状态文件损坏检测。

分布式 store 需要单独 backend 研究。

## 文献路线

做 novelty claim 前至少覆盖：

- appraisal theory / affective computing；
- EMA / FAtiMA；
- PSI / MicroPsi 与 motivation-driven task selection；
- Global Workspace / attention competition；
- 生成式 Agent 的 persistent memory / reflection；
- affective action controller；
- fast calibrated / System-One decision layer；
- preemptive scheduler / durable workflow；
- multi-agent state 与 concurrency control。

论文需要区分已有机制、工程重组和真正经过实验支持的新贡献。

## 安全不变量

任何 affective state 都不能自动授予权限。learned appraisal 默认只能影响 soft control。
