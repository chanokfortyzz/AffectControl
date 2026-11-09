# Bitemporal label audit for research (2026-11-08)

## Why

A later correction or revocation of an appraisal/interruption label must not
quietly change what was *known* when a frozen benchmark was first evaluated.
A single `active: false` flag loses this history and can create hindsight leakage.

We record **valid_at** (when an adjudication applies to a case) separately from
**recorded_at** (when that adjudication entered the research log). History is
append-only. An `assign` event has a binary `label`; a `revoke` has **no**
label and means unadjudicated, not negative. Later reassignment/correction at
the same `valid_at` has a later `recorded_at`.

This is an audit of labels, **not** a model that proves any Agent scheduling
advantage or authorizes an action. It does not modify the runtime.

## Input

`events.jsonl` (append in nondecreasing recorded time):

```jsonl
{"event_id":"e1","sample_id":"case-a","kind":"assign","label":1,"valid_at":"2026-10-01T09:00:00Z","recorded_at":"2026-10-01T10:00:00Z"}
{"event_id":"e2","sample_id":"case-a","kind":"revoke","valid_at":"2026-10-01T09:00:00Z","recorded_at":"2026-10-05T12:00:00Z"}
```

`cases.jsonl`:

```jsonl
{"sample_id":"case-a","observed_at":"2026-10-01T09:00:00Z"}
```

Run:

```bash
python -m benchmarks.temporal_label_audit --events events.jsonl --cases cases.jsonl \
  --frozen-at 2026-10-04T00:00:00Z --reviewed-at 2026-10-06T00:00:00Z
```

`n_changed` counts differing binary values **and** assignments turning
unknown or vice versa; `n_missing_*` preserves abstentions. Raw case IDs
should be pseudonymous before release. Query both the effective time of a
case and the knowledge cutoff. Do **not** call the final review “ground truth”
without independent adjudication.

## Next evidence gate

1. Establish a consented or public real-trajectory sample with lineage IDs.
2. Freeze labels, sources, and adjudicator protocol before seeing model scores.
3. Run this audit on real revision history. Verify the evidence source and
   artifact-level completion independently.
4. Only then run a prospective paired comparison against urgency-only with
   session-level inference. Replay alone cannot identify effects of unchosen
   actions; require known randomized action probabilities or controlled runs.

The tests use authored illustrative events, not externally validated data.
