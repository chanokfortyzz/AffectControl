# Exploratory real subprocess ordering crossover — 2026-11-08

## Question

Does the uncalibrated affective scheduler queue four **real executed**
local verification tasks differently from the urgency-only baseline?
Does a fixed set of **researcher-assigned** deadlines show an
observable mechanical advantage or disadvantage?

This is a **negative exploratory result**, not an independent real-world
study. Nothing ran in Sage, S1, or production scheduling.

## Prior to running

The pilot command froze its task list, assigned deadlines, model
reference parameters, random seed, and arm order in
`.research-data/crossover-pilot-20261108-p2-seed20261108/frozen-plan.json`
before starting any of the 16 child processes. Plan SHA256:
`d6d96d4d7cff5e248e46044fca1fd11a5020cf2d82c75552785f7a390912a229`.

Four tasks were actual repository test runs:
`tests/test_core.py`, `tests/test_scheduler.py`,
`tests/test_workloads.py`, and `tests/test_trace_cohort.py`.
No arbitrary shell command was accepted. Each strategy ran the same
four task types in a new subprocess; each had two repeated rounds.

The researcher assigned task deadlines relative to the start of
each arm, **not real user deadlines**: 2.0, 1.0, 2.6, and 3.6 seconds,
respectively. These were chosen before this execution, but they are
artificial constraints and must not be described as natural deadlines.

The code was **uncommitted when the first pilot ran**; the stored
Git SHA `c778914` identifies the previously committed repository base,
not the exact experiment script. The script is archived by a subsequent
commit, but this first pilot does not carry independent signed software
provenance.

## Actual recorded result

| Trial | Arm | Queued order | All tests exit zero? | Exit zero by assigned deadline |
|---|---|---|---|---:|
| Pair 1 | Affective | trace → workloads → core → scheduler | 4/4 | 2/4 |
| Pair 1 | Urgency-only | scheduler → trace → workloads → core | 4/4 | 3/4 |
| Pair 2 | Affective | trace → workloads → core → scheduler | 4/4 | 2/4 |
| Pair 2 | Urgency-only | scheduler → trace → workloads → core | 4/4 | 3/4 |

Observed mean descriptive paired contrast, affective minus urgency:
**−0.25** (−25 percentage points for this artificial local
timely-test-exit measure). There is no confidence interval.
Affective placed the lexical "urgent right now" task last, while
urgency-only placed it first, a potentially important failure mechanism
for the current reference-weighted model.

**Design problem discovered:** both arms ran in the same order
(Affective, then Urgency) on both pairs. Although produced by
the pre-frozen random seed, this is not balanced; strategy and
execution-order effects are confounded.

## Interpretation & corrective protocol

The pilot is one repo/one lineage, with no live process preemption.
The test exit code is not an independently verified task acceptance
label; no natural deadline or observed actual working-time evidence
was available. Startup overhead and warm OS caches can affect this
tiny sample. This cannot justify production use, causal superiority,
or evidence level E2.

A balanced AB/BA follow-up may eliminate this obvious order imbalance,
but because the imbalance and negative result are **already known**,
it must be labeled a **post-pilot methodological amendment**, not
a prospectively independent confirmatory replication. Do not change
policy weights, deadlines or task selection to chase a favorable
result. Any preregistered confirmatory study needs genuinely independent
task lineages with natural deadlines and external outcome adjudication.
