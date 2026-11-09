# External historical workload reality check: KTH and Cornell CTC

**Completed:** 2026-11-08 · **Status:** External arrival-metadata evidence, **NOT AffectControl E2 effectiveness evidence**.

## Why

The `override_risk` forecast assumes no future arrivals after an
explicit user interruption. The earlier 1,536-scenario authored
stress-test showed that a synthetic later arrival could break the
incremental-deadline-miss prediction. Its frequency in *actual*
workload traces remained untested. This separate audit evaluates
**empirical future-arrival frequency** without importing any
synthetic user deadlines or inventing missing acceptance labels.

## Provenance

These are **historical HPC cluster jobs, not Agent actions**.

- Original archival project: [Parallel Workloads Archive](https://www.cs.huji.ac.il/labs/parallel/workload/).
- Dataset copies: [public GitHub mirror](https://github.com/ihfaz297/cpu-scheduling-fairness-survey), pinned commit
  `b9362a40bf5c0f86788a7b1411ec1c3dea9a92d9`.
- KTH source file: `KTH-SP2.swf`,
  SHA256 `fba36494c4e4257f72182e8b629ebb0bcb054b3b82851ef957445bd627adcc87`.
  Source header: IBM SP2, Swedish Royal Institute of Technology
  (KTH), Sep 1996–Aug 1997; cleaned copy.
- CTC source file: `CTC-SP2.swf`,
  SHA256 `d078f9517bafcf37602482abe99e0b2e1c1867e3ce7748df8acc50364847bccf`.
  Source header: IBM SP2, Cornell Theory Center, Jun 1996–May 1997;
  cleaned copy.
- Raw files reside **only in gitignored local research data**.
  They are not uploaded, republished or included in commits.
- Files match their pinned checksums. This is **NOT** an independent
  byte-for-byte verification against the original archive, whose
  direct addresses were not available at the attempted URLs.

The [SWF 2.2](https://www.cs.huji.ac.il/labs/parallel/workload/swf.html)
format contains 18 columns per job. This audit treats **column 2
as observed submit time**, **column 4 as run-time duration**, and
**column 9 as requested run-time/resource limit**, *not* a task
completion deadline. User IDs, job contents and queue-specific
private labels are not exported.

## Actually observed input-data quality

| Metric | KTH-SP2 | CTC-SP2 |
|---|---:|---:|
| Raw SWF job rows | 28,476 | 77,123 |
| Valid nonnegative submit time and positive runtime | 28,468 | 77,106 |
| Invalid or missing times excluded (never imputed) | 8 | 17 |
| Median actual job runtime | 847 s | 1,113 s |
| Median inter-submission gap | 193 s | 85 s |
| Simultaneous next-job gaps (timestamp precision = seconds) | 332 | 501 |

Numbers describe only these cleaned, dated source logs.
Jobs within the same system share queues, policy and users and must
**not** be treated as statistically independent Agent episodes.

## Future-arrival frequencies

For each adjacent pair of valid, chronologically sorted job submission
timestamps, calculate the observed time gap. The **event-origin**
fraction counts the proportion of existing job submissions followed
by another within the stated horizon. A second **uniform-time**
fraction counts the time coverage during which a uniformly sampled
instant within the observed trace window would be followed by an
arrival within that horizon, using `sum(min(horizon, gap)) / total span`.

| Horizon | KTH: at job submission | CTC: at job submission | KTH: at random time | CTC: at random time |
|---|---:|---:|---:|---:|
| 1 s | 3.09% | 7.85% | 0.10% | 0.27% |
| 5 s | 7.84% | 18.03% | 0.47% | 1.20% |
| 10 s | 11.55% | 24.18% | 0.92% | 2.26% |
| 30 s | 21.75% | 35.06% | 2.57% | 5.98% |
| 60 s | 30.59% | 44.27% | 4.76% | 10.80% |
| 300 s | 59.11% | 74.42% | 17.26% | 34.66% |

The sharp gap between the two reference origins is evidence that
**sampling position matters**. Arrivals are temporally clustered
around existing arrivals. Neither event-origin nor uniform-time
sampling necessarily matches the instant at which an Agent user sends
an actual explicit override. We therefore do **not** call these
numbers the real Agent arrival probability.

## Scientific implications and remaining gaps

1. The universal "no future arrivals" assumption should not be used
   silently in a risk prediction for arbitrary tasks. The observed
   historical job streams provide a non-synthetic counterexample to
   the idea of isolated task arrivals.
2. HPC jobs execute on many processors and were scheduled under
   external HPC policies, not a single preemptive Agent worker.
   Thus we cannot insert their measured runtime values into
   AffectControl's one-resource simulator and call the outcome
   externally valid.
3. SWF requested-runtime limits are **walltime/resource constraints**,
   **not user completion deadlines**. This audit does not produce
   authentic customer-deadline data or a human override preference.
4. A single observed historic policy cannot identify what a
   different policy would have achieved, let alone a causal
   incremental deadline-miss effect. There is no independent Agent
   acceptance oracle or proper intervention randomization.
5. The two systems and cleaned log files are a narrow, old,
   selected sample. Do not draw conclusions about current workload
   mix, all HPC systems, or today's Agent products.

**Conclusion:** we have externally sourced empirical evidence for
the *existence and distribution of future arrivals* in two real
historical job streams, not for AffectControl scheduling benefit.
The research evidence level remains **E1**.

## Reproduction and review

Download both pinned files from the pinned public commit into
`.research-data/pwa-real-arrival-20261108/` and verify the
two SHA256 digests above. Then run:

```bash
uv run --extra dev python -m benchmarks.pwa_arrival_audit \
  --root .research-data/pwa-real-arrival-20261108 \
  --out .research-data/pwa-real-arrival-20261108/arrival-audit-v2.json

uv run --extra dev pytest -q tests/test_pwa_arrival_audit.py
uv run --extra dev pytest -q
```

The tool refuses overwrites, checks the exact source hashes,
validates format/version and numeric fields, excludes invalid
runtime/submission records and emits only aggregate statistics.
No raw task records are committed to Git.
