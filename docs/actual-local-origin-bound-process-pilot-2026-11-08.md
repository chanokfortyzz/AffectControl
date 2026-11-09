# Real local subprocess, origin-bound staged source events

Date: November 8, 2026. Status: executed isolated research pilot.
**AffectControl remains E1.**

## Why this is materially different from signing fabricated old records

The earlier origin-bound v3 join protocol rejected retrospective
attribution, but its positive examples were synthetic in-memory
source records. This pilot runs a *real* non-destructive local
unit-test subprocess and writes an intake registration **before**
starting that process. The observed subprocess receipt is hashed
and included in two independently readable, immutable staging
event records, with the same registered correlation token and
request digest in the event records themselves.

The script is benchmarks/prospective_origin_lab.py.
It is opt-in, has a fixed allowlisted test command, captures the
child process through the existing non-shell local execution
collector, writes evidence create-only, and then performs a
separate read-only verification pass over the local files.

## Exact event sequence

1. Pre-run intake records a randomly generated 256-bit task token,
   SHA256 of a fixed research task intent, actual Git HEAD commit,
   immutable SHA256 of the runner script, and UTC issue time.
2. One real subprocess runs the existing repository core tests:
   Python -m pytest -q tests/test_core.py. The observation collector
   records wallclock process time, return code and output digests.
   It does not persist raw stdout/stderr or the command arguments.
3. The staging S1-format record stores the intake token/digest
   and digest of the actual captured process receipt.
4. The staging Bus-format record stores the same intake
   token/digest and process receipt hash, as a separate source row.
5. The local pilot signs intake, S1 and Bus source rows with
   three different **test-only** HMAC secrets, binding all event
   contents under the v3 protocol.
6. A separate call of the verifier reads the source files,
   immutable process receipt, task registration, original runner
   source digest, and source signatures, rechecking each link.
7. Missing keys, source-row mutation, registration changes,
   process-receipt mutation, or proof tampering fail verification.

## Outcome and scientific interpretation

The initial pre-commit engineering dry run actually executed one
subprocess and demonstrated one verified join of the two *staged
source-format records*. After source code is committed, a new,
create-only and source-pinned run is needed for the reference
result. **No genuine Sage Bus or S1 production event was created.**

The local controller currently holds ALL three **test-only**
signing secrets in a single ignored evidence directory. Therefore,
the roles are only logically separated and cannot establish
independent key custody or genuine source identity under an
adversarial compromise. The staged Bus event's actor flag records
the local test reporter, NOT authentication by the real Bus.

The process return code verifies only a local unit-test run.
There is no true user task deadline, external user outcome, verified
real Agent acceptance, real scheduler preemption, or causal policy
comparison. The output explicitly leaves these fields null.
**Do not report the one staged join as a production S1–Bus join.**

Raw local pilot files including test-only secret keys are stored
under the repo's gitignored .research-data directory. No keys,
private conversation content, raw model outputs or original
S1/Bus database records are committed to Git.

## Reproduce

From the research repo, with uv and pytest available:

    uv run --extra dev python -m benchmarks.prospective_origin_lab run \
      --root .research-data/origin-bound-pilot-new-id

    uv run --extra dev python -m benchmarks.prospective_origin_lab verify \
      --root .research-data/origin-bound-pilot-new-id

    uv run --extra dev pytest -q tests/test_prospective_origin_lab.py
    uv run --extra dev pytest -q

The root must not exist before the run. Every execution uses a new
ID; a failed/incomplete run is not silently replaced. Verification
requires checkout of the original runner source version, or it
will reject the source digest.

## Next real evidence gate

A trusted intake, live S1 writer and live Bus writer must each be
modified through separately reviewed integration with distinct
trusted key custody and actual actor verification. Those changes
are NOT performed in this research-only pilot. An independent
read-only verifier will then be able to assess real source events,
followed by human-approved task acceptance and real deadlines.

This pilot is an executable integration demonstration, not a
production deployment or an AffectControl performance result.
