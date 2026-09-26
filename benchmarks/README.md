# Benchmarks

[中文](README.zh-CN.md)

The benchmark directory contains **engineering evaluation harnesses**, not published scientific results.

## Scheduler benchmark

```bash
PYTHONPATH=src python benchmarks/scheduler_benchmark.py --episodes 200 --seed 17
```

Each episode contains randomized task arrival times and durations. The current fixture includes:

- a running background task;
- a non-urgent noise task;
- a deadline-constrained urgent task;
- a mix of explicit-immediate and inferred-urgent cases.

The same scenario is evaluated under:

- `static`: no affective preemption;
- `affective`: integrated control with lifecycle preemption/resume.

Reported metrics:

- mean preemption latency;
- deadline miss rate;
- wrong-preemption rate using synthetic ground-truth labels;
- task thrashing from repeated preemptions inside a configured window;
- resume success rate;
- explicit user-override compliance;
- preemption and switch counts.

The synthetic labels are benchmark definitions, not claims about human judgment.

## Sensitivity scan

```bash
PYTHONPATH=src python benchmarks/sensitivity.py
```

The current scan varies interrupt threshold over a small grid and reports confusion counts against synthetic labels. It is deliberately simple so parameter dependence is visible.

## Interpreting results

Do not report a single benchmark number without also reporting:

- random seed and episode count;
- complete policy config;
- provider config;
- scenario generator version;
- static/non-persistent baselines;
- sensitivity or confidence intervals.

The current benchmark is designed to catch engineering regressions and expose parameter sensitivity before larger experiments are built.

## Workflow-shaped long-horizon diagnostic

`long_horizon_compare.py` replays task arrival, requirement revision, blocked/unblocked work, cancellation of stale work, explicit user overrides, deadline changes, pause/resume and completion. It compares four scheduler strategies on the exact same traces:

- static priority;
- earliest-deadline-first (EDF);
- urgency-only;
- integrated affective control.

Run:

```bash
python benchmarks/long_horizon_compare.py --episodes 200 --seed 41
```

A 200-episode diagnostic run on 2026-09-27 produced the following point estimates (95% bootstrap intervals are emitted by the script):

| Strategy | Deadline miss | Override compliance | Wrong preemption | Thrashing |
|---|---:|---:|---:|---:|
| static | 0.400 | 0.000 | 0.000 | 0.000 |
| EDF | 0.213 | 1.000 | 0.613 | 0.675 |
| urgency-only | **0.200** | 1.000 | 0.000 | 0.000 |
| affective | 0.298 | 1.000 | 0.000 | 0.000 |

This is deliberately **not** presented as evidence that AffectControl outperforms the baselines. In this workload, urgency-only has the best deadline result. EDF improves deadlines but over-preempts and thrashes. The current affective policy trades deadline performance for fewer unnecessary switches. These traces are semi-synthetic diagnostics, not external-validity evidence.

## Calibration split

`calibration_split.py` fits a decision threshold on the training partition only, freezes it, then reports Brier/ECE and threshold metrics on the held-out partition. Input CSV schema:

```text
score,label
0.82,1
0.14,0
```

This exists to prevent choosing an interrupt threshold on the same cases used for reporting test performance.
