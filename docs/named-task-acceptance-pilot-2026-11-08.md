# Named-task independent-machine acceptance pilot — 2026-11-08

## Purpose

Move from repository-wide CI status to explicit, **task-scoped machine
verification**, while refusing to call CI a human independent task oracle.
This is research instrumentation under PR #1, NOT production scheduling.

## Task acceptance contract (frozen before remote execution)

The exact test selectors and task purposes are versioned in
`benchmarks/task_acceptance_spec.json`.

1. `override-contract`: the actual user-immediate event reaches the
   scheduler; nonpreemptible work remains protected; metadata spoofing
   cannot grant the explicit hard override. Three existing targeted tests.
2. `swf-byte-integrity`: exact-source-byte SWF parsing is cross-platform,
   and a forged SHA256 checksum is rejected. Two existing targeted tests.

These are **research code maintenance tasks**, not independent projects or
a sampled portfolio of real Agent workloads. They intentionally have **no
user-provided completion deadline**. The automated pass criterion for
each case is all frozen pytest selectors passing with exit status zero,
not a model-generated grade or a user's business acceptance.

## Execution and evidence

`.github/workflows/task-acceptance.yml` runs the two cases on
GitHub-hosted Ubuntu and Windows Python 3.12. The workflow checks out
the PR's actual head revision; no external runner may silently execute
a different commit. Each case generates:

- `receipt.json`: case name, exact commit SHA, entire contract SHA256,
  frozen pytest selector names, exit status, JUnit SHA256, count of
  passed/failed/skipped tests, and provenance from the GitHub run ID.
- `results.xml`: JUnit output from actually executing those selectors.

The GitHub Actions artifact upload preserves these files for 14 days.
The local `verify` command checks the frozen test selectors, receipt
source commit, contract hash and JUnit bytes and refuses a pass if the
counts, exit status or evidence disagree. Source response hashes alone
do not authenticate an arbitrary artifact: to claim external execution,
also independently check the GitHub run/job statuses and artifact
source through the GitHub Actions API.

The workflow grants only read access to repo contents; there are no
external writes beyond the build artifact and no use of credentials
in the subprocess test runner. Raw stdout and stderr are hashed but
not persisted; original test evidence XML is restricted to the frozen
code's selected tests. A custom command cannot be supplied through
the acceptance CLI.

## Local preflight (prior to remote runs)

- `override-contract`: 3/3 local test checks passed.
- `swf-byte-integrity`: 2/2 local test checks passed.
- The new runner's eight tests passed, including corrupted JUnit,
  forged claim, wrong revision, unauthorized case and contract drift.
- Full suite at this stage: **238 tests passed**, with 33 existing
  uncalibrated-reference warnings.

These local checks are not yet independent-host execution. The GitHub
run and downloadable artifacts must be checked separately after
pushing the committed workflow. This document records that explicit
sequence rather than retroactively describing local tests as external.

## Reproduction

```bash
uv run --extra dev python -m benchmarks.task_acceptance run \
  --case override-contract \
  --out .research-data/task-acceptance/demo-override

uv run --extra dev python -m benchmarks.task_acceptance verify \
  --receipt .research-data/task-acceptance/demo-override/receipt.json \
  --junit .research-data/task-acceptance/demo-override/results.xml \
  --expected-sha "$(git rev-parse HEAD)"
```

Use a new output folder for every experiment. Never change the
contract after inspecting a failed run and call the revision a
prospective preregistration. New contract versions and edits must be
explicitly linked and labeled.

## Evidence boundary

This advances only to a **named research-task automated oracle**
running outside the research laptop. It still lacks a trusted
user-origin task request, a real user deadline, multiple independent
Agent work lineages, and a human/external business-level acceptance
criterion. It does not evaluate affective versus urgency-only
scheduling and does not demonstrate a causal policy effect.

**AffectControl remains E1, not E2.**

## Cross-platform receipt validation finding and v2 correction

The first committed remote workflow (head `b473c97`, GitHub run
[42451320693](https://github.com/chanokfortyzz/AffectControl/actions/runs/42451320693))
successfully ran all four Ubuntu/Windows task checks. However,
downloading and verifying the actual JUnit + receipt archives on the
Mac gave the following *distinct* evidence result:

- Ubuntu override-contract: 3/3 and receipt verification passed.
- Ubuntu swf-byte-integrity: 2/2 and receipt verification passed.
- Windows receipts: the original v1 raw-file contract SHA256 did not
  match the Unix-checkout JSON bytes, despite the Windows CI tests
  succeeding. The original Windows receipts therefore **failed the
  cross-host artifact verifier**, and cannot be retroactively marked as
  verified under v1.

The cause is Git's platform-dependent LF/CRLF text conversion when
checking out the JSON contract. A frozen *semantic JSON contract* is
not a frozen byte-for-byte checked-out text file.

**Corrective v2:** The acceptance receipt schema is now
`affectcontrol-named-task-machine-check-v2`. Its contract digest is
computed from sorted-key, compact UTF-8 canonical JSON, not the
locally checked-out text bytes. A new regression test proves LF and
CRLF copies yield the same semantic digest, while another test
rejects old v1 receipts under v2. No test selectors, acceptance
criteria, policy weights, deadlines, or task outcomes were changed.

This is a **post-run evidence-format repair** and must produce new
remote artifacts before claiming cross-platform receipt integrity.
Neither v1 nor v2 can establish independent human task completion.
