# Historical Sage Bridge queue evidence: original S1 tasks
Date: November 8, 2026. Read-only inspection; research remains E1.

## Verified source coverage

Native S1 agent_executions stores 3 provider mappings, 2 reported
COMPLETED and 1 CREATED. Original local 04-MAC_OUTBOX.md contains
3 request blocks with exact (s1_ref, suggested Sage task ID) matches.

A new strictly source-grained audit scanned cached historic Sage
task-queue and archive snapshots (02-MAC_TASK_QUEUE files).
317 candidates existed: 77 contained duplicate task card IDs and
were **excluded in their entirety**; 240 passed this source-grain check.

| Evidence criterion | Native mappings covered |
|---|---:|
| Source native S1-to-provider IDs | 3 |
| Exact local outbox request matches | 3 |
| Provider task ID observed in an eligible historic queue snapshot | 2 |
| At least one cached card with exact in-card matching s1_ref | 1 |
| At least one cached card with provider ID only and missing s1_ref | 2 |
| Cached queued card present | 2 |
| No eligible cached card | 1 |
| Eligible cached done status | 0 |
| Separate nonempty result files, from prior audit | 2 |
| Authenticated remote Sage acceptance receipt | unavailable |
| Authenticated native S1-to-WebClip Bus message ID | unavailable |

For the FIRST S1 task, a historical queued card explicitly contained
both the original S1 ref and provider ID, while other provider-ID
cards omitted the ref. The SECOND had a queued provider-ID card
without the original S1 ref, a weaker association. The THIRD had
no eligible historic queue card despite its local outbox entry.

Important correction: an earlier raw file search found archived
done cards for the first task, but these occurred in archive source
files with duplicate card IDs. The strict audit excluded those
sources rather than selecting favorable status labels. Neither a
historical done flag nor an existing result file proves independently
accepted business completion.

## Implementation and evidence boundaries

The new read-only source auditor is
benchmarks/sage_bridge_historical_queue.py. It uses native SQLite
read-only access, bounded local queue backup reads, exact per-card
s1_ref and provider-ID comparison, full source SHA256 fingerprints
and aggregate-only results. It does not expose task IDs, original
goals, archived card text, private prompts, credentials or filenames
in the committed output. Nine regression tests cover exact matches,
provider-only matches, missing cards, duplicate and malformed
snapshots, conflicting mappings, duplicate submissions and source
immutability.

The bridge-push script uses rsync; command success alone does not
prove the Sage service consumed a particular request. Local queue
backups are not remotely signed acknowledgements. Missing current
indices can reflect rotation or archiving.

The next real integration must write an authoritative per-task
Sage intake acknowledgement referencing the exact native S1 ID
and Sage provider ID; a WebClip message ID must be attached only
if the associated real Bus event is independently sourced and
authenticated. The existing v3 source-origin proof can then check
prospective events, not retroactively manufactured tokens.

No Sage production dispatch, native S1 database, WebClip event,
stored worktree or scheduler was changed. No real user deadline,
independent outcome judgement or AffectControl treatment effect
is demonstrated. Research remains E1 and PR #1 remains draft.

## Reproduce on the authorized host

Run python -m benchmarks.sage_bridge_historical_queue with
--db pointing at the existing native S1 SQLite file, --bridge at
the real SAGE-MAC-BRIDGE directory, --outbox at the existing
04-MAC_OUTBOX.md, and --out at a new ignored research-data file.
Run pytest -q tests/test_sage_bridge_historical_queue.py.
The evidence output is create-only and never overwrites an old run.
