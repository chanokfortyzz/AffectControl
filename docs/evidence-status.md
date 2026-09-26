# Evidence Status

[中文](evidence-status.zh-CN.md)

## Current claim level

AffectControl is currently an **engineering and experimental framework**, not a validated affective-control theory.

What exists today:
- task/goal-scoped persistent affective state;
- a configurable control policy and lifecycle scheduler;
- keyword, mock, structured-provider, and Jev-style appraisal adapters;
- local JSON and SQLite persistence with concurrency tests;
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

## Current negative diagnostic results

The current semi-synthetic workload should be read as a falsification tool, not a showcase. On a held-out 200-seed diagnostic split:

| Strategy | Deadline miss | Wrong preemption | Thrashing | Override compliance |
|---|---:|---:|---:|---:|
| static | 0.400 | 0.000 | 0.000 | 0.000 |
| urgency-only | **0.200** | 0.000 | 0.000 | 1.000 |
| learned logistic interruption | 0.222 | 0.000 | 0.000 | 1.000 |
| EDF | 0.222 | 0.613 | 0.675 | 1.000 |
| affective reference policy | **0.299** | 0.000 | 0.000 | 1.000 |

The reference affective policy therefore does **not** beat the simple urgency baseline on deadline misses.

Feature ablation provides another negative result: on the current synthetic distribution, the minimal candidate feature set and most leave-one-feature-out configurations are nearly indistinguishable from the full ten-feature configuration. The project currently has no evidence that all ten candidate state variables are necessary.

These results remain E1 because the workload generator and labels are project-authored and the reference policy is uncalibrated.
