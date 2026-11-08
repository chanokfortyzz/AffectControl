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


## Session-clustered frozen-label appraisal comparison (2026-11-08)

The `appraisal_compare.py` evaluator now accepts `session_id` or
`cluster_id` per JSONL row. Paired Brier differences are averaged **within
each session**, then averaged equally across sessions, and the 95% percentile
bootstrap resamples entire sessions with replacement. Different session
lengths must not silently alter the independent experimental unit.

- Missing IDs on all rows: descriptive row-mean only, **no CI**.
- Mixed missing and present IDs among paired rows: evaluation **fails**.
- One independent session: point estimate only, **no CI**.
- Provider-specific Brier metrics remain event-weighted and may not equal
  session-equal paired differences. Do not conflate these estimands.
- Compare only providers on the **same labeled cases**; report coverage.
- Multiple pairs are exploratory until a primary comparison is predeclared.
- This still depends on independent session sampling, honest labels, and a
  frozen test split; it is not evidence of a causal intervention effect.

## Public external source integrity check (2026-11-08)

Run `agentrx_integrity.py` against the two pinned files described in
`docs/external-reality-check-2026-11-08.md`. This checks public
trajectory-to-annotation consistency and pinned SHA256 digests. It does
**not** treat AgentRx error-localization labels as an AffectControl
interruption-ground-truth oracle, or report success rate improvements.


## Read-only S1 pseudonymous event coverage audit (2026-11-08)

`s1_shadow_audit.py` consumes only the pre-existing, pseudonymized
S1 observation metadata. Unknown fields (including raw content) are
rejected, and the report contains no source trace IDs or task text.
The audit is **not an AffectControl intervention**.

```bash
python -m benchmarks.s1_shadow_audit --input /path/to/changes.pseudonymous.jsonl
```

The locally verified 202-row S1 source yielded 17 distinct task
trace IDs: **6** unambiguous start/terminal status-event spans, **2**
ambiguous and **9** incomplete. Median status-event interval was
**419 seconds**, not active task compute time. No independently
verified acceptance, real deadlines or observed preemption labels
could be derived; research status remains E1. Full source hash,
reproducible protocol and limitations are recorded in
`docs/s1-shadow-evidence-audit-2026-11-08.md`.


## Controlled real-process lifecycle audit (2026-11-08)

`task_lifecycle.py` adds a research-only, SHA256-linked and
monotonic-timestamped task event ledger with `start / pause / resume /
finish / fail / check` states, linked to actual isolated
`capture_execution.py` process receipts. A `check` is a **separate
local subprocess exit**, **not** external independent acceptance.
Incomplete lifecycles are censored, and duplicate or mismatched
receipts, forged transitions and nonzero exits labelled successful
are rejected. See `docs/real-multitask-lifecycle-pilot-2026-11-08.md`
for the executed two-task interleaving and limitations. Evidence
remains E1, not a real Agent scheduler policy trial.


## Real subprocess crossover: negative exploratory finding (2026-11-08)

`prospective_local_crossover.py` executes fixed, allowlisted local
pytest tasks in child processes, with the real AffectControl reference
scoring formula choosing their queue order. It freezes the plan before
the first run, includes source/plan hashes, and randomizes then balances
AB/BA strategy order. It never touches production Sage/S1.

The initial unbalanced two-pair experiment yielded artificially timed
local exits of 50% for Affective versus 75% for Urgency-only. Because
both pairs ran affective first, the result was kept unchanged and a
**post-pilot, explicitly nonconfirmatory AB/BA amendment** was made.
The balanced rerun produced 62.5% versus 75%, respectively. This is a
mechanistic local-compute exercise, not real-world deadlines, task
acceptance or any independent causal advantage. Negative results and
the priority-vs-urgency conflict are recorded without retuning.

See `docs/exploratory-local-crossover-2026-11-08.md` and
`docs/balanced-crossover-method-amendment-2026-11-08.md`.
Research evidence remains E1.


## Explicit-user hard override regression (2026-11-08)

A factored behavioral check found that an explicit immediate user
command could be blocked by a higher weighted-score background task
even when that background was preemptible. The Affective reference
scheduler now enforces user-confirmed hard override **above ordinary
ranking**, without changing comparative baseline strategies, weight
parameters, or nonpreemptible work. This is a policy-contract bug fix,
not evidence that AffectControl beats Urgency-only; see
`docs/explicit-user-override-regression-2026-11-08.md`.


## Research-only explicit override deadline conflict projection (2026-11-08)

`affectcontrol.override_risk` projects a potential *incremental*
deadline miss to the task displaced by a valid explicit user override.
The `affective` scheduler records conditional per-decision projections
and exposes **aggregate counters** only in its metrics summary;
it does **not** change whether the explicit instruction executes.
Missing deadlines, nonfinite durations or unverifiable assumptions
are not interpreted as proof of safety. The model is one-processor,
fixed-work-time and diagnostic only. A deterministic fixed task pair
showed one newly projected miss and one simulated realized miss.
See `docs/explicit-override-conflict-projection-2026-11-08.md`.
Research status: **E1**.


## Displaced-task risk stress: future arrivals break calibration (2026-11-08)

