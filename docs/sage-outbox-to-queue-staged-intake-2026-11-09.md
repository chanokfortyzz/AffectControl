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

## Follow-up: actual Sage VPS isolated-source execution

After first checking the local copy, the staging module was made
**standalone Python standard library only**, with an atomic,
create-only, mode-0600 evidence writer. No installed AffectControl
runtime is required on the Sage VPS.

A second, actually executed pilot transferred the pinned staging
program into a **single authorized SSH Python process** running on
the real Sage VPS. It read the real VPS Bridge 04 Outbox and 02
queue as inputs and copied their bytes to a PRIVATE temporary
directory with automatic cleanup. It bootstrapped the history,
appended one synthetic S1 request to the private Outbox COPY,
built one non-dispatchable queue-copy card, and then checked the
original production source SHA256 values.

Verified VPS result:

- Actual VPS Outbox baseline read: yes.
- Actual VPS queue used as read-only staging template: yes.
- Historical Outbox task requests replayed: **0**.
- Synthetic new S1 requests staged: **1**.
- Generated card explicitly NOT dispatchable: yes.
- Original remote production Outbox/queue bytes unchanged: yes.
- Private temporary copies removed: yes.
- Actual Sage receiver acknowledgement: **none**.
- Actual WebClip Bus message: **none**.

This shows executable compatibility on the **real host**, not just
on the developer laptop. It does not install a production watcher,
modify OpenClaw services, allocate production authentication keys,
or claim a real receiver accepted an S1 task. Actual task intake,
crash-safe queue fencing and independent outcome/deadline evidence
remain the next controlled integration steps. E1 remains.
