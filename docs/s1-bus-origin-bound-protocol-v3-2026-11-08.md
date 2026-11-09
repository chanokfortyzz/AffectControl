# S1 / Sage Bus: prospective source-bound correlation v3

Date: November 8, 2026. This is research code and is not deployed
to the Sage production system. AffectControl evidence remains E1.

## Problems with previous evidence protocol

Version 1 signed event ID, timestamp and task registration, but not
the entire original event: another field could change while the
signature remained valid. Version 2 signed full event contents but
still allowed a signer to *retroactively assert* that an unrelated
historical source event belonged to a given task.

Version 3 fixes both weaknesses and rejects the unsupported join.

## New origin-bound event requirements

Legacy historical S1 and Bus rows can be counted, but do NOT qualify
for a signed task join. New prospective event schemas are:

- affectcontrol/s1-origin-bound-v1
- affectcontrol/bus-origin-bound-v1

Both must contain fields correlation_id (random 256-bit opaque token)
and request_sha256 (original task request digest), written by the
trusted source event reporter AT event creation, not backfilled later.

Three different role keys, separately owned, must sign:
1. Intake: token, original request digest, registered issue time.
2. S1: token, request digest, event ID, observed time, SHA256 of the
   entire canonical S1 event.
3. Bus: matching fields for its own independently observed Bus event.

Verification checks the HMAC signatures, timestamp order, matching
task/digest, event source content hashes, source-record token/digest,
an authentic Bus actor identity and unique unreplayed source joins.
It rejects records that lack the prospective source fields even if
a later caller produces a cryptographically valid attestation.

## Executed actual source census

| Evidence | Number |
|---|---:|
| Real historical S1 rows | 202 |
| Real historical Bus message rows | 2 |
| S1 rows containing preissued task token and request digest | 0 |
| Bus rows containing preissued task token and request digest | 0 |
| Bus actors independently verified | 0 |
| Admissible S1/Bus source event joins | 0 |

This does not establish that past S1 and Bus work was unrelated. It
establishes only that the existing saved records cannot prove it.
Raw source files were not changed or published; the actual audit
output is kept in the gitignored research data directory.

## Proven safety boundary and limitations

Synthetic adversarial tests show that changing S1 status, Bus status,
Bus evidence digest, event token or request digest breaks admission.
Even a legacy event with an after-the-fact signed proof is rejected.

The code does not yet authenticate real users or install an
independent production key-custody boundary. Symmetric HMAC secrets
need separate protected ownership for the trusted intake, S1 and
Bus reporter, or one compromised process could forge all signatures.
A Bus source bool asserting authenticated sender is insufficient
unless the source really validated the actor. Live source writers
do not yet issue these new fields. Test fixtures are NOT evidence
of actual production-source attestations.

Neither an event join nor source integrity alone proves task
acceptance, natural deadlines or a causal AffectControl scheduling
benefit. E1 remains; no Sage production scheduling change.

## Concrete next integration steps

- Trusted intake: issue correlation token and hash original task
  instruction before work starts, store provenance privately.
- S1 and Bus: persist the verified token/digest *at event creation*
  with source identity and real observation timestamp; Agents cannot
  edit or supply these fields.
- Keep separate protected intake, S1 and Bus keys; sign complete
  immutable event records and protect against replay.
- Independent read-only verifier: inspect original event sources,
  signed attestations and distinct task acceptance criterion.
- Only later, with documented consent, capture real deadlines and
  preplanned treatment allocation for an E2 intervention experiment.

Reproduce: run pytest tests/test_s1_bus_join_gate.py and then the
full repository tests using uv run --extra dev pytest -q.
