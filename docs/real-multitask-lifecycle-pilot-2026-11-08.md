# Real two-task cooperative lifecycle pilot — 2026-11-08

## Executed work

This audit actually ran test commands as separate local subprocesses
under an **isolated research controller**, without changing the
AffectControl scheduler, Sage, S1, Bus or any production jobs.

The controller interleaved two work units:
1. Task A `start` → run `tests/test_core.py` → `pause`.
2. Task B `start` → run `tests/test_scheduler.py` → `finish`.
3. Task A `resume` → run `tests/test_workloads.py` → `finish`.
4. Run `tests/test_core.py` in a **separate** local check process
   and record Task A's `check` event.

The workflow order was chosen manually as part of the pilot. These
are research test commands, not sampled real-world competing Agent
missions and not an urgency-vs-affective randomized comparison.

## Actual local observations

| Measure | Task A | Task B |
|---|---:|---:|
| Lifecycle events | 5 | 2 |
| Controlled work phases | 2 | 1 |
| Controller pause events | 1 | 0 |
| Controller-observed running interval | 1.860 s | 0.493 s |
| Controller-observed paused interval | 0.494 s | 0.000 s |
| Subprocess phases exiting with code 0 | 2 | 1 |
| Separate local check exiting with code 0 | 1 | 0 |
| External independent task acceptance | unavailable | unavailable |
| Final event-chain SHA256 | `6311170de2fbad7defb074d23e8d2f77e3b40b8037d268923c891e9ce7aee7ec` | `224dc070248940bf22f86060ced7f5be44e59f89fbb816d1f1c622683dca7ca8` |

The observations are not CPU utilization or true *active model work*
time. The controller's running intervals include process startup,
blocking, I/O, and hash/receipt writes. Paused interval reflects
controller-instrumented time between A's pause and A's resume; no
live Agent process was forcibly suspended. Exit code 0 does not
establish human-judged acceptance.

## Source and verification

The new `benchmarks.task_lifecycle` records an append-only,
event-hash-chained ledger, with strictly checked task lineage,
transition order, monotonic clock, and unique phase receipt IDs.
Each `pause`, `finish`, `fail`, or `check` references the hash of
a **real process receipt** created by `capture_execution.py`.
The reader verifies that hash and task lineage before calculating
time spans and separately reports local subprocess checks.

Both ledgers and all raw receipts are local and excluded by
`.research-data/` from Git; the repository contains the
reproducible instrumentation and tests but not private process
payloads. The aggregate report intentionally omits real task IDs.
The hash chain detects accidental tampering and is **not**
provider-signed independent attestation. Concurrent appends are not
transactional in this prototype; restrict to one authorized
controller per task.

CI/unit coverage includes contradictory transitions, replayed receipt,
altered hash, wrong lineage, missing receipt, nonzero result wrongly
marked as successful, symlinked ledger path and incomplete sessions.
A missing `finish` or `fail` is censored; no duration
estimate is emitted for unfinished tasks.

## Reproduction and research boundary

Tests from the research branch:

```bash
uv run --extra dev pytest -q tests/test_task_lifecycle.py
uv run --extra dev pytest -q
```

The root is `<repo>/.research-data/lifecycle-pilot-20261108`,
with `lifecycles/<opaque-task-id>.jsonl` and
`receipts/<opaque-phase-id>.json`. Use the public module
`benchmarks.task_lifecycle.append` to append transitions after
successfully capturing each phase with
`benchmarks.capture_execution.capture`. This must remain an
explicit opt-in local research action, not a production timer.

This pilot demonstrates that actual executed test tasks can be
interleaved and **audited without confusing a local check with
independent acceptance**. It provides zero evidence that
AffectControl improves throughput, deadline compliance or user
interruption satisfaction. No real task deadline was available.
Research evidence stays at **E1**.

The next scientifically meaningful step is a consented, prospective
set of multiple independent real tasks with verified arrival,
suspension, completion, externally fixed deadlines and independent
outcome judgments. Freeze the comparison protocol before observing
task outcomes; only then study real control-policy effects.
