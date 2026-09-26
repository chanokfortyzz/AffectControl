# Failure Modes

[中文](failure-modes.zh-CN.md)

AffectControl is an experimental control/evaluation harness. The following failures are expected research risks, not edge cases to hide.

## Model/appraisal failures

- transport failure, malformed response, or missing fields;
- poor calibration under distribution shift;
- lexical baseline errors from negation scope, sarcasm, multilingual context, or multiple simultaneous tasks;
- correlated appraisal outputs that make nominally different state features redundant.

`JevProvider`/`StructuredAppraisalProvider` distinguish transport, response-shape, and missing-field errors. Fallback behavior must be explicit.

## Control failures

- deadline misses caused by excessive persistence or weak interrupt thresholds;
- unnecessary preemption and thrashing from aggressive thresholds;
- starvation of low-salience tasks;
- hysteresis or fixation after repeated failure signals;
- false confidence from uncalibrated reference weights;
- duplicated features creating apparent complexity without independent utility.

## State/dynamics failures

The bundled exponential decay and additive/multiplicative outcome updates are reference baselines only. They may fail under bursty event timing, dependent tasks, delayed feedback, non-stationary goals, or workload-specific recovery dynamics.

## Cross-task failures

Per-task scope prevents accidental state leakage, but it does not solve global resource allocation. `GlobalControlContext` is intentionally separate from affect state so cross-task competition can be modeled and ablated explicitly.

## Storage/runtime failures

- `JsonStateStore` is single-host and rewrites the state document;
- `SQLiteStateStore` is transactional on one host but is not distributed consensus;
- crashes between external side effects and control-state updates require host-level idempotency/recovery;
- optional framework helpers do not authorize tools or irreversible actions.

## Hard override risk

`explicit_user_immediate=True` is a control invariant, not an authorization primitive. It forces P0/interrupt bias and emits an audit trace event, but the host application must still enforce permissions, safety gates, approvals, and non-preemptible critical sections.

## Research failure criteria

A hypothesis should be considered unsupported when simpler baselines match or exceed it on frozen held-out workloads, when gains disappear under modest parameter perturbation, when ablation shows dimensions are redundant, or when results fail to replicate on external traces.
