# AffectControl

[English](README.md) · [架构](docs/architecture.zh-CN.md) · [策略参数](docs/policy-parameters.zh-CN.md) · [接入](docs/integration.zh-CN.md) · [研究计划](docs/research-plan.zh-CN.md) · [Benchmark](benchmarks/README.zh-CN.md)

AffectControl 是一个与具体 Agent 框架无关的研究 Harness，用于研究：**当情感、动机、兴趣、紧迫度不再只是 metadata，而是真正进入控制回路时，会发生什么。**

它不是完整 Agent 框架，而是提供以下可独立替换的控制组件：

- 按 task / goal 隔离的持续状态；
- appraisal provider 接口；
- 状态衰减与结果重评估；
- 优先级、抢占、注意力、规划、记忆与反思的软控制偏置；
- 用于可控实验的任务生命周期调度器；
- 单机多进程安全的 JSON 状态存储；
- benchmark、敏感性与校准指标工具。

> 当前状态：研究原型。不声称类人情感、意识或心理学等价性。
> **证据状态：** 当前只有工程框架与合成诊断证据；尚无控制策略标定、真实长时程验证、与强 baseline 的正式比较或同行评审结果。详见 [证据状态](docs/evidence-status.zh-CN.md)、[相关工作](docs/related-work.zh-CN.md) 与 [评估路线图](docs/evaluation-roadmap.zh-CN.md)。


## 研究问题

> 当快速 appraisal 更新的是“按任务/目标隔离的持续状态”，并且这些状态真正接入调度、记忆和注意力时，能否改善长时程 Agent 控制，相比之下又是否优于只把 affect 存成 metadata？

```text
事件（task / goal scope）
        │
        ▼
   Appraisal Provider
        │
        ▼
按 scope 持久化的状态
 urgency / salience / arousal / interest / tension / goal activation
        │
        ├──────────────► 记忆 + 反思策略
        │
        ▼
      控制策略
 优先级 / 抢占 / 注意力 / 规划
        │
        ▼
 任务生命周期调度器
 QUEUED → RUNNING ⇄ PAUSED → DONE/FAILED
        │
        ▼
       Outcome
        │
        └──────────────► 结果重评估 + 衰减
```

## 关键设计边界

1. **状态按任务或目标隔离。** A 任务的 salience/tension 不应直接灌进 B 任务。
2. **无 scope 的事件默认是瞬态。** 没有 `task_id` / `goal_id` 时，不复用任何全局情感向量。
3. **用户显式 immediate 是硬约束。** 模型 appraisal 无权把它降级。
4. **Affect 不等于权限。** 授权、密钥、部署、删除、不可逆动作和确认门都必须位于本库之外。
5. **模型失败策略必须显式。** `JevProvider` 默认抛出 `AppraisalError`；要 neutral / conservative fallback 必须主动指定。
6. **默认数字不是“科学常数”。** 仓库里的权重、阈值和半衰期全部标记为未标定 reference priors，实验前必须扫描、拟合或消融。

## 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

```python
from affectcontrol import AffectControlHarness, Event, RuleProvider

h = AffectControlHarness(RuleProvider())
r = h.process(
    Event("今天审查这个方案", task_id="review-42"),
    base_priority="P2",
)

print(r["scope_key"])
print(r["state"].asdict())
print(r["control"].asdict())
```

## 用户显式 immediate

```python
r = h.process(
    Event(
        "现在立刻审查",
        task_id="review-43",
        explicit_user_immediate=True,
    ),
    base_priority="P3",
)

assert r["control"].effective_priority == "P0"
assert r["control"].should_interrupt is True
```

这一条是控制不变量，不依赖任何模型概率或经验阈值。

## 按 task / goal 隔离的持久状态

```python
from affectcontrol import AffectControlHarness, Event, JsonStateStore, RuleProvider

store = JsonStateStore("./runtime/affect-state.json")
h = AffectControlHarness(RuleProvider(), store=store)

h.process(Event("未完成任务 A", task_id="A"))
h.process(Event("普通任务 B", task_id="B"))

state_a = h.get_state("A")
state_b = h.get_state("B")
```

`JsonStateStore` 使用锁 + 原子替换，保证**单机多进程**对同一状态文件的 read/modify/write 不互相丢更新。它不是分布式一致性数据库；跨主机多 writer 应换成事务数据库或 event store。

## 状态维度

| 变量 | 控制含义 |
|---|---|
| `urgency` | 时间紧迫度 |
| `salience` | 注意力吸引程度 |
| `arousal` | 激活/强度 |
| `interest` | 持续兴趣/项目相关性 |
| `tension` | 未完成目标张力 |
| `goal_activation` | 当前目标激活度 |
| `interrupt_value` | 抢占低优先级可抢占工作的效用 |
| `memory_value` | 保留/召回/整理的价值 |
| `certainty` | appraisal 解释的确定性代理 |
| `competence` | 当前 Agent 推进任务的能力估计 |

