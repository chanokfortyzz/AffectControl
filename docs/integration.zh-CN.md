# 接入指南

[English](integration.md)

## 1. 需要持续状态的单位必须有 scope

任何需要积累状态的任务/目标都应使用稳定的 `task_id` 或 `goal_id`。

```python
from affectcontrol import Event

event = Event(
    text="今天审查方案",
    task_id="review-42",
    explicit_priority="P2",
)
```

无 scope 事件默认瞬态，不会污染其他任务。

## 2. 权限系统必须在外部

`ControlBias` 只能作为控制建议。权限、凭据、部署、删除、金融动作和人工确认门都必须由宿主 runtime 管理。

## 3. 接模型前先确定失败语义

建议先用 `RuleProvider` 建立确定性 baseline。接 System-One/校准模型时必须明确模型失败怎么办：

```python
from affectcontrol import JevProvider
provider = JevProvider(call=backend, missing_policy="raise")
```

不要让 fail-calm / fail-urgent 成为隐式行为。

## 4. 需要连续性时持久化

```python
from affectcontrol import AffectControlHarness, JsonStateStore
store = JsonStateStore("runtime/state.json")
h = AffectControlHarness(provider, store=store)
```

内置 store 只保证单机多进程事务。分布式系统应换成支持事务的数据库或 event store。

## 5. 明确映射输出

| 输出 | 常见宿主用法 |
|---|---|
| `effective_priority` | 队列排序 |
| `should_interrupt` | 当前工作允许抢占时请求抢占 |
| `planning_effort` | 推理/规划预算 |
| `attention_weight` | attention/global workspace 权重 |
| `memory_salience` | retrieval/consolidation 权重 |
| `reflection_trigger` | 请求反思/重规划 |

## 6. outcome 必须按 scope 回写

```python
h.outcome("review-42", success=True)
h.outcome("review-43", success=False)
```

结果只改变对应任务/目标的状态。

## 7. 是否使用内置 scheduler 取决于研究需求

`AffectiveScheduler` 是受控实验 runtime；已有生产 scheduler 可以只通过 adapter 消费 `ControlBias`。

## 8. 可审计日志至少要记录

- task/goal scope；
- 原始 provider 输出；
- provider failure policy；
- 状态转移前后值；
- 完整 config；
- control 输出；
- scheduler 决策；
- outcome；
- latency / cost；
- 人工/用户 override。

缺少这些信息就无法复现 calibration 与失败分析。
