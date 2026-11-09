# Real-process observation pilot (2026-11-08)

## Summary

This is a genuinely executed **single local subprocess**, not another
fabricated task duration. It demonstrates reliable collection of a
privacy-reduced wall-clock receipt. It does *not* validate scheduling
interventions or advance evidence level beyond E1.

On 2026-11-08 UTC, executed (opt-in, read-only test operation):

```bash
uv run --extra dev pytest -q tests/test_core.py
```

Source: local AffectControl repository, using the standalone collector
`benchmarks.capture_execution`. It recorded:

| Measure | Observed |
|---|---|
| Session ID | `affectcontrol-core-tests-20261108` |
| Lineage ID | `affectcontrol-main` |
| Wall-clock duration | **1.494701375 s** |
| Exit status | **0 (exited)** |
| Captured stdout size | **2,577 bytes** |
| Captured stderr size | **0 bytes** |
| Deadline basis | **none** |
| Duration basis | **wallclock_proxy** |
| Ground-truth adjudication | **none** |
| Trace SHA256 | `704b412d550bfe486320f3139ce2bbf24ebe7ffd0ca0333ed2e1e0f4dc27164f` |

The original stdout/stderr was **not saved**; only output SHA256 and
byte counts are retained. Original command arguments and environment
are not stored. Raw receipt/trace and manifest are local, excluded from
Git, under `.research-data/live-observations-20261108/`. Do not
publish raw logs or credentials when using the collector on other tasks.

## Reproducible collection

Run an explicitly authorized and harmless command, giving a *new*
opaque session identifier each time:

```bash
uv run --extra dev python -m benchmarks.capture_execution \
  --root .research-data/live-observations-20261108 \
  --session-id example-002 \
  --lineage-id affectcontrol-main \
  --cwd /path/to/AffectControl \
  --timeout-s 120 -- python -m pytest -q tests/test_core.py

uv run --extra dev python -m benchmarks.observation_manifest \
  --root .research-data/live-observations-20261108 \
  --out .research-data/live-observations-20261108/manifest-v2.jsonl
```

The collection uses `subprocess.run(..., shell=False)`, monotonic
elapsed time, create-only evidence files and session reservations to
avoid duplicate reruns. It blocks symlink redirection of the evidence
directories, hashes output without persisting its contents, and records
the subprocess exit code. Process launch errors and timeouts are
**censored** from the usable completion-duration manifest. It never
converts success/failure exit status into an independently labeled
human interruption preference. A new collection is a new observation.

This pilot has **one lineage** and no real deadline; the cohort gate
correctly refuses to use it to form train/validation/test, and paired
scheduler replay rejects the proxy/no-deadline condition.

## Existing Agent evaluation run-summary audit (separate project)

The local `agent-eval` project has three task-matched B2/B3 run pairs
(six runs) in two private, locally stored `paired-results.jsonl`
files. An audit was executed *without* exporting underlying messages.
In the existing project README, B2 denotes one execution agent,
whereas B3 adds planning/implementation/QA separation. These are
**not** AffectControl scheduler interventions.

| Descriptive measure | B2 | B3 |
|---|---:|---:|
| Run count | 3 | 3 |
| Reported test passed | 3 | 2 |
| Reported complete workflow | 2 | 0 |
| Mean wall-clock duration | 39.176 s | 84.556 s |
| Mean API cost (USD) | 0.340762 | 0.606942 |

The paired B3-minus-B2 wall-time difference averages **+45.38 s**
across three paired tasks. This is exploratory, with no confidence
interval or causal interpretation. The per-run `verified_by` field
says `independent_tests`, but this is a *claim in the source file*,
not independently established by the present audit. "Tests passed"
and "workflow complete" disagree on some rows and must not be merged.

The two source file SHA256 digests in the private audit report allow
later rechecking for tampering; only aggregated numbers are recorded
here. Different task families, models and data sources must not be
confounded with the AffectControl hypothesis.

## E2 gate remaining

Independent real scheduling sessions need *observed* deadlines,
actual preemptibility, task arrival/interruption timestamps,
measured active work (not a wall-clock proxy), independent outcome
verification, positive **and** negative intervention labels, and
prospective allocation/selection rules. The test set, calibration
and primary endpoint must be locked before looking at test outcomes.
Until then, keep the project at **E1**.
