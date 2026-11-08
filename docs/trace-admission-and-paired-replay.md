# External trace admission and matched replay (2026-11-08)

## Claim boundary

These tools prevent common evidence errors; they **do not** prove that
AffectControl improves any real agent. AgentRx's 29 failed trajectories
cannot be used as scheduler episodes without inventing task durations and
deadlines. On-device agent-evaluation logs were checked only for *schema
availability*: they contain timestamps but do not natively provide the
required measured execution times and observed task deadlines. No private
logs are included here.

## Data contract

Provide independently sourced **one-session-per-file** JSONL traces. The
event schema is documented at [external-trace-schema.md](external-trace-schema.md).
Admission now runs inside `load_jsonl_trace` itself, not only a CLI.

Each session needs a manifest JSONL entry:

```json
{"session_id":"s-001","lineage_id":"project-abc","trace_file":"s-001.jsonl","sha256":"<64 lowercase SHA-256 hex digits>","source":"consented:collection-protocol-v1","duration_basis":"measured","deadline_basis":"observed"}
```

- `lineage_id` identifies the **independent task/project/trajectory
  family**. Repeated sessions from the same lineage always stay in the
  same train, validation, or held-out test partition.
- The `trace_file` must resolve inside the supplied data root; external
  paths, traversals, and escaping symlinks are rejected.
- `sha256` is computed on original JSONL bytes; duplicates and changed
  sources are rejected.
- `duration_basis` is **measured**, **wallclock_proxy**, or **synthetic**.
- `deadline_basis` is **observed**, **inferred**, **synthetic**, or
  **none**. A declaration must match the presence/absence of deadlines.
- At least three independent lineages are required for separate train,
  validation and test sets. More independent lineages are necessary for
  useful statistical precision.
- Admissions validate chronological event order, unique task arrivals,
  referenced task state, finite timestamps/durations, valid event kinds,
  and the replay horizon. CLI JSON summaries intentionally omit event
  content.

Metadata is *self-declared*. A successful audit checks internal
consistency, **not** whether the provenance assertion is honest. Maintain
source permissions, the immutable event-generation code and independent
adjudication separately. Do not publish private task bodies.

## Step 1: freeze a cohort manifest

```bash
python -m benchmarks.trace_cohort --root /path/to/sessions \
  --manifest /path/to/manifest.jsonl --seed 17 \
  --out /path/to/cohort-audit.json
```

Record both `manifest_sha256` and `split_sha256` before looking at final
test outcomes. The split uses seeded lineage-level randomization (not
event-row randomization). The deterministic manifest audit is not a
power calculation, and may yield uneven case counts when lineages vary.

## Step 2: two-policy matched diagnostic

```bash
python -m benchmarks.trace_paired_eval --root /path/to/sessions \
  --manifest /path/to/manifest.jsonl --partition validation
```

Only records declaring `duration_basis=measured` and
`deadline_basis=observed` enter the paired diagnostic. Remaining
sessions are excluded and counted. The primary operational endpoint is
predeclared as **deadline miss rate**. Completion and simulated wall
time are secondary. The contrast is **affective minus urgency**,
computed for the same trace and averaged at the independent
`lineage_id` level; confidence intervals bootstrap lineages, not events.

When there is only one independent lineage, the CI is **withheld**.
When no eligible sessions exist, the contrast is **null**, not zero.
Train/validation work should precede test access; the tool refuses
`--partition test` unless `--unlock-test` is explicitly supplied.
This is an access warning, **not** cryptographic proof of a frozen
policy, and a pre-registered config/threshold hash and independent
review remain essential.

## Why this is not a causal result

An offline replay imposes **identical arrivals and durations** on two
policies. Real task execution, future arrivals, human actions, and
deadlines might change when a different scheduler intervenes.
Consequently, even a statistically precise replay contrast is a
**mechanical simulator result**, not the treatment effect of deploying
AffectControl. Any result from authored fixtures is E1. Real causal
identification needs controlled intervention/random assignment or a
defensible logged-propensity off-policy evaluation with coverage
requirements. Outcome labels must be recorded independently and
frozen before the final test.

## Current gate

- **Passed:** deterministic ingestion, checksum and lineage splits;
  two-policy matched replay; no-CI-on-one-lineage guard; default
  held-out test lock; repository regression tests.
- **Not achieved:** independently verified real scheduling durations,
  deadline oracles, genuinely exogenous workload sampling, sufficient
  independently labeled success and failure cases, randomized
  interventions, confirmatory power. E2 is **not** established.

Do not replace missing durations, preemptibility, deadlines or observed
outcomes with values reverse-engineered from final reward.
