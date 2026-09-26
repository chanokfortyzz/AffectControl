# Research Plan

[中文](research-plan.zh-CN.md)

## Status

Implemented today:

- task/goal-scoped persistent state;
- decay and outcome reappraisal;
- configurable rule, memory, control and scheduler policies;
- explicit appraisal failure semantics;
- local process-safe state transactions;
- deterministic task lifecycle scheduler;
- scheduler metrics and calibration utilities;
- randomized scheduler benchmark and basic sensitivity sweep.

Not yet established:

- empirically calibrated default parameters;
- superiority over alternative agent control architectures;
- external validity on natural workloads;
- novelty relative to all adjacent literature;
- robust multi-provider calibration study;
- production distributed-scheduler performance.

## Main research question

Can persistent **task/goal-scoped** affective/motivational state improve long-horizon agent control when appraisal is integrated into scheduling, attention, memory and reflection rather than stored only as metadata?

## Why scope isolation is part of the hypothesis

A global affect vector confounds experiments: task A can change task B's scheduler score even when no relation exists. Therefore the primary experimental unit is a task/goal-scoped state trajectory, not an agent-wide scalar mood.

A separate research question may later test whether a higher-level global context state adds value on top of scoped state, but it must be modeled explicitly rather than accidentally leaked.

## Hypotheses

H1. Integrated scoped state reduces deadline misses or user-override latency relative to metadata-only affect, without unacceptable wrong-preemption or thrashing cost.

H2. Persistent unfinished tension improves task resumption/reflection only when paired with decay and outcome reappraisal.

H3. A fast calibrated appraisal layer can reduce control-plane latency/cost relative to generative appraisal while preserving useful decision quality.

H4. Explicit user intent remains more reliable than learned appraisal under provider failure and distribution shift.

H5. Parameter-sensitive gains disappear or reverse outside some policy region; therefore sensitivity surfaces must be reported alongside headline metrics.

## Baseline matrix

| ID | Appraisal | Persistent scoped state | Scheduler coupling |
|---|---|---:|---|
| A | Static priority | No | Static/non-preemptive |
| B | Rule/Fast appraisal | No | Priority only |
| C | Generative appraisal | Yes | Integrated |
| D | Fast/System-One appraisal | Yes | Integrated |
| E | Any appraisal | Yes | Metadata only |
| F | Integrated state | Yes | Memory only, no scheduling |
| G | Integrated state | Yes | Scheduling only, no memory/reflection |

D vs E tests affect-as-control vs affect-as-representation. F/G separate scheduler and memory contributions.

## Scheduler benchmark family

The reference scheduler gives these metrics an operational definition:

- **preemption latency**: time from interrupt request to actual preemption;
- **deadline miss**: a deadline task remains unfinished after its deadline;
- **wrong preemption**: benchmark ground truth labels an interrupt as unnecessary but the scheduler preempts;
- **thrashing**: multiple preemptions occur inside a configured time window;
- **resume success**: a paused task later resumes and completes;
- **switch count**: total runtime task switches.

Synthetic ground truth must be described as a fixture definition, not human preference truth.

## State benchmark families

### Persistence and isolation

- high activation in task A must not change task B without a linking event;
- repeated events in task A should accumulate only within A;
- unscoped events should remain transient.

### Decay

Measure state trajectories under multiple half-life settings and event densities. Report stability and recovery, not only final scores.

### Outcome reappraisal

Test success, partial success, failure and unresolved outcomes. Measure tension release, salience/tension escalation and false carry-over.

### Memory/reflection

Measure retrieval utility and reflection precision/recall under memory coupling on/off.

## Calibration

Provider probabilities and control-policy parameters are separate problems.

### Provider calibration

Use Brier score, ECE, reliability diagrams and task-specific discrimination metrics.

### Control-policy tuning

Use sensitivity surfaces, held-out scenarios and preferably nested tuning/evaluation splits. Never tune a threshold on the same episodes used for the headline comparison and then present the result as general performance.

## Parameter sensitivity

Every reported experiment should store:

- all config dataclasses;
- random seed;
- scenario generator version;
- task duration/deadline distributions;
- provider version and question schema;
- fallback mode;
- complete raw decisions and outcomes.

Major thresholds/weights should be swept before interpreting a single default configuration.

## Concurrency experiments

The included JSON store is local-process-safe. Test at least:

- two writers updating different scopes;
- two writers updating the same scope;
- repeated update contention;
- crash during write;
- store corruption detection.

Distributed-store experiments belong in a separate adapter/backend study.

## Literature program

Before novelty claims, maintain a sourced review covering:

- appraisal theory and affective computing;
- EMA/FAtiMA;
- PSI/MicroPsi and motivation-driven task selection;
- Global Workspace/attention competition;
- persistent memory/reflection in generative agents;
- affective action controllers;
- fast calibrated/System-One decision layers;
- preemptive scheduling and durable workflow systems;
- multi-agent state/concurrency control.

The paper should distinguish established mechanisms, engineering recombination and empirically supported new contributions.

## Safety invariant

No affective state grants authorization. Learned appraisal may affect only soft control unless an external policy system explicitly allows more.
