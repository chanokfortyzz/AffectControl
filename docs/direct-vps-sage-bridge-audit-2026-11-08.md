# Direct Sage VPS Bridge source audit (2026-11-08)

## Real source inspection: E1

Using the authorized Mac Sage Bridge SSH connection, a read-only
program accessed actual remote VPS Bridge files. This is a
stronger source than local Mac backups, but it does NOT constitute
a signed, per-task Sage intake acknowledgement. No production
dispatch or configuration was modified.

The program benchmarks/remote_sage_bridge_audit.py reads four
bounded remote sources through one BatchMode SSH Python process:

- 04-MAC_OUTBOX.md: remotely replicated requests
- 02-MAC_TASK_QUEUE.md: current remote queue
- 02-MAC_TASK_QUEUE-ARCHIVE.md: remote queue archive
- 07-MAC_TASK_STATE.json: remote task watchdog

It reads native S1 SQLite via read-only mode, sends original
task correlation fields through encrypted SSH standard input
rather than shell arguments, and returns only aggregate counts,
file sizes, UTC times and SHA256 digests. Raw task text and IDs
are NOT printed, added to the repo or exported.

## Actual VPS observations

| Evidence field | Direct remote value |
|---|---:|
| Native S1-to-Sage mappings checked | 3 |
| Remotely replicated Outbox request blocks matching BOTH native s1_ref and provider ID | 3 |
| Duplicate exact remote Outbox pairs | 0 |
| Mapped provider IDs in current VPS queue | 0 |
| Mapped provider IDs in current VPS 76-task watchdog | 0 |
| Provider ID in VPS historic archive | 1 |
| Historic archived card with matching original s1_ref | 0 |
| Historic done status as untrusted source text | 1 |
| Duplicate task-card IDs inside VPS archive | 1 |
| Positive done status admitted after source-grain check | 0 |
| Signed Sage per-task intake acknowledgement | Missing |
| Authenticated native S1 to WebClip message ID | Missing |

Original source SHA256 hashes and file metadata are recorded in
private, gitignored local research data. They detect changes to
source copies but do not certify independent remote provider
acceptance. The authoritative remote Outbox confirms all three
request blocks arrived at the VPS Bridge FILE layer, not that
the Sage task intake service accepted or dispatched each request.

A historic remote archive contains a done status but also duplicate
task IDs. The archive cannot be used as positive outcome evidence:
the raw done occurrence is explicitly untrusted.

## Repeatability and trust boundaries

The tool does not run the Sage Bridge push script or any remote
write. It parses the literal SSH target from the existing Mac
config file without sourcing it or running shell substitutions.
Only a fixed, read-only Python source inspector runs over SSH.

Nine source-free regression tests run the identical remote code
over temporary mock directories and exercise missing/linked
files, duplicate Outbox request pairs, conflicting task refs,
duplicate archive cards, source SHA256 consistency and SSH
config safety. Full local suite: 346 passed, with 33 old
uncalibrated-reference warnings.

A proper Sage acceptance receipt needs a trusted receiver source
to record the original S1 task ID, actual accepted Sage provider
card ID, request digest, arrival timestamp, verified actor and,
if a real Bus message was generated, its authenticated message ID.
Nothing in this audit authorizes an in-place Sage production
configuration change or retroactive receipt fabrication.

Original user deadlines, independent business outcomes and a
prospective AffectControl-vs-urgency policy study remain absent.
Research stays E1; the PR remains draft.

## Reproduction

Run this from the research repository, with authorized Mac access:

    uv run --extra dev python -m benchmarks.remote_sage_bridge_audit \
      --db '/Users/chenzhiliang/Desktop/_项目/S1/data/s1.db' \
      --push-script '/Users/chenzhiliang/bin/sage-bridge-push.sh' \
      --out '.research-data/new-real-vps-audit.json'

Then run pytest against tests/test_remote_sage_bridge_audit.py.
Use a new output path; no existing results are overwritten.
