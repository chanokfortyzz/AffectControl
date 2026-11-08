# S1 pseudonymous shadow observation audit — 2026-11-08

This is an **executed offline audit of real S1 observation metadata**, not
an AffectControl scheduling intervention or proof of causal benefit.

## Real source

- Reader: `agent-eval/adaptive/s1_watch/changes.pseudonymous.jsonl`
  from the pre-existing, read-only S1 SQLite watcher on the user's Mac.
- Source SHA256:
  `7f3407b3efa452bf740b4cb077c27bbf32261b57119d6dd725aaf4b555987174`
- 202 pseudonymized first-seen rows, 202 unique event IDs, 17 distinct
  trace IDs, no duplicate appends or changed-metadata rows in this snapshot.
- The 202 source entries were captured between 2026-11-01 and 2026-11-03.
  The separate watcher health file `s1_watch/latest.json` was updated
  at 2026-11-08 04:34:23 UTC and showed 202 observed records, zero new
  or changed records during that poll.
- No raw S1 database, task text, credentials, source trace IDs, tool
  arguments or original private JSONL logs are committed here.

The `s1_shadow_audit.py` analyzer fails closed on unknown fields,
untrusted source schema, duplicate event IDs with altered metadata,
backdated amendments, timestamp-naive rows and changed lineage IDs.
It reports only aggregate counts and time intervals.

## Results

| Observation | Result |
|---|---:|
| Source rows | 202 |
| Unique source event IDs | 202 |
| Distinct pseudonymous trace IDs | 17 |
| Traces with exactly one `task_started` and one `task_terminal_reported` | 6 |
| Traces with ambiguous multiple start or terminal events | 2 |
| Traces missing a unique start/terminal pair | 9 |
| Backward-time paired traces | 0 |
| Source events missing event timestamp | 1 |
| Source events timestamped after their capture | 0 |
| Self-reported `verified_acceptance=true` events | 0 |
| Independently audited task acceptance | **unavailable** |
| Observed active execution time | **unavailable** |
| Observed task deadlines | **unavailable** |

The **six matched start/end spans** (seconds) were
142, 374, 387, 451, 540 and 14,546; median **419 s**.
They are **elapsed status-event intervals**, not measured task
processing durations. The longest interval is over four hours and may
include idle time, delayed reporting, queued work, retries or pauses.
Do not infer CPU occupancy, a calibrated scheduler duration or
deadline compliance from these spans.

The watcher health also explicitly reports:
`bus_sage_join_established=false`,
`independent_acceptance_available=false` and
`auto_dispatches=0`. This is a useful negative audit result;
no production scheduler was modified.

## Reproduce without copying private raw events

```bash
uv run --extra dev python -m benchmarks.s1_shadow_audit \
  --input /Users/chenzhiliang/coding-service/agent-eval/adaptive/s1_watch/changes.pseudonymous.jsonl \
  --out .research-data/s1-audit-20261108/another-audit.json

uv run --extra dev pytest -q tests/test_s1_shadow_audit.py
```

Output is aggregated JSON and excluded from Git. Use a **new**
filename if one exists: the CLI refuses overwriting summary output.

## Scientific interpretation

This is direct evidence of *metadata availability and annotation
gaps*, not independent third-party verification of S1 operations.
Source fingerprints cannot be independently recreated from the
redacted metadata alone. No success labels, independent intervention
judgments, active work durations or real user-provided deadlines are
available from this source. Even the 17 trace IDs may be dependent
sessions under a shared project. Do not promote these 202 source events
to 202 independent experimental units or to evidence level E2.

**Next credible step:** instrument *prospective* real tasks with
explicit task lineage, actual task queue arrival, task run/pause/resume,
preemptibility, measured active duration, real deadline origin, and
independent externally verified completion. Capture a priori assigned
urgent/normal workload cases, and keep the production controller
separate until tests and safety review complete.
