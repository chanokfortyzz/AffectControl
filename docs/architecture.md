# Architecture

[中文](architecture.zh-CN.md)

AffectControl separates appraisal, scoped state transition, memory/reflection policy, control policy, scheduling, and persistence. The separation exists to make ablation and failure analysis possible.

## Runtime graph

```text
Event(task_id / goal_id)
        │
        ▼
AppraisalProvider
        │
        ▼
Appraisal vector
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
        ├──► host runtime / adapter
        └──► experimental AffectiveScheduler
                    │
                    ▼
          QUEUED → RUNNING ⇄ PAUSED → DONE/FAILED
                    │
                    ▼
                  outcome
                    │
                    └────────► StateEngine.reappraise_outcome
```

## Scope model

Persistent state is keyed by `task_id` or `goal_id`.

This is a deliberate design constraint. A single global state vector causes cross-task contamination: a high-salience event in task A can otherwise raise the drive of task B without evidence that B is related.

Resolution order:

```text
Event.task_id
→ metadata.task_id
→ Event.goal_id
→ metadata.goal_id
→ no persistent scope
```

If no scope exists, the event is evaluated against a fresh transient state.

## Component responsibilities

### `AppraisalProvider`

Produces an `Appraisal`. It does not schedule tasks or authorize actions.

### `StateEngine`

Owns decay, evidence blending and outcome reappraisal. Numerical choices come from `StateConfig`.

### `MemoryControl`

Owns memory salience and reflection triggering. These values are computed once and passed into `ControlPolicy`.

### `ControlPolicy`

Produces priority/interruption/attention/planning recommendations. It does not duplicate memory policy.

### `AffectiveScheduler`

Provides a deterministic experimental task lifecycle so scheduler metrics can actually be measured. It supports queued/running/paused/done/failed/cancelled states, deadline pressure, preemption, resume and metric collection.

It is intentionally not presented as a production distributed scheduler.

### `JsonStateStore`

Uses a lock around read/modify/write plus atomic replace. This prevents local multi-process lost updates, including same-key transitions.

The lock is local-host synchronization only. Distributed deployments require a database or event store with transactional semantics.

## Failure semantics

Appraisal failure is explicit. `JevProvider` supports:

- `raise`: default; fail visibly;
- `neutral`: missing values become neutral 0.5 priors;
- `conservative`: control-relevant missing values bias upward.

The library does not silently interpret malformed provider output as calm/zero activation.

## Hard and soft control

Hard constraints belong outside the learned control layer. An integrator may encode explicit immediate intent as a hard invariant, while authorization, destructive-action, credential, financial and deployment gates remain external.

Soft controls include queue ordering, preemption recommendation, attention allocation, planning budget, memory salience and reflection triggering.

## Parameterization

All major numerical choices live in config dataclasses. Defaults are reference priors, not validated constants. See [policy-parameters.md](policy-parameters.md).
