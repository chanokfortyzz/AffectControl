# Evidence Status

[中文](evidence-status.zh-CN.md)

## Current claim level

AffectControl is currently an **engineering and experimental framework**, not a validated affective-control theory.

What exists today:
- task/goal-scoped persistent affective state;
- a configurable control policy and lifecycle scheduler;
- deterministic, mock, and System-One/Jev-style appraisal adapters;
- concurrency-safe local JSON persistence;
- synthetic interruption/deadline/resumption diagnostics;
- sensitivity tooling for policy thresholds.

What does **not** exist yet:
- calibrated policy parameters;
- statistically powered empirical results;
- formal comparison against strong affective/motivational baselines;
- validation on realistic long-horizon workloads;
- evidence that the external control-plane mechanism is superior to representation-level or learned alternatives;
- a peer-reviewed paper.

## Evidence ladder

| Level | Meaning | Status |
|---|---|---|
| E0 | API/unit correctness | done |
| E1 | synthetic scheduler diagnostics | partial |
| E2 | calibrated synthetic/semi-synthetic evaluation | not done |
| E3 | semi-real long-horizon benchmark validation | not done |
| E4 | real workload external validity | not done |
| E5 | peer-reviewed mechanistic/theoretical claim | not done |

No claim in the repository should imply a level above the evidence currently available.

## 2026-09-27 stronger synthetic baselines

E1 now includes a workflow-shaped trace runner and static priority, EDF, urgency-only, and integrated-affect scheduler baselines. The first 200-episode diagnostic does **not** favor the affective policy on deadline misses: urgency-only is better. This is useful falsification pressure, but it still does not raise the project to E2 because the policy is uncalibrated and the trace distribution is authored by this project.
