# AffectControl

[中文](README.zh-CN.md) · [Architecture](docs/architecture.md) · [Policy Parameters](docs/policy-parameters.md) · [Integration](docs/integration.md) · [Research Plan](docs/research-plan.md) · [Benchmarks](benchmarks/README.md)

AffectControl is a framework-neutral research harness for studying **affect and motivation as control variables** in long-horizon agents.

The project is intentionally narrower than a full agent framework. It provides:

- task/goal-scoped affective state;
- appraisal provider interfaces;
- decay and outcome reappraisal;
- soft control bias for priority, interruption, attention, planning, memory and reflection;
- a deterministic task-lifecycle scheduler for controlled experiments;
- process-safe local JSON persistence;
- benchmark and calibration utilities.

> Status: research prototype. It does not claim human-like emotion, consciousness, or validated psychological equivalence.

## Research question

> Does persistent, task-scoped affective/motivational state improve long-horizon agent control when appraisal is coupled to scheduling, memory and attention rather than stored only as metadata?

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
from affectcontrol import AffectControlHarness, Event, RuleProvider

h = AffectControlHarness(RuleProvider())
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
from affectcontrol import AffectControlHarness, Event, JsonStateStore, RuleProvider

store = JsonStateStore("./runtime/affect-state.json")
h = AffectControlHarness(RuleProvider(), store=store)

h.process(Event("unfinished task A", task_id="A"))
h.process(Event("routine task B", task_id="B"))

state_a = h.get_state("A")
state_b = h.get_state("B")
```

`JsonStateStore` serializes local multi-process read/modify/write transitions with a lock plus atomic replace. It is **not** a distributed consensus store. Multi-host deployments should provide a transactional database/event-store adapter.

## State dimensions

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

State evolution is controlled by `StateConfig`; values decay over time and can be reappraised after outcomes.

## Appraisal providers

### `RuleProvider`

A transparent deterministic baseline. It includes explicit negation handling such as `not urgent`, `no rush`, `不急`, and `不用马上`. Its constants are configurable through `RuleProviderConfig` and are not presented as calibrated psychology.

### `MockProvider`

Used for unit tests and controlled ablations.

### `JevProvider`

A transport-injected adapter for calibrated/System-One-style appraisal backends. Network/auth code is intentionally external.

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
├── providers.py    # rule/mock/System-One-style appraisal adapters
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
