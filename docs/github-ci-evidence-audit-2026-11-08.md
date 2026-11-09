# External GitHub Actions outcome evidence (2026-11-08)

## Purpose and strict evidence boundary

This research-only workflow reads real GitHub-hosted CI checks through
the authenticated `gh api` interface and connects them to their exact
**repository commit SHA**. GitHub executes these tests on its hosted
runners, independently of the researcher's laptop. This is a useful
external *automated check* and a cross-platform regression gate, **NOT**
independently adjudicated acceptance of a real Agent business task.
It provides no user-imposed deadlines and cannot identify a causal
AffectControl scheduling-policy effect. **Research remains E1.**

## Executed API checks

Repository: `chanokfortyzz/AffectControl`; branch:
`research/bitemporal-label-audit-20261108`.

| GitHub run | Commit | Source check outcome | Six-job matrix |
|---|---|---|---|
| [42449990949](https://github.com/chanokfortyzz/AffectControl/actions/runs/42449990949) | `e5e5750deceb3743ee2bf2effd538207b15e736a` | success | 6/6 passed |
| [42450509244](https://github.com/chanokfortyzz/AffectControl/actions/runs/42450509244) | `6d4a433170fec86dbb075fe3eece17beef0097b1` | failure | 4 passed, **2 Windows failed** |
| [42450701463](https://github.com/chanokfortyzz/AffectControl/actions/runs/42450701463) | `b787a52d70a3395efffc92ae71507d2df6b55861` | success | 6/6 passed after fix |

Each run was retrieved from GitHub's live Actions REST endpoints. Every
job name, job status and job commit SHA was checked. All six
OS/Python combinations are required: macOS, Ubuntu, Windows × Python
3.10 and 3.12.

**Root cause of the failed run**: one PWA audit test generated an SWF
fixture using `Path.write_text()`, which translated LF to CRLF on
Windows, while calculating the expected SHA256 over UTF-8 LF bytes.
Commit `b787a52` changed the fixture to `write_bytes()` so the
expected hash matches bytes actually written on any OS. This was
verified with the next complete GitHub CI runs above. The original
real PWA source file hashes and numeric results were not modified.

## Validation guarantees and limitations

`benchmarks/github_ci_evidence.py` retrieves **only** run and
per-job metadata. It checks exact repository, branch, event, complete
40-character source commit SHA, run ID, canonical GitHub URLs,
job IDs, timestamps, duplicate jobs, six-platform matrix, completed
states and every job conclusion. A single failed job prevents a pass.
An in-progress run is **pending**, never prematurely successful.

For local research integrity, each source API response receives a
SHA256 digest and the aggregate report is written create-only under
gitignored `.research-data/ci-evidence-20261108/`. Raw job logs,
personal credentials, GitHub token, repository secrets and task
message bodies are **not** stored or published. Source GitHub API
response digests do not constitute a cryptographic signature of
execution, and metadata could subsequently change (e.g. a rerun).

The API evidence is **not** joined to a specific local
`capture_execution` receipt: those local subprocess receipts lack
a guaranteed repository-commit measurement at capture time, and a
passing repository CI does not prove that an unrelated task achieved
its requested business goal. The report therefore keeps:

- `automated_ci_outcome`: verified repository test result as
  reported by the GitHub Actions API.
- `independent_human_task_acceptance`: **null**.
- `natural_user_deadlines`: **null**.
- `causal_agent_scheduler_effect`: **null**.

Only commit-linked automated-test evidence is established.

## Reproduce from GitHub

With a read-only GitHub CLI authorization:

```bash
uv run --extra dev python -m benchmarks.github_ci_evidence \
  --run-id 42449990949 \
  --expected-sha e5e5750deceb3743ee2bf2effd538207b15e736a \
  --out .research-data/ci-evidence-20261108/recheck-pass.json

uv run --extra dev python -m benchmarks.github_ci_evidence \
  --run-id 42450509244 \
  --expected-sha 6d4a433170fec86dbb075fe3eece17beef0097b1 \
  --out .research-data/ci-evidence-20261108/recheck-fail.json

uv run --extra dev pytest -q tests/test_github_ci_evidence.py
uv run --extra dev pytest -q
```

Use new output filenames: this collector rejects overwrites. Tests use
authored API-shaped metadata only; **live API retrieval** was separately
performed for the real runs listed above.

## Scientific next gate

A separate source must link a **specific user-origin request** to its
precommitted natural deadline, evidence of task arrival and execution,
the exact external acceptance criterion and a genuinely independent
completion adjudication. Then freeze intervention allocation and a
lineage-aware analysis protocol. GitHub CI, regardless of 6/6 passing,
must not substitute for this experiment.
