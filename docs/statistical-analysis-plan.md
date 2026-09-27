# Statistical Analysis Plan

[中文](statistical-analysis-plan.zh-CN.md)

This plan is prospective guidance for future confirmatory studies. It does not upgrade current E0–E1 evidence.

## Experimental unit

Use a workload/session as the primary unit for scheduler comparisons. Do not treat every scheduler tick or state update as an independent sample.

For repeated tasks from the same project/day/trajectory, preserve cluster identifiers and use cluster-aware resampling or hierarchical analysis.

## Primary appraisal endpoint

For a frozen human interruption label, pre-specify Brier score as the primary probabilistic endpoint. Report ECE, AUROC, fixed-threshold confusion metrics, latency and cost as secondary endpoints.

Thresholds must be selected on train/validation data and frozen before final test evaluation.

## Primary scheduler endpoint

Pre-specify one primary operational endpoint before the confirmatory run, such as deadline miss rate or binary task completion. Report preemption latency, wrong preemption, resume success, starvation, thrashing, token cost and wall time as secondary outcomes.

Run every scheduler strategy on matched traces whenever possible.
## Inference

For matched continuous/rate outcomes, report paired effect differences with confidence intervals using session-level bootstrap resampling. For paired binary outcomes, use a paired binary analysis (for example McNemar-style discordance analysis) rather than an independent-proportions test.

Do not rely on a p-value without an effect size and interval.

## Multiple comparisons

Choose one primary baseline or apply a pre-declared correction such as Holm when testing several providers/strategies. Do not select the comparison after seeing results.

## Leakage control

Split by task lineage/session/project rather than random event rows when nearby events share context. Provider calibration, policy fitting and threshold selection must not see final test labels.

## Power planning

Do not estimate confirmatory power from the current tiny operational pilot. First define a minimum effect of practical interest, then use pilot data only to estimate variance/discordance and simulate required session counts under the intended paired design.

Document assumptions, attrition, clustering and the power procedure before collecting the confirmatory test set.

## Negative results

Publish pre-specified primary outcomes even when the affective/controller hypothesis loses to a simpler baseline. Parameter changes motivated by test-set failures belong to a new experiment, not a rewritten result.
