# Explicit post-pilot amendment: balanced AB/BA crossover (2026-11-08)

**Status: exploratory methods sensitivity check.** The first real-process
pilot had both arm orders Affective → Urgency. Its negative result was
seen **before** this amendment, so the amendment is not a fresh
confirmatory preregistration. The original unbalanced pilot, including
its unfavorable result, is preserved separately in
`docs/exploratory-local-crossover-2026-11-08.md` and source commit
`5b713cf`. No parameter, workload, priority, or deadline was tuned
after that pilot.

## Corrective change and source freezing

- Revised code **requires an even number of pairs** and enforces
  AB/BA alternating ordering. Randomness selects only the first arm,
  before the experiment; the next pair reverses the order.
- Source commit recorded in the plan:
  `b7361e3f298c3e0c73f29249e19a7221f5b8ecf2`.
- Frozen plan SHA256:
  `e57e28d8a51874e4106664ff57cdb56ecd95913d79c03dfb51db72829fa260e3`.
- Plan, live process receipts and complete detailed results are stored
  locally in the excluded research directory
  `.research-data/crossover-balanced-v2-20261108/`.
- Plan also includes the Python runner's source file SHA256, allowing
  detection of an uncommitted change to the execution logic.

Exact frozen experiment: 2 pairs, 4 tasks per arm, 16 real subprocess
runs; strategy order **Affective → Urgency** then
**Urgency → Affective**. All 16 local processes exited with code zero.

The endpoint was **exit code 0 by an experimentally assigned elapsed
deadline**, not externally adjudicated task success. Artificial
deadlines were unchanged from the first pilot:
core 2.0 s; scheduler 1.0 s; workloads 2.6 s; trace 3.6 s.

## Actual observed results

| Pair | Strategy | Task order | Local timely exits | Arm elapsed |
|---|---|---|---:|---:|
| 1 | Affective | trace, workloads, core, scheduler | 3/4 | 2.308 s |
| 1 | Urgency-only | scheduler, trace, workloads, core | 3/4 | 2.492 s |
| 2 | Urgency-only | scheduler, trace, workloads, core | 3/4 | 2.923 s |
| 2 | Affective | trace, workloads, core, scheduler | 2/4 | 2.466 s |

Affective's mean artificial timely-exit rate: **62.5%**.
Urgency-only: **75.0%**. Equal-weight paired difference
Affective minus Urgency: **−12.5 percentage points**.
No CI or inferential p-value is justified from two repeats of one
research codebase. The relative result moved toward zero after
arm-order balancing, a reason not to overinterpret the initial −25 pp.

## Post-pilot mechanistic audit (not another preregistered test)

The frozen reference policy, evaluated without new task outcomes at
elapsed time zero, generated:

| Task | Base priority | Lexical urgency | Affective score | Urgency score |
|---|---|---:|---:|---:|
| core | P2 | 0.3 | 1.5589 | 0.305 |
| scheduler (contains "urgent ... right now") | P3 | 1.0 | 1.4768 | 0.850 |
| workloads | P1 | 0.3 | 1.8823 | 0.355 |
| trace | P0 | 0.3 | 2.1989 | 0.405 |

Thus the Affective ranking puts the routine P0 trace task
ahead of the urgent-phrase P3 scheduler task, while the
Urgency-only baseline puts the latter first. This is a
**priority-weight/salience conflict candidate**, not evidence that
the explicit user override is broken: the experimental input did
NOT set `explicit_user_immediate=True`. The current implementation
does not have an independent human label validating which order
a real user would want. No weights were modified.

## Research gate and responsible interpretation

This study has one source lineage, all unit-test tasks from a single
repository, artificially chosen time targets, no actually preempted
running subprocess, no independent acceptance oracle, and no live
human interruption preferences. The order balanced only one major
source of execution bias; OS performance/cache variability remains.
There is no basis for promoting to E2 or for statistical/general
causal claims.

Next work should freeze a new task portfolio with **naturally
observed user deadlines**, externally judged completion, and
task-independent source lineages; make explicit user override and
lexical urgency separately specified factors. Include an ablation
that removes the affect-related term without changing all other
weights, and compare with Urgency-only and EDF. Report negative
results and guardrails, and do not deploy to Sage before independent
prospective validation.

## Reproduction

```bash
uv run --extra dev python -m benchmarks.prospective_local_crossover \
  --root .research-data/crossover-balanced-new-id --pairs 2 --seed 20261108

uv run --extra dev pytest -q tests/test_prospective_local_crossover.py
```

A new run must use a **new** output directory; the collector refuses
to overwrite evidence. Only aggregate outcomes belong in this
repository; all subprocess receipts stay gitignored.
