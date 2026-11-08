# Actual S1 Outbox to Sage task queue intake gap: staged repair

Date: 2026-11-09. Research status E1. No production writes.

## Inspected running Sage receiver

The authorized read-only VPS inspection located the live
sage-queue-watch.py in the OpenClaw Sage Router directory.
It observes 02-MAC_TASK_QUEUE.md and wakes the existing queue
router on changes to that file. Its router implementation
sage-local-worker-launch.sh route-queue reads the 02 queue,
while the S1 SageAdapter writes task requests to
04-MAC_OUTBOX.md. Router usage of that Outbox relates to
result reporting, not the demonstrated conversion of a new
Outbox task request into a 02 task card.

The separate task_intake.py is explicitly a read-only shadow
normalizer, not a production S1 request consumer. Although all
three historical S1 requests reached the real VPS Outbox file,
a trustworthy per-task Sage receiver acknowledgement is still
unavailable. We have NOT established that no other remote
component can ever consume Outbox; we established no such
verified path in the inspected live router components.

## Implemented isolated staging adapter

benchmarks/sage_outbox_staged_intake.py creates a safe, optional
Outbox->queue staging flow, without touching live sources.

1. Bootstrap pins the entire pre-existing Outbox bytes and SHA256
   so historical requests are not automatically replayed.
2. The stage operation fails if any original source prefix byte
   changes, the original is truncated, or a source is unsafe.
3. Only newly appended S1 requests with matching header and
   provider task IDs, valid s1_ref, task goal and risk are parsed.
4. Duplicate requests and collisions with existing queue card IDs
   are rejected.
5. The result is a new, private, create-only queue-copy artifact,
   explicitly marked STAGING_NOT_DISPATCHABLE and auto_run=no.
6. The receipt contains SHA256 evidence and aggregate counts,
   with real Sage acceptance, WebClip message ID, human outcome
   and user-origin deadline all NULL.

The private queue copy may contain task goals and must not be
published. It is gitignored. No signed real Sage receiver receipts
were forged.

## Executed pilot on real source copies

Copied actual local Sage Outbox and queue into a new private
gitignored research directory, bootstrapped the existing Outbox,
then appended a single synthetic S1 request to that COPY only.

| Validation | Result |
|---|---|
| Real historical Outbox baseline accepted | Yes |
| Prior requests replayed | 0 |
| New synthetic S1 request staged | 1 |
| New staged card dispatchable | No |
| Original production Outbox hash before/after | Unchanged |
| Original production task queue hash before/after | Unchanged |
| Real Sage receipt | None |
| Real WebClip Bus message | None |

All 13 new portable negative/positive unit tests passed; full
local AffectControl test suite: 359 passed and 33 old warnings
for uncalibrated reference parameters.

## Remaining production integration

This staging adapter is NOT the production receiver.
A real intake service must create new cards atomically under
the existing queue authority rules, persist a nonforgeable
per-task acceptance receipt with original S1 ID, accepted
Sage provider ID and source digest, and handle replay,
duplicates and crash recovery. Actual authenticated Bus message
IDs must only be recorded when real messages exist.

The original deadlines and independently accepted business
outcomes are still unavailable. E2 conditions are not met.
Sage production routing and S1 databases remain unchanged.
