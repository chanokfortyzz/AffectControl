# AffectControl

[English](README.md) · [证据状态](docs/evidence-status.zh-CN.md) · [失败模式](docs/failure-modes.zh-CN.md) · [外部轨迹](docs/external-trace-schema.zh-CN.md) · [适配器](docs/adapters.zh-CN.md) · [研究计划](docs/research-plan.zh-CN.md) · [Benchmark](benchmarks/README.zh-CN.md) · [统计计划](docs/statistical-analysis-plan.zh-CN.md)

**面向长时程 Agent 的实验性 appraisal-control 评估 Harness。**

> [!WARNING]
> **它不是可直接生产使用的“情感 Agent 框架”，也不是经过验证的心理学模型。** 仓库自带的所有权重、阈值、半衰期都只是未标定 reference settings；未显式传入配置时会抛出 `UncalibratedReferenceWarning`。
>
> **当前合成证据并不支持集成 affective reference policy 优于简单 baseline。** 当前 held-out 半合成 workload 中，urgency-only 的 deadline miss 约为 **0.200**，当前 affective reference policy 约为 **0.299**；一个简单监督学习 logistic interruption baseline 约为 **0.222**。
>
> **当前消融也没有证明完整 10 维状态是必要的。** 在现有 synthetic workload 上，大多数 leave-one-feature-out 结果与全维配置几乎无差别。这些是负面的诊断结果，不是外部效度证据。

AffectControl 的目标不是证明“情感一定有用”，而是让这类假设能够被统一比较、消融、校准和证伪。它提供可替换的 appraisal、候选状态特征、状态动力学、控制策略、调度、持久化、外部轨迹回放、标定、消融与结构化观测接口。

当前证据等级仍是 **E0–E1**：没有同行评审结果，没有真实长时程外部验证，也不声称 affective control 比 urgency / EDF / learned policy 更好。

### v0.2 的结构变化

- 默认 reference 参数会主动告警，不再伪装成合理默认值；
- 10 个状态量改称**候选实验特征**，可通过 `FeatureMask` 做最小集和 leave-one-out；
- 衰减/结果重评估改成可替换 `DynamicsModel`，不再被写成理论机制；
- `IntegratedRuntime` 统一管理 Harness、Scheduler 与同一时钟；
- 加入监督学习 logistic interruption baseline 和外部 JSONL trace 导入；
- 加入事务式本地 `SQLiteStateStore`；
- 加入结构化 trace 与 explicit-immediate 审计事件；
- 正式名称改为 `KeywordRuleBaseline`，明确它只是粗糙关键词 baseline；
- 加入 LangGraph 风格节点、OpenAI Agents SDK context、AutoGen 风格 run、CrewAI 风格 Flow 的实验性 helper。

## 研究问题

> 在哪些 workload 分布下（如果存在），持续的 appraisal-derived control features 能够相对 static、urgency-only、deadline-based 与 learned baseline 改善长时程调度、记忆分配或反思？

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
from affectcontrol import (
    AffectControlHarness, Event, KeywordRuleBaseline, StateEngine,
    ControlPolicy, MemoryControl, reference_policy,
)

p = reference_policy()  # emits an explicit uncalibrated-reference warning
h = AffectControlHarness(
    KeywordRuleBaseline(p.rule),
    state_engine=StateEngine(p.state),
    control=ControlPolicy(p.control),
    memory=MemoryControl(p.memory),
)
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
from affectcontrol import (
    AffectControlHarness, Event, JsonStateStore, KeywordRuleBaseline,
    StateEngine, ControlPolicy, MemoryControl, reference_policy,
)

p = reference_policy()
store = JsonStateStore("./runtime/affect-state.json")
h = AffectControlHarness(
    KeywordRuleBaseline(p.rule), store=store,
    state_engine=StateEngine(p.state),
    control=ControlPolicy(p.control), memory=MemoryControl(p.memory),
)

h.process(Event("未完成任务 A", task_id="A"))
h.process(Event("普通任务 B", task_id="B"))

state_a = h.get_state("A")
state_b = h.get_state("B")
```

`JsonStateStore` 使用锁 + 原子替换，保证**单机多进程**对同一状态文件的 read/modify/write 不互相丢更新。它不是分布式一致性数据库；跨主机多 writer 应换成事务数据库或 event store。

## 候选状态特征

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

这些变量是**候选实验特征，不是经过验证的心理学本体**。`FeatureMask` 支持最小特征集与 leave-one-out 消融；当前半合成实验几乎没有证明大多数维度对已有调度指标有独立贡献。

## Appraisal Provider

### `KeywordRuleBaseline`（`RuleProvider` 仅保留兼容别名）

这是一个刻意保持简单的词法 baseline。它处理少量显式否定，但**不具备**可靠的否定作用域解析、上下文理解或多任务语义建模；不能把它描述成 双加工心理学模型。

### `MockProvider`

用于单元测试和严格消融。

### `StructuredAppraisalProvider` 与 `JevProvider`

`StructuredAppraisalProvider` 可接生成式 LLM、分类器或其他结构化 scorer；`JevProvider` 则适配 Jev 风格的 bounded probabilistic questions。仓库统一称其为**快速/结构化 appraisal provider**，不再把实现等同于 Kahneman 的 System 1。

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
├── providers.py    # keyword / mock / structured appraisal adapter
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
