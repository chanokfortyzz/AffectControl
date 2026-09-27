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

## Learned interruption baseline

```bash
python benchmarks/learned_baseline.py
```

The script trains a dependency-free logistic interruption model on seeds 0–99 and evaluates on frozen seeds 100–299. It is a deliberately modest supervised baseline, not a claim of state-of-the-art learning.

Current held-out point estimates:

| Strategy | Deadline miss | Wrong preemption | Thrashing | Override compliance |
|---|---:|---:|---:|---:|
| static | 0.400 | 0.000 | 0.000 | 0.000 |
| urgency-only | **0.200** | 0.000 | 0.000 | 1.000 |
| learned logistic | 0.222 | 0.000 | 0.000 | 1.000 |
| EDF | 0.222 | 0.613 | 0.675 | 1.000 |
| affective reference | **0.299** | 0.000 | 0.000 | 1.000 |

**Warning:** the current affective reference policy is worse than urgency-only on deadline misses in this synthetic distribution. Do not cite these numbers as evidence that affective control improves performance.

## Candidate-feature ablation

```bash
python benchmarks/feature_ablation.py
```

This runs the all-feature configuration, a minimal candidate set, and leave-one-feature-out masks. On the current synthetic workload, most masks are effectively indistinguishable on the reported scheduler metrics. This is evidence of **insufficient support for the 10-dimensional design**, not evidence that every dimension matters.

## External traces

```bash
python benchmarks/external_trace_runner.py trace.jsonl --strategy urgency
```

The JSONL importer is intended for externally collected or benchmark-derived event timelines. Merely importing an external trace does not establish external validity; source population, labels, sampling, privacy processing and train/test separation still have to be documented.
## Operational-shape interruption overlay

```bash
python benchmarks/operational_overlay.py sessions/ --overlay-mode explicit --assume-preemptible
python benchmarks/operational_overlay.py sessions/ --overlay-mode inferred --assume-preemptible
```

This runner freezes externally supplied task-arrival and duration-proxy traces, then injects one controlled interruption per session. It is intended for a **semi-real pilot** between fully synthetic workloads and full environment benchmarks.

Important limitations:

- no operational/private dataset is bundled in this repository;
- `--assume-preemptible` is an explicit counterfactual manipulation, not an observed fact;
- injected interruptions are synthetic conditions;
- observed wall-clock durations may be proxies rather than active compute time;
- a small number of sessions does not raise the evidence level by itself.

The output therefore labels itself `not external-validity evidence`.
## Frozen-label appraisal comparison

`appraisal_compare.py` compares multiple appraisal providers on the **same frozen binary labels**. Input JSONL:

```json
{"id":"case-1","label":1,"predictions":{"jev":0.82,"llm":0.71},"latency_ms":{"jev":45,"llm":4200}}
```

Run:

```bash
python benchmarks/appraisal_compare.py predictions.jsonl --threshold 0.5
```

It reports per-provider coverage, Brier score, ECE, AUROC, fixed-threshold confusion metrics, latency/cost summaries, plus paired bootstrap confidence intervals for Brier-score differences on common cases.

This evaluator deliberately does **not** tune thresholds. Use a separate train/validation procedure, freeze the threshold, then run this script on held-out labels.
