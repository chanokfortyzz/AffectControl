# AffectControl

[中文](README.zh-CN.md) · [Evidence](docs/evidence-status.md) · [Failure Modes](docs/failure-modes.md) · [External Traces](docs/external-trace-schema.md) · [Adapters](docs/adapters.md) · [Research Plan](docs/research-plan.md) · [Benchmarks](benchmarks/README.md)

**Experimental appraisal-control evaluation harness for long-horizon agents.**

> [!WARNING]
> **This is not a production emotion-agent framework and not a validated psychological model.** Shipped numerical parameters are uncalibrated reference settings. Instantiating reference components without explicit configs emits `UncalibratedReferenceWarning`.
>
> **Current synthetic evidence does not support superiority of the integrated affective reference policy.** On the current held-out semi-synthetic workload, urgency-only has lower deadline miss rate (~0.200) than the affective reference policy (~0.299). A simple trained logistic interruption baseline is ~0.222.
>
> **Current ablation evidence also does not justify the full 10-dimensional candidate state.** Most leave-one-feature-out runs are indistinguishable from the all-feature configuration on the present synthetic workload. These are negative diagnostic results, not external-validity evidence.

AffectControl exists to make such hypotheses easy to test and easy to falsify. It supplies replaceable interfaces for appraisal, candidate state features, state dynamics, control policies, scheduling, persistence, external trace replay, calibration, ablation and structured observability.

Current evidence level remains **E0–E1**. There is no peer-reviewed result, no realistic long-horizon external validation, and no claim that affective control is better than simpler scheduling baselines.

### What v0.2 changes

- reference parameters now emit runtime warnings instead of looking like validated defaults;
- the 10 state values are explicitly **candidate features**, selectable through `FeatureMask`;
- decay/outcome dynamics are replaceable (`DynamicsModel`), not treated as a theory;
- `IntegratedRuntime` owns harness + scheduler + a shared clock;
- a supervised logistic interruption baseline and external JSONL trace ingestion are included;
- `SQLiteStateStore` adds a transactional local backend for larger experiments;
- structured trace sinks and explicit-immediate audit events are available;
- `KeywordRuleBaseline` replaces the misleading idea that lexical rules are a dual-process psychological model;
- experimental integration helpers exist for LangGraph-style graph nodes, OpenAI Agents SDK context, AutoGen-style runs and CrewAI-style flows.

## Research question

> Under what workload distributions, if any, do persistent appraisal-derived control features improve long-horizon agent scheduling, memory allocation or reflection relative to simpler static, urgency-only, deadline-based and learned baselines?

```text
Event(task/goal scope)
        │
        ▼
   Appraisal Provider
        │
        ▼
Persistent scoped state
 urgency / salience / arousal / interest / tension / goal activation
        │
        ├──────────────► Memory + reflection policy
        │
        ▼
    Control policy
 priority / interrupt / attention / planning
        │
        ▼
 Lifecycle scheduler
 QUEUED → RUNNING ⇄ PAUSED → DONE/FAILED
        │
        ▼
      Outcome
        │
        └──────────────► reappraisal + decay
```

## Important design boundaries

1. **State is scoped to a task or goal.** Task A cannot silently contaminate Task B's state vector.
2. **Unscoped events are transient.** If no `task_id` or `goal_id` is provided, no persistent global affect vector is reused.
3. **Explicit immediate intent is a hard invariant.** Appraisal cannot demote it.
4. **Affect is not authorization.** Permission, credentials, deployment, destructive actions and confirmation remain outside this library.
5. **Model failure policy is explicit.** `JevProvider` defaults to raising `AppraisalError`; neutral or conservative fallback must be selected deliberately.
6. **Default numerical parameters are not validated constants.** They are uncalibrated reference priors and must be swept/fitted before scientific claims.

## Quick start

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
result = h.process(
    Event("review this today", task_id="review-42"),
    base_priority="P2",
)

print(result["scope_key"])
print(result["state"].asdict())
print(result["control"].asdict())
```

## Explicit user override

```python
result = h.process(
    Event(
        "review this now",
        task_id="review-43",
        explicit_user_immediate=True,
    ),
    base_priority="P3",
)

assert result["control"].effective_priority == "P0"
assert result["control"].should_interrupt is True
```

This is a control invariant, not a learned threshold.

## Task/goal-scoped persistent state

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

h.process(Event("unfinished task A", task_id="A"))
h.process(Event("routine task B", task_id="B"))

state_a = h.get_state("A")
state_b = h.get_state("B")
```

`JsonStateStore` serializes local multi-process read/modify/write transitions with a lock plus atomic replace. It is **not** a distributed consensus store. Multi-host deployments should provide a transactional database/event-store adapter.

## Candidate state features

| Dimension | Control interpretation |
|---|---|
| `urgency` | time sensitivity |
| `salience` | attention attraction |
| `arousal` | activation/intensity |
| `interest` | sustained relevance |
| `tension` | unresolved-goal pressure |
| `goal_activation` | active-goal relevance |
| `interrupt_value` | utility of interrupting preemptible work |
| `memory_value` | retention/retrieval/consolidation value |
| `certainty` | appraisal confidence proxy |
| `competence` | estimated ability to progress |

