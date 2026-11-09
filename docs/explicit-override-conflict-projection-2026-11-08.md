# Explicit user override: projected deadline-conflict audit (2026-11-08)

## Research question

After fixing the authenticated hard-override ranking bug, can the
reference scheduler **disclose** a potential cost to the task being
interrupted without suppressing or silently rewriting a user's explicit
immediate instruction?

The implemented answer is a conservative, *diagnostic-only*
single-processor displaced-task projection. No emotion weights,
interrupt decisions, baseline strategies or Sage/S1 production
behaviors were modified.

## Estimand and assumptions

For an incoming explicit user task arriving at time `t`, with
remaining processing time `I`, and the currently executing task with
remaining time `B` and deadline `D`, the audit calculates:

- Uninterrupted projected background finish: `t + B`.
- After uninterrupted explicit task: `t + I + B`.
- Newly projected deadline miss: `t + B <= D < t + I + B`.

This is valid only for a **hypothetical single work resource** with
fixed known processing times, zero switching cost, no competing task
arrivals and no additional pauses. It does not predict outcomes under
uncertain Agent execution times or validate a real-world user deadline.
It measures only the **immediately displaced** task, not total
downstream delay among queued work.

The optional `deadline_basis` tag is `observed`, `inferred`,
`synthetic` or `unspecified`. It is self-reported metadata and
**not independent provenance attestation**. Missing deadlines and
unquantifiable processing times produce explicit unknown states,
never an inferred safe outcome.

## Implemented behavior

The research AffectiveScheduler adds local-only
`override_risk_events` for *actual explicit-user preemption*
decisions. The per-event audit contains only task IDs, calculation
inputs, a result category and fixed limitations, not user task text
or prompts. Aggregate `SchedulerMetrics.summary()` includes:

- `override_displaced_task_projections`
- `override_newly_projected_misses`
- `override_already_projected_misses`
- `override_missing_deadline_projections`
- `override_unquantifiable_projections`

A metric is a **counter of projections, not actual violations**.
The scheduler continues to obey valid user instructions even when
the projection warns of a potential miss. Nonpreemptible tasks remain
protected. Other scheduling baselines are unchanged.

## Fixed, executed simulation check

One already-running P0 task (4 seconds total work, synthetic deadline
at t=5), and one P3 incoming task at t=1 (3 seconds remaining,
synthetic deadline t=20) were run twice with the reference
AffectiveScheduler. The only changed factor was the explicit
user-immediate flag.

| Case | Background finished | Incoming finished | Observed simulated misses | New projected miss |
|---|---:|---:|---:|---:|
| Flag false | t=4 | t=7 | 0 | no projection |
| Flag true | t=7 | t=4 | 1 | 1 |

The projected miss matched this deterministic simulator, which is
expected given the exact same fixed processing-time assumptions. It is
**not** external validation or evidence of deployment safety.

The new `tests/test_override_risk_audit.py` tests positive/negative
projections, unknown/missing/invalid inputs, already-unavoidable
misses, nonpreemptibility, baseline isolation, an exact deadline
boundary, and the complete scheduling call path.

## Decisions and boundaries

1. **Do not silently block a legitimate explicit user instruction**
   to optimize a model-estimated deadline; disclose the competing
   risk instead. Authentication of the user-origin flag must happen
   at a trusted intake boundary. Task metadata alone is insufficient.
2. An immutable, user-specified task deadline and its provenance
   must be collected prospectively; synthetic timestamps are not
   adequate for operational claims.
3. Do not conflate predicted incremental misses with realized misses.
   For a legitimate live study, separately record both categories,
   uncertainty calibration, actual acceptance, displaced-task effects
   and user-accepted precedence.
4. Independent adjudication and multi-lineage real tasks remain
   missing. **Evidence status remains E1.** No production deploy.

To reproduce:

```bash
uv run --extra dev pytest -q tests/test_override_risk_audit.py
uv run --extra dev pytest -q
```
