# Integration Guide

[中文](integration.zh-CN.md)

## 1. Give every persistent unit a scope

Use a stable `task_id` or `goal_id` for anything that should accumulate state.

```python
from affectcontrol import Event

event = Event(
    text="review the proposal today",
    task_id="review-42",
    explicit_priority="P2",
)
```

Unscoped events are intentionally transient.

## 2. Keep authorization outside

Treat `ControlBias` as control advice. Permission, credentials, deployment, destructive actions, financial actions and confirmation gates remain host-runtime responsibilities.

## 3. Choose failure semantics before adding a model

Start with `RuleProvider`. When adding a System-One/calibrated backend, choose what model failure means:

```python
from affectcontrol import JevProvider
provider = JevProvider(call=backend, missing_policy="raise")
```

Do not leave failure behavior implicit.

## 4. Persist state if continuity matters

```python
from affectcontrol import AffectControlHarness, JsonStateStore
store = JsonStateStore("runtime/state.json")
h = AffectControlHarness(provider, store=store)
```

The included store supports local multi-process serialization. For distributed systems, implement an adapter backed by a transactional store.

## 5. Map outputs deliberately

| Output | Typical host use |
|---|---|
| `effective_priority` | queue ordering |
| `should_interrupt` | request preemption only if current work is preemptible |
| `planning_effort` | reasoning/planning budget |
| `attention_weight` | attention/global-workspace weighting |
| `memory_salience` | retrieval/consolidation weight |
| `reflection_trigger` | reflection/replanning request |

## 6. Feed outcomes back by scope

```python
h.outcome("review-42", success=True)
h.outcome("review-43", success=False)
```

Outcome reappraisal changes only that scope.

## 7. Use the scheduler only if you need an experimental runtime

The included `AffectiveScheduler` is useful for controlled comparisons. Existing production schedulers can instead consume `ControlBias` through an adapter.

## 8. Log enough to audit behavior

Record:

- task/goal scope;
- raw provider output;
- provider failure policy;
- state before/after transition;
- complete config dataclasses;
- control output;
- scheduler decision;
- outcome;
- latency/cost;
- human/user overrides.

Without this, calibration and failure analysis are not reproducible.
