# Actual WebClip Bus and archived S1 Shadow evidence re-audit

Date: 2026-11-08. Evidence status: **E1**, not AffectControl E2.

## Previously overlooked real evidence

An earlier S1/Bus join census examined only 202 pseudonymous native-S1
observer events and two sampled Bus messages. It correctly found **zero
validated native S1 ↔ Bus task joins** in those inputs. However, the
existing AgentEval project also contained a separate S1 Shadow task
sidecar, established November 1, with a real WebClip Bus exchange and
an archived independent-of-executor coding test receipt.

This new audit intentionally does NOT call the Shadow sidecar the real
S1 database or claim production scheduling is connected.

## Actual evidence checked in this turn

- Existing local S1 Shadow SQLite sidecar opened read-only.
- One registered, append-only isolated Shadow task, five closed events,
  full event order and hash chain intact.
- One archived WebClip task request, real Sage result, task-token and
  evidence-digest echo, matching reply-to and original thread ID.
- A second read through the **currently connected WebClip Bus** returned
  two actual messages in the original thread: the research request and
  Sage's matching result. Their live returned values were compared to
  the archived metadata.
- A privacy-reduced provider-thread observation was stored **only in
  local gitignored research data**. The original request body was not
  written into this snapshot.
- The archived software-test attestation hash matched the Shadow ledger.
  The historical accepted outcome was a software test result for a
  **pre-existing** code run, not a new automatically dispatched Agent run.

The standalone `benchmarks/existing_s1_shadow_bridge.py` independently
recomputed the sidecar event SHA256 chain and checked cross-file
referential consistency. Actual executed audit result:

| Evidence dimension | Result |
|---|---|
| Real Bus request / result transport correlation | **1 verified against observed provider response** |
| Closed Shadow sidecar events | **5**, hash chain verified |
| Archived software test receipt hash | Matched |
| Native production S1 task ID | **None** |
| Native S1 ↔ Bus task join | **Unverified / false** |
| Actual completion deadline from user | None |
| Affective-versus-urgency scheduling trial | None |

## Material negative finding: current-code re-verification blocked

The archived AgentEval `s1_shadow_trial.py verify` path additionally
checks the **current** RaceLine worktree against the historical frozen
test fixture. The current worktree has subsequent modifications,
including changes to the backend and reader modules; that strict
dynamic re-verification now raises "staged, untracked or unexpected
worktree changes".

This does **not** invalidate a prior real Bus transport exchange or
an append-only Shadow ledger. But it means the historical accepted
software artifact must NOT be described as a successful **current**
full code re-test. The new read-only bridge audits historical
stored evidence only, and reports the present code re-execution as
`not_ascertained_by_this_historical_archive_audit`.

Do not silently clean, reset or overwrite the changed worktree to
make the old verifier pass; doing so would affect user projects and
could destroy intervening changes. An independent new code
acceptance trial requires a separate frozen worktree snapshot.

## What was implemented

The read-only bridge rejects:
- Modified Shadow SQLite chain payload/hash or invalid event order.
- A Bus provider reply with an unexpected parent, sender, thread or
  echoed evidence digest.
- Tampered archived response body or software attestation file.
- Any claim that the historical Shadow task had a live/native S1 ID.
- A provider snapshot falsely labeled as an authenticated WebClip
  observation.
- Unallowlisted/invalid Shadow task identifiers or source database.

Nine portable synthetic fixture tests cover successful artifact
cross-checking and the negative cases. The full research repository
passed **306 local tests** with 33 existing warnings about
uncalibrated reference parameters.

## Trust limits and next integration milestone

A connected Bus API read is real, but the provider observation is NOT
a cryptographically signed external attestation. Historic Shadow
hash chains are tamper-evident under local storage assumptions,
not externally timestamped notarizations. The original Shadow trial
reused an existing software run; no new Sage code-agent task was
created by that experiment.

A complete native S1↔Bus join still needs an **original source
registration recorded before dispatch**, verified native S1 task
identifier, Bus sender authentication, independent role custody,
and source-bound event evidence as in v3. These have not been deployed
to the original S1 task writer or Sage production Bus dispatcher.
For real AffectControl E2 evidence, natural user deadlines,
independent environment outcome checks and a prospective controlled
policy comparison remain missing.

**No production task was dispatched, published, or modified in this
audit. No live S1 database or existing AgentEval worktree was changed.**

## Reproduce (on authorized host)

Call the bridge with: `--shadow-db`, `--trial-dir`,
`--provider-snapshot`, `--shadow-id`, and a new `--out` path.
The provider-thread snapshot is from the connected read-only Bus
operation and is excluded from Git. The original source files are
private and cannot be reproduced from the public repository alone.

Run `uv run --extra dev pytest -q tests/test_existing_s1_shadow_bridge.py`
for source-free fixture validation and
`uv run --extra dev pytest -q` for the full suite.

The bridge's output is create-only; raw source task content and
the real provider transcript stay outside Git.
