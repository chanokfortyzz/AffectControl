# Source-bound test receipts for isolated Sage task intake

Date: 2026-11-09. Evidence level E1. Sage production dispatch,
native S1 database, WebClip Bus and provider credentials remain unchanged.

## Why this change was needed

The isolated receiver was crash-recoverable but a task from its
historical Outbox baseline could be replayed later with a changed
timestamp and accepted again, if it was absent from the copied
queue and no longer in the post-baseline ledger. The new private
receiver indexes SHA256 digests of historical native S1 refs and
suggested Sage provider IDs. Reuse of EITHER previously observed
identity is rejected. Actual raw user task IDs are not written
to the state or research report.

The prior state transition did not create independently verifiable
per-task evidence. The new lab signer checks committed staging
state SHA256, staged queue SHA256, exact source Outbox prefix,
original source byte-range hashes, original task entry digests,
matching original native/provider IDs, and the non-dispatchable
queue-card fields. A per-task receipt includes those source-bound
claims and a test-only HMAC-SHA256 value.

The receipt explicitly declares:
- private_staging_card_committed_not_dispatched
- production_sage_intake_signed: false
- real WebClip Bus message: null
- independently verified business acceptance: null

A 32-byte random lab key is supplied via a private file. The
signer and verifier execute as separate processes. The verifier
reconstructs every original claim from source, state and queue
and compares MACs in constant time. Any source, state, queue,
receipt or task-guard tampering fails closed. It refuses to
sign while a durable staging transaction remains pending.
No actual Sage production credentials or signing service are used.

## Real Sage VPS private execution

A private temporary directory on the authorized actual Sage
VPS copied the 04 Outbox and 02 queue byte-for-byte. All
historical requests were ignored; two synthetic new S1 requests
were appended to the private copy only. They became two
non-dispatchable private queue cards.

One subprocess issued the two lab receipts, a second subprocess
independently recomputed the source and verified both. A
deliberately forged claim of real Sage acceptance failed
signature verification. The original VPS Outbox and queue file
SHA256 values were unchanged. The random test key, code copies,
staging files and test receipts were cleaned up automatically.

Observed counts:
- 2 synthetic private tasks staged, both source-bound receipts verified
- 1 forged real-acceptance claim rejected
- 0 historic user requests replayed
- 0 actual Sage production tasks dispatched
- 0 real Sage authenticated task-intake receipts
- 0 actual WebClip Bus events

Source-free tests also cover historical ID replays, rejected
signatures with wrong keys, missing/changed source bytes,
tampered staging guard, pending transaction, replay into a
different staging state, duplicate signature file and
test key permissions.

## What this test cannot prove

HMAC is symmetric: anyone able to verify a MAC using the
test secret could also sign a fake receipt. The two lab
processes share a key controlled by the same test operator.
This is NOT independent Sage receiver identity, key custody,
externally verifiable task acceptance, or actual Bus attribution.

For production, a separately authorized Sage receiver must
sign ONLY after real intake and atomic queue admission; a
publicly verifiable asymmetric signature or appropriately
separated trust model should let auditors verify without
holding production signing authority. A production receipt
must bind the actual original request, receiver actor, source
time and accepted task ID. Any real Bus message ID must come
from the authenticated Bus source, not from the proposed
Sage provider task ID.

The lab receipt binds to the CURRENT committed queue/state
hash. Later staging commits change this hash. Long-term
historical validation will need frozen source snapshots
and independent notarization or another authenticated store.

There are still no original user-specified deadlines, human
outcome acceptance or real controlled AffectControl policy
interventions. Remain E1; PR stays draft.

## Reproduce

Run the source-free tests:
  uv run --extra dev pytest -q tests/test_sage_outbox_durable_stage.py
  uv run --extra dev pytest -q tests/test_sage_intake_receipt_lab.py
  uv run --extra dev pytest -q

The independent receipt CLI supports issue and verify with
explicit --root, --source, --test-key-file, and --receipt.
Never use production credentials or a live Sage queue path
with this research-only signer.
