# 架构说明

[English](architecture.md)

AffectControl 将 appraisal、按 scope 隔离的状态转移、记忆/反思策略、控制策略、调度和持久化拆开，目的是让每一层都可以单独消融、替换和定位故障。

## 运行图

```text
Event(task_id / goal_id)
        │
        ▼
AppraisalProvider
        │
        ▼
Appraisal 向量
        │
        ▼
StateEngine ───────────────┐
        │                  │
        ▼                  │
Scoped AffectiveState      │
        │                  │
        ├──► MemoryControl │
        │      │           │
        │      ├─ memory salience
        │      └─ reflection trigger
        │
        ▼
ControlPolicy
        │
        ▼
ControlBias
        │
        ├──► 外部 runtime / adapter
        └──► 实验 AffectiveScheduler
                    │
                    ▼
          QUEUED → RUNNING ⇄ PAUSED → DONE/FAILED
                    │
                    ▼
                  outcome
                    │
                    └────────► StateEngine.reappraise_outcome
```

## Scope 模型

持久状态必须按 `task_id` 或 `goal_id` 隔离。

这是设计级约束，不是优化项。单一全局状态向量会造成实验混淆：A 任务的高 salience 会直接抬高 B 任务的 drive，即使二者毫无关系。

scope 解析顺序：

```text
Event.task_id
→ metadata.task_id
→ Event.goal_id
→ metadata.goal_id
→ 无持久 scope
```

没有 scope 时，使用新的瞬态状态，不复用全局状态。

## 组件职责

### `AppraisalProvider`

只负责产生 `Appraisal`，不调度任务、不授权动作。

### `StateEngine`

负责衰减、证据融合和 outcome reappraisal。所有数值由 `StateConfig` 提供。

### `MemoryControl`

唯一负责 memory salience 与 reflection trigger，结果传给 `ControlPolicy`，不允许两套公式并存。

### `ControlPolicy`

负责优先级、抢占、注意力和规划建议，不再自行计算记忆策略。

### `AffectiveScheduler`

提供确定性的实验任务生命周期，使 preemption latency、deadline miss、thrashing、resume 等指标有真实对象可测。

支持 queued / running / paused / done / failed / cancelled、deadline pressure、抢占、恢复和指标采集。

它不是生产级分布式调度器。

### `JsonStateStore`

在 read/modify/write 外层加锁，并使用原子替换，避免单机多进程同 key 更新丢失。

该锁只解决单主机同步；分布式 writer 需要事务数据库或 event store。

## Appraisal 失败语义

`JevProvider` 的失败行为必须显式选择：

- `raise`：默认，直接暴露失败；
- `neutral`：缺失字段使用 0.5 中性先验；
- `conservative`：控制相关缺失值向高风险/高关注方向偏置。

格式错误不会再静默变成“平静 0 分”。

## 硬控制与软控制

硬约束不属于 learned control。用户显式 immediate 可以由集成方定义为硬不变量；授权、删除、凭据、金融、部署等门控必须留在外部。

软控制包括队列排序、抢占建议、注意力分配、规划预算、记忆显著性和反思触发。

## 参数化

主要数值全部集中在 config dataclass 中。默认值是 reference priors，不是已验证常数。见 [policy-parameters.zh-CN.md](policy-parameters.zh-CN.md)。