These fields are **candidate experimental features, not a validated ontology**. `FeatureMask` supports minimal and leave-one-out ablations. The current semi-synthetic ablation provides little evidence that most fields independently affect the reported scheduler metrics.

## Appraisal providers

### `KeywordRuleBaseline` (`RuleProvider` compatibility alias)

A deliberately crude lexical baseline. It handles a few explicit negations but does **not** provide robust scope parsing, contextual semantics or multi-task interference modeling. It exists as a weak deterministic comparator, not as a fast cognitive model.

### `MockProvider`

Used for unit tests and controlled ablations.

### `StructuredAppraisalProvider` and `JevProvider`

`StructuredAppraisalProvider` is vendor-neutral and can wrap a generative LLM, classifier or other structured scorer. `JevProvider` is a specialized adapter for Jev-style bounded probabilistic questions. The repository calls these **fast/structured appraisal providers**, not implementations of Kahneman System 1.

```python
from affectcontrol import JevProvider

provider = JevProvider(call=my_backend)  # strict by default
```

Missing/malformed fields do not silently become zero. Choose explicitly:

```python
JevProvider(call=my_backend, missing_policy="raise")        # default
JevProvider(call=my_backend, missing_policy="neutral")      # missing → 0.5
JevProvider(call=my_backend, missing_policy="conservative") # control-relevant missing values biased upward
```

## Memory and reflection

`MemoryControl` is the single source for memory salience and reflection triggering. `ControlPolicy` consumes those outputs instead of recomputing a second memory formula.

This separation lets memory policy be ablated independently from priority/preemption policy.

## Lifecycle scheduler

AffectControl now contains a deterministic experimental scheduler:

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

Lifecycle:

```text
QUEUED → RUNNING ⇄ PAUSED → DONE
                    └──────→ FAILED / CANCELLED
```

It records:

- preemption latency;
- deadline miss rate;
- wrong-preemption rate against scenario labels;
- rapid-preemption thrashing;
- pause/resume attempts and completion success;
- task switches.

The scheduler is an **experimental reference runtime**, not a production distributed scheduler.

## Configuration instead of hidden constants

Numerical policy choices live in dataclasses:

- `RuleProviderConfig`
- `StateConfig`
- `MemoryPolicyConfig`
- `ControlPolicyConfig`
- `SchedulerConfig`

They are documented in [docs/policy-parameters.md](docs/policy-parameters.md).

The repository intentionally labels the shipped values as **uncalibrated reference priors**. Use `benchmarks/sensitivity.py`, task fixtures, calibration data and ablation studies before choosing production or research values.

## Benchmarks

```bash
PYTHONPATH=src python benchmarks/scheduler_benchmark.py --episodes 200 --seed 17
PYTHONPATH=src python benchmarks/sensitivity.py
```

The scheduler benchmark runs randomized task-arrival episodes rather than printing three hand-written cases. It compares a static non-preemptive baseline with integrated affective control over deadline misses, preemption latency, wrong preemption, resume success and thrashing.

Current outputs are **engineering diagnostics, not scientific evidence**. See [benchmarks/README.md](benchmarks/README.md).

## Calibration utilities

```python
from affectcontrol import brier_score, expected_calibration_error
```

These metrics evaluate probabilistic appraisal outputs. They do not magically calibrate the control policy itself; policy weights and thresholds require separate sensitivity analysis or fitting.

## Test coverage

The test suite currently includes checks for:

- hard immediate override;
- task-scope isolation;
- transient unscoped events;
- memory/reflection single-source behavior;
- urgency negation handling;
- strict/neutral appraisal failure modes;
- state decay and outcome reappraisal;
- process-safe same-key state transactions;
- scheduler preemption, deadline miss, resume and wrong-preemption metrics;
- Brier/ECE calculations.

Run `pytest -q` to verify the exact current count.

## Repository layout

```text
src/affectcontrol/
├── config.py       # all reference policy parameters
├── types.py        # events, appraisal, scoped state, tasks
├── providers.py    # keyword/mock/structured appraisal adapters
├── state.py        # decay and outcome reappraisal
├── memory.py       # memory salience + reflection policy
├── control.py      # priority/interruption/attention/planning policy
├── scheduler.py    # experimental task lifecycle scheduler
├── storage.py      # process-safe local JSON state store
├── metrics.py      # Brier/ECE
├── harness.py      # scoped control orchestration
└── adapters/       # generic integration helpers
```

## Research status

The repository separates three things deliberately:

- **implemented engineering mechanisms**;
- **uncalibrated reference policy choices**;
- **research hypotheses that still require experiments**.

No novelty or superiority claim should be inferred from the presence of a mechanism or a benchmark script.

## Security

Read [SECURITY.md](SECURITY.md). High urgency or affective activation never authorizes privileged or irreversible actions.

## License

MIT.
