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
