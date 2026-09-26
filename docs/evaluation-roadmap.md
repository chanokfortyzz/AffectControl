# Evaluation Roadmap

[中文](evaluation-roadmap.zh-CN.md)

## Phase 1 — calibration

- Build labelled interruption/priority datasets with train/validation/test separation.
- Calibrate appraisal outputs with Brier score, ECE, reliability diagrams and AUROC/PR where applicable.
- Fit control-policy weights/thresholds on train only; report held-out performance and sensitivity surfaces.
- Never tune against the final benchmark test set.

## Phase 2 — formal baselines

Compare at least:
1. static priority scheduler;
2. rules + scoped persistent state;
3. Jev/System-One appraisal + scoped state;
4. generative-LLM appraisal + scoped state;
5. explicit VAD first-/second-order dynamics;
6. isolated affect metadata (no control coupling).

Where open-weight access permits, add representation-level steering as a separate family rather than pretending it is the same mechanism.

## Phase 3 — semi-real long-horizon workloads

Use an interruption overlay on realistic environments such as OSWorld 2.0/2.1 or comparable self-hosted workflows. Inject dynamic requirements, deadlines, stale/contradictory state, resumptions and concurrent tasks.

Primary endpoints:
- binary/partial task completion;
- deadline miss rate;
- preemption latency;
- user-override compliance;
- wrong-preemption rate;
- resumption success;
- task starvation/thrashing;
- tokens, wall time and monetary cost.

## Phase 4 — external validity

Run on real or operationally realistic multi-hour workloads with frozen protocols, privacy scrubbing and pre-registered metrics. Report paired confidence intervals/effect sizes, not single-run anecdotes.

## Phase 5 — paper gate

A paper should only be drafted after Phases 1–3 produce reproducible results. A mechanism/theory claim requires substantially stronger evidence than an engineering-framework paper.