状态演化由 `StateConfig` 控制，会随时间衰减，也可以依据成功、失败或部分成功重新评估。

## Appraisal Provider

### `RuleProvider`

透明的确定性 baseline。已经处理 `不急`、`不用马上`、`no rush`、`not urgent` 等否定表达，避免最明显的子串误判。

规则数值全部集中在 `RuleProviderConfig`，只作为 reference priors，不声称经过心理学或行为数据标定。

### `MockProvider`

用于单元测试和严格消融。

### `JevProvider`

用于接快速/可校准的 System-One 类 appraisal 后端。传输、鉴权、密钥都不在库内。

默认策略是严格失败：

```python
JevProvider(call=my_backend, missing_policy="raise")
```

也可以明确选择：

```python
JevProvider(call=my_backend, missing_policy="neutral")
JevProvider(call=my_backend, missing_policy="conservative")
```

缺失字段不会再静默变成 `0.0`。

## 记忆与反思

`MemoryControl` 现在是 memory salience 和 reflection trigger 的唯一计算源。`ControlPolicy` 只消费它的输出，不再自己维护第二套记忆公式。

这样可以独立做“有/无 memory coupling”的消融实验。

## 真实任务生命周期调度器

项目现在包含一个确定性的实验调度器：

```python
from affectcontrol import AffectiveScheduler, TaskSpec

scheduler = AffectiveScheduler()
scheduler.add_task(TaskSpec(
    task_id="background",
    text="background work",
    duration_s=30,
    base_priority="P2",
))
```

生命周期：

```text
QUEUED → RUNNING ⇄ PAUSED → DONE
                    └──────→ FAILED / CANCELLED
```

目前可测：

- 抢占延迟；
- deadline miss rate；
- 基于场景真值标签的错误抢占率；
- 高频抢占产生的 task thrashing；
- 暂停/恢复次数与恢复完成率；
- task switch 数量。

它是**实验参考 runtime**，不是生产级分布式调度器。

## 参数全部显式配置

不再把控制权重散落在公式里。当前参数分为：

- `RuleProviderConfig`
- `StateConfig`
- `MemoryPolicyConfig`
- `ControlPolicyConfig`
- `SchedulerConfig`

详细说明见 [docs/policy-parameters.zh-CN.md](docs/policy-parameters.zh-CN.md)。

这些默认值统一定义为 **uncalibrated reference priors（未标定参考先验）**。做研究结论前必须跑敏感性分析、拟合、交叉验证或消融。

## Benchmark

```bash
PYTHONPATH=src python benchmarks/scheduler_benchmark.py --episodes 200 --seed 17
PYTHONPATH=src python benchmarks/sensitivity.py
```

现在的 scheduler benchmark 会随机生成任务到达时序并完整跑任务生命周期，不再是三个手写 case 打印 dict。

它比较：

- 静态、不可抢占 baseline；
- affective integrated control。

输出包括 deadline miss、preemption latency、wrong preemption、resume success 和 thrashing。

**当前 benchmark 只是工程诊断，不是论文证据。** 详细说明见 [benchmarks/README.zh-CN.md](benchmarks/README.zh-CN.md)。

## 校准指标

```python
from affectcontrol import brier_score, expected_calibration_error
```

Brier/ECE 用于 appraisal 概率输出的校准评估，不代表 control policy 自己已经被标定。控制权重和阈值仍需单独做 sensitivity / fitting。

## 当前测试覆盖

测试包含：

- immediate 硬覆盖；
- task scope 隔离；
- 无 scope 事件瞬态化；
- memory/reflection 单一来源；
- “不急”等否定表达；
- Jev strict / neutral failure policy；
- 衰减与 outcome reappraisal；
- 多进程同 key 事务更新不丢失；
- scheduler 抢占、deadline、恢复、错误抢占指标；
- Brier / ECE。

具体数量以 `pytest -q` 的当前输出为准。

## 工程结构

```text
src/affectcontrol/
├── config.py       # 所有参考策略参数
├── types.py        # Event / Appraisal / scoped state / task lifecycle
├── providers.py    # Rule / Mock / System-One 类 appraisal adapter
├── state.py        # 衰减 + outcome reappraisal
├── memory.py       # memory salience + reflection
├── control.py      # priority / interrupt / attention / planning
├── scheduler.py    # 实验任务生命周期调度器
├── storage.py      # 单机多进程安全 JSON 状态存储
├── metrics.py      # Brier / ECE
├── harness.py      # scoped control orchestration
└── adapters/       # 通用 adapter
```

## 研究状态

仓库会严格区分：

- 已经实现的工程机制；
- 尚未标定的 reference policy；
- 仍需要实验验证的研究假设。

“代码里存在一个机制”不等于“已经证明这个机制更好”。

## 安全边界

见 [SECURITY.zh-CN.md](SECURITY.zh-CN.md)。任何高 urgency / high arousal 都不能自动获得高风险或不可逆操作权限。

## License

MIT。
