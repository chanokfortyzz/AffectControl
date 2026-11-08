# External reality check: AgentRx failure-only sample (2026-11-08)

This is a **source and annotation-integrity smoke test**, not evidence
that AffectControl reduces interruption errors, failure rates or deadline misses.

## Source and audit scope

- Source: Microsoft [AgentRx](https://github.com/microsoft/AgentRx), MIT license.
- Pin: `7a18c79708e7671be15124460f4f7296107c2a55`.
- Source files:
  - `data/tau_retail/tau_dataset_failed.json`
  - `data/ground_truth/tau_ground_truth.json`
- SHA256 of traces:
  `17f8b3356d1124274cc7ed0215b5ff696970073dbed57394c60e775d5f85d717`.
- SHA256 of annotations:
  `58067689b2ec42f9cbfec2a84ec08d39cea4d8270617b55d0185862753642d16`.

Only these two ~0.94 MB public files were downloaded for this check;
the raw files are excluded from Git via `.research-data/`. Treat any
identifying names/tool content in public trajectories as potentially
sensitive before republishing them.

To reproduce, download those files from the pinned commit to a local
temporary data directory and run:

```bash
python -m benchmarks.agentrx_integrity \
  --traces .research-data/agentrx/tau_dataset_failed.json \
  --labels .research-data/agentrx/tau_ground_truth.json
```

The script verifies exact checksums, unique trajectory IDs, exact match
between labeled and source trajectories, unique root-failure references,
valid message step indexes, and category coverage. It deliberately does
not inspect user message text or forward it to other systems.

## Observed audit, executed 2026-11-08

| Check | Verified count |
|---|---:|
| Task trajectories | 29 |
| Matching annotated trajectories | 29 |
| Missing annotated trajectories | 0 |
| Individual failure annotations | 39 |
| Root-failure references matching annotations | 29 |
| Rewards equal to zero | 29 |
| Rewards greater than zero | 0 |

Failure categories among these 39 **error annotations**: underspecified
user intent 10, intent-plan misalignment 8, tool-output misinterpretation
8, instruction adherence 6, invalid invocation 4, unsupported intent 2,
and system failure 1. These are annotations, not independent task counts;
one task can have multiple errors.

## What is not identifiable

1. The 29 task runs were selected as **failed** and cannot estimate
   population failure rate, false alarms or preventive value.
2. AgentRx annotates likely critical *failure* steps; this does not label
   whether a human would prefer a scheduler **interruption** at that step.
3. A successful trajectory can still suffer a destructive intermediate
   error. Final reward alone is not a full safety oracle.
4. Offline re-ordering of an existing trajectory cannot reveal the actual
   outcome of an unchosen action. Randomized real interventions or an
   explicit, defended off-policy identification scheme would be required.
5. The data show one software/system family; no claim about independent
   task-lineage generalization is justified.

## Recommendation

Use this public dataset only as a validation/diagnostic source while
testing the provenance and label audit. Continue prospective primary
AffectControl vs urgency-only comparisons only when **human interruption
labels, independent task/session lineage, both positive and negative
cases, and observable task outcomes** are available in an appropriately
split dataset.

For the main endpoint, predeclare session-level deadline miss or task
completion and report paired cluster-aware uncertainty. Do not retroactively
change frozen thresholds/labels after inspecting final results.
