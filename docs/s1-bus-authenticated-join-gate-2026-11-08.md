# S1 / Sage Bus authenticated join evidence gate (2026-11-08)

Research evidence status: E1. No changes to Sage production dispatch.

## Actual read-only source audit

- S1 watcher: 202 actual pseudonymous event records; 17 distinct trace IDs.
- Historic Sage Bus partial sample: 2 message event records.
- Bus rows with verified actor identity: **0**.
- Literal S1 trace-ID versus Bus trace/task/run/event-ID overlaps: **0**.
- Valid authentic intake/S1/Bus three-way attestations found: **0**.
- Confirmed S1-Bus event joins: **0**.

The S1 watcher has one event with a null source timestamp. It was
included in source coverage but excluded from any time-bound proof.
The read-only S1 observer health also reports an unestablished
Bus-Sage join, unavailable independent acceptance, and zero automatic
dispatches. The Bus record sample is partial, so the zero result
does not establish that no real corresponding tasks ever existed.
It means **no join can be demonstrated from these samples**.

Raw source logs and full machine output remain gitignored; only
aggregate counters are included in the report and commit.

## Prospective three-role authenticated event proof

The new benchmarks/s1_bus_join_gate.py verifier supports
the following OPTIONAL future evidence structure:

1. Trusted task intake issues an unpredictable 256-bit correlation
   token, records a hash of the original request, and signs both
   with its own intake HMAC key and registration timestamp.
2. The S1 trusted observer signs its observed event ID, original
   timestamp, token and matching request digest using a separate
   S1 key.
3. The Bus trusted observer independently signs its event ID,
   timestamp, token and request digest under a separate Bus key.
   The Bus source event must additionally have an authenticated
   message-sender identity.

The offline gate rejects absent or wrong-source events, inconsistent
request digests, invalid signatures, timestamp mismatch, replayed
event proofs, post-event intake registration, non-independent role
keys, malformed source flags and unknown/raw private fields.
Even identical-looking pseudonymous IDs are explicitly NOT trusted
without proofs.

The positive proof fixture is synthetic. No such proof or role
key infrastructure was deployed to the live user's S1 or Bus.
Three symmetric HMAC keys would need independent, trusted custody
outside the Agent executor; holding all three in one compromised
process would defeat this boundary. This is a research prototype,
not a deployed security service or cryptographic signature from
three independently validated organizations.

A valid event join would still not establish natural user deadlines,
independent task acceptance, actual task running time, or randomized
AffectControl-vs-urgency efficacy. **E2 remains unavailable.**

## Reproduction on the authorized user's computer

    uv run --extra dev python -m benchmarks.s1_bus_join_gate \
      --s1-watch /Users/chenzhiliang/coding-service/agent-eval/adaptive/s1_watch/changes.pseudonymous.jsonl \
      --bus /Users/chenzhiliang/coding-service/agent-eval/bus-partial-trace.jsonl \
      --out .research-data/e2-evidence-20261108/another-s1bus-audit.json

    uv run --extra dev pytest -q tests/test_s1_bus_join_gate.py

The output is create-only. Never generate retrospective fictitious
attestations for historical S1 or Bus records.

## Subsequent v3 protocol correction

After adversarial review, it became clear that the original HMAC
proof did not cover all event content, and that full-event signing
without prospective in-source task binding was still insufficient.
Current v3 additionally requires the task token and request digest
to be present in the original source event row. Historical events
are readable for coverage but cannot be retroactively promoted.
Actual data: 202 S1 events, two Bus events, zero eligible joins.
See s1-bus-origin-bound-protocol-v3-2026-11-08.md.
