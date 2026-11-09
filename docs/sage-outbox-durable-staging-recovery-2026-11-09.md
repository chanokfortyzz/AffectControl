# Crash-safe durable S1 Outbox staging receiver — actual executed evidence

Date: 2026-11-09. Research only. AffectControl E1.
Sage production dispatch and native S1 database were NOT modified.

## Concrete problem and implemented solution

The prior source conversion could stage a task card once, but
did not maintain persistent committed state. An interruption
between writing a queue card and recording its processed ID
could cause a duplicate on process restart.

New standalone staging receiver:

    benchmarks/sage_outbox_durable_stage.py

It uses only Python standard-library functions and the existing
standalone Outbox parser. It operates on a private staging root,
not on the live Sage queue or task dispatcher.

### Durable state transition

- Bootstrap saves a complete immutable-hash Outbox prefix as the
  high-water mark: historical requests are never replayed.
- Incremental processing checks that the entire prior source
  prefix remains unchanged and the new suffix ends in a newline.
  Suspicious S1 headings with unfinished/malformed type are
  **rejected without checkpoint advancement**.
- Validated new requests must have unique proposed Sage ID,
  unique original S1 ref and no collision against existing
  staged queue cards or the prior committed request ledger.
- A private, durable pending transaction journal records
  the exact old state/queue hashes, fully rendered new queue
  and the next state. Writes are fsynced and use create-only
  files. Queue and state are replaced atomically, one at a time.
- On the next invocation, the receiver finds any pending
  transaction, reconciles the old/new hashes and finishes
  that same transaction. It does NOT reinterpret or reissue
  the original task. If a temporary file was cut short during
  writing, it is rebuilt only from the already persisted
  private journal. Unexpected changes to committed queue
  or state fail closed.
- OS-level advisory file locks prevent two receiver processes
  from concurrently handling a private staging root. The OS
  releases a lock when a process exits.
- Committed state retains only task-ID hashes, native-ref hashes,
  source-entry hashes, the queue hash and cursor; original
  goal text exists only in the private queue copy or pending
  journal, never in public report output.

All new cards contain:
STAGING_NOT_DISPATCHABLE; auto_run=no;
requires_user_confirm=yes.

This is **not** an authenticated production Sage receiver receipt;
the private metadata is unsigned and no live Bus message is created.

## Actual Mac validation and real VPS fault injection

Ran targeted tests including:
- three injected interruptions: after pending-journal fsync,
  after queue replacement and after committed-state replacement;
- restart/recovery of each to a single new queue card;
- repeated ticks after successful recovery produce no new card;
- a separate process exits during a staged transaction, then
  another process recovers using the same staging directory;
- partial queue.next and state.next writes healed from the
  existing journal;
- malformed/partial appended task records not consumed;
- modified/shortened historical Outbox rejected;
- source/task ID collisions, duplicate native IDs, symlinks,
  unknown notifications and external queue edits refused.

The full research repository passed 383 local tests with
33 existing uncalibrated-reference warnings.

**Executed on the actual authorized Sage VPS:** The adapter was
loaded into an SSH Python process without installing any file or
service. It copied the REAL VPS Outbox and task queue into an
automatically cleaned private temporary directory, then
appended three separate synthetic S1 requests to that COPY.

Each request was interrupted at a different durable transaction
phase; recovery succeeded three times. The final stage contained
**exactly three** private non-dispatchable cards, zero historical
replays and no outstanding journal. The source VPS production
Outbox and queue SHA256 values were identical before and after
the experiment; private staging files were removed. This is
fault injection in an isolated process, not a kill of the
production Sage receiver.

**Actual observed VPS counters:**
- Fault phases injected: 3
- Successful recoveries: 3
- Staged cards, exactly once: 3
- Replayed historic user requests: 0
- Changed live Sage Outbox/queue bytes: 0
- Authenticated real Sage task intake receipts: 0
- Real WebClip messages emitted: 0

These measurements establish an implementable private-source
transaction contract, NOT production ingestion or an
AffectControl scheduling-effect experiment.

## Remaining deployment boundaries

Before real installation, the actual Sage receiving authority
must approve and integrate task-card creation under its existing
queue guard and fencing policies. The receiver must preserve
trusted user authorization and source identity and produce an
independently verifiable task-level intake receipt bound to
S1 ID, accepted Sage task ID, source hash and observation time.
A genuine Bus message ID may be attached only when actually
returned by the authenticated Bus source.

Source files are merely replicated to the VPS today. The private
staged receipt is not a Sage-signed task acceptance, and a
queue card is not independent task-business acceptance. Natural
user deadlines, controlled AffectControl assignment and actual
task outcome oracle remain missing. Research stays E1 and
PR #1 remains draft.

## Reproduce with synthetic/authorized private files

Run:
    uv run --extra dev pytest -q tests/test_sage_outbox_durable_stage.py

The module's CLI supports:
    python -m benchmarks.sage_outbox_durable_stage init
    python -m benchmarks.sage_outbox_durable_stage tick
    python -m benchmarks.sage_outbox_durable_stage recover

All commands require an explicit private root; never point
that root at live Sage production queue files.