`override_risk_stress.py` executed **1,536** authored deterministic
scenarios as **3,072 matched reference scheduler replays**. With
no further arrivals, the conditional two-task projection agreed with
the corresponding simulator in all 256 cases. When a third explicit
task arrived later, precision and recall of **incremental displaced
deadline misses** fell to 20% in the 1,280 deliberately synthetic
shifted cases. The code contains reproducible false-positive and
false-negative scenarios. The `OverrideRisk` result now advertises
its no-future-arrivals assumption and unvalidated external calibration
status explicitly. Do not deploy it as a real-time risk probability.
See `docs/override-risk-stress-2026-11-08.md`. Evidence remains E1.


## External real historical workload arrivals, without fake deadlines (2026-11-08)

`pwa_arrival_audit.py` ingests two pinned public SWF 2.2 historical
HPC job logs (KTH and Cornell CTC) from a pinned, checksum-verified
GitHub mirror. Of 105,599 records, **105,574** have valid recorded
submit timestamps and positive actual job runtimes. Event-origin
next-arrival frequency within 60 seconds is **30.59% at KTH** and
**44.27% at CTC**, whereas uniform-in-time frequency is **4.76%**
and **10.80%**. The difference demonstrates sampling dependence and
non-isolated arrivals in these historical *HPC* contexts, not Agent
task arrival probabilities. A requested runtime/CPU limit is NOT a
user task-completion deadline; no intervention outcomes or verified
Agent acceptance were obtained. The two entire raw logs remain
gitignored. Full provenance, exact file checksums, data quality and
limitations: `docs/historical-real-arrival-external-audit-2026-11-08.md`.
Evidence level remains E1.


## Externally executed CI outcomes are not independent Agent acceptance (2026-11-08)

`github_ci_evidence.py` reads authenticated GitHub Actions REST API
run/job metadata, pins the repository, full revision hash and exact
six-OS/Python matrix, rejects incomplete, failed or mismatched inputs,
and writes a create-only, redacted local evidence report. It has
verified a **6/6 passed** prior commit, the **4/6 passed and 2/6
Windows-failed** historic SWF-test commit, and the subsequent
**6/6 passed** Windows fix commit. These are independently hosted
*automated repository tests*, **not** human acceptance of Agent tasks,
user completion deadlines, or causal scheduler outcomes. See
`docs/github-ci-evidence-audit-2026-11-08.md`. E1 unchanged.


## Named-task machine checks on GitHub runners (2026-11-08)

`task_acceptance_spec.json` fixes two narrow research-code test
contracts: the explicit user override's safety behavior (3 selected
tests), and SWF source-byte integrity (2 selected tests).
`task_acceptance.py` executes only those frozen selectors and emits
a case/commit/contract SHA256-pinned JUnit receipt. A dedicated
GitHub Actions workflow executes both cases on Ubuntu and Windows.
The separate verifier checks JUnit hashes, exact frozen test selection,
revision and recorded outcomes. Local preflight of 5 selected checks
and 8 receipt tests succeeded. External GitHub job and artifact
verification must be performed before claiming remote execution.

This is **externally hosted machine verification of named research
code tasks**, *not* independent human Agent task acceptance or
natural deadline/causal intervention evidence. Documentation:
`docs/named-task-acceptance-pilot-2026-11-08.md`. E1 unchanged.


## E2 evidence-readiness census (2026-11-08)

The privacy-reduced e2_evidence_census.py checked local S1 and
Agent run-summary sources: 202 watcher events, 196 shadow events
and six run summaries. No complete E2-admissible episodes could
be demonstrated because naturally sourced task deadlines, trusted
cross-system joins, independently judged task outcomes and prospective
policy allocations were absent. This is missing evidence, NOT a
failure label. No task content or raw logs leave gitignored storage.
Details: docs/e2-readiness-data-gate-2026-11-08.md. E1 unchanged.

## Real executor-separated Agent coding-test evidence (2026-11-08)

The agent_eval_hidden_recheck.py auditor checks frozen external-to-
executor hidden suites and archived public/hidden log hashes, then
actually reruns hidden tests against isolated copies of six preserved
coding worktrees. Five hidden suites passed, one failed. The
individual task programs and logs remain private and outside Git.
This corrects the overly broad interpretation of the original
summary-only census: executor-separated code tests DO exist, but
natural deadlines and AffectControl policy experiments still do not.
See docs/agent-eval-hidden-oracle-recheck-2026-11-08.md. E1 unchanged.

## S1/Bus authenticated event join gate (2026-11-08)

The S1-Bus join audit inspected 202 pseudonymous S1 records and
two historic Bus messages. No Bus actor identity was verified and
zero source joins were admitted. The research-only proof verifier
requires separate intake/S1/Bus HMAC attestations bound to real
source event IDs, request hash, consistent timestamps and replay
protection. Seventeen synthetic protocol tests passed including
forged matches and replay. No synthetic proof is claimed to be a
real Bus event, no keys were deployed, and no Sage production task
was changed. See docs/s1-bus-authenticated-join-gate-2026-11-08.md.
E1 remains.

## Prospective origin-bound S1/Bus attribution v3 (2026-11-08)

The v3 gate signs the entire canonical source event and rejects
after-the-fact correlation of legacy messages with no original
source-record token. All historical sources remain unbound:
202 real S1 watcher events, two Bus message events and zero
authenticated cross-source joins. Positive tests are synthetic.
Independent intake/S1/Bus key custody and prospective source writers
are not installed. See the v3 origin-bound protocol document.
Evidence remains E1.
