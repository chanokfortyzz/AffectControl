# Displaced-task risk projection: synthetic distribution-shift stress test

**Date:** 2026-11-08. **Research status: E1.**

## Why this was necessary

The previous proof-of-concept used a deterministic two-task schedule
with no further arrivals. The projection and simulator shared all
assumptions. Agreement in that case is almost a mathematical identity
and is **not evidence of real-world predictive calibration**.

This follow-up deliberately violated the no-future-arrivals assumption
using the *same* deterministic experimental tasks in a synthetic
full-factorial comparison of two task-arrival scenarios. No policy
weights, target labels, or task priorities were fitted to results.

## Frozen factorial design

- Background remaining work at t=1: 3, 4, 5 or 6 seconds.
- Incoming explicit immediate task: 1, 2, 3 or 4 seconds.
- Third exogenous explicit task at t=2: absent (0 seconds) or duration
  1, 2, 3, 4 or 5 seconds.
- Synthetic background deadline: integer t=3 through t=18.
- 4 × 4 × 6 × 16 = **1,536** unique scenarios.
- Every scenario ran two matched reference-Affective scheduler
  simulations: incoming user-immediate flag false and true.
  Total: **3,072 deterministic simulations**.

The projection was captured at t=1 (before any optional third task
arrival). The realized incremental-miss outcome was:

`(background misses deadline under explicit-override arm) AND
(background does NOT miss deadline under no-override arm)`.

This is a matched, scenario-specific incremental *binary* label, not
a counterfactual inference for a human user or real production Agent.
Task completion times in both arms were obtained from the simulator,
not the projection formula.

Protocol: `projected-override-risk-factorial-stress-v1`.
Frozen parameter-grid SHA256:
`0e28087e1e6550dc36d6e19d8044fe0b7705a633d8f0eb75088240d034f6bcd9`.
Source: `benchmarks/override_risk_stress.py`.
Outputs are aggregate-only; no private task contents are read.

## Executed results

| Future task arrival | N | TP | FP | FN | TN | Precision | Recall | Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| None | 256 | 40 | 0 | 0 | 216 | 100% | 100% | 100% |
| Third explicit task at t=2 | 1,280 | 40 | 160 | 160 | 920 | 20% | 20% | 75% |

The 75% accuracy under the second scenario is deceptive: there are
920 true negatives. **Precision and recall are each only 20%.**
This is a synthetic, deliberately hostile change in the simulator's
future-arrival structure; these percentages do not estimate any
population error rate.

Two independently reproducible counterexamples:

- **False positive:** remaining background=3 s, incoming=1 s,
  future task=1 s, background deadline t=4. The two-task projection
  predicts a new deadline miss. But the background actually finishes
  at t=5 in the no-override arm and t=6 in the override arm; it
  misses in **both**. Thus no *incremental* binary loss is observed.
- **False negative:** same durations, deadline t=5. The projection
  expects the background to finish by t=5 with the override, so
  predicts no new miss. The realized no-override completion is t=5
  (on time), while the override completion is t=6 (late). The third
  task makes the incremental loss real.

## Scientific interpretation

- A risk projection that shares all fixed-work assumptions with its
  test simulator is useful as a calculation check, not validation.
- The result is sensitive to later high-priority arrivals, competing
  queued work, and potential interactions between two user commands.
  A point-in-time model cannot know future arrivals.
- The model assesses one **displaced task**, not the complete queue.
  It must not be called a calibrated probability of SLA violation.
- A genuine field validation must record prospective predictions
  *before* the outcomes, keep all prediction records (including unknown
  cases), compare with a separately sourced outcome oracle, and
  use distinct independent task/project lineages. For causal
  incremental harm, use a randomized intervention design or justified
  logged-propensity methods: one observed production run cannot tell
  what the unchosen policy would have done.
- **Do not adjust weights using these synthetic cases** or deploy to
  Sage on the strength of this stress test.

## Engineering guardrails

The `OverrideRisk` result now explicitly includes:
`predictive_scope="conditional_on_no_future_arrivals"` and
`external_calibration_status="unvalidated"`. The module still
does not suppress an authorized immediate-user request. It reports
unknown for missing deadlines/durations, and the audit never treats
a projected new miss as a confirmed actual miss.

The 256 no-future scenarios and both synthetic counterexamples
are covered by new regression tests.

Reproduce:

```bash
uv run --extra dev python -m benchmarks.override_risk_stress
uv run --extra dev pytest -q tests/test_override_risk_stress.py
uv run --extra dev pytest -q
```

**Evidence remains E1.** These findings narrow the claim that can be
made about the projection; they do not establish field effectiveness.
