"""Synthetic proof fixtures; no sensitive real source IDs in this suite."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest
from benchmarks.s1_bus_join_gate import audit, sign, PROTOCOL, digest, canonical


KEYS = {"intake": b"i"*32, "s1": b"s"*32, "bus": b"b"*32}
REQ = "a"*64
TOKEN = "f"*64
ISSUED = "2026-11-01T00:00:00Z"
S1_TIME = "2026-11-01T01:00:00Z"
BUS_TIME = "2026-11-01T02:00:00Z"


def s1(timestamp=S1_TIME):
    return {
        "captured_utc": "2026-11-08T01:00:00Z",
        "event_id": "s1-observation-1",
        "event_type": "task_started",
        "kind": "first_seen",
        "observed_fingerprint": "c"*64,
        "schema": "affectcontrol/s1-origin-bound-v1",
        "correlation_id": TOKEN,
        "request_sha256": REQ,
        "source_table": "tasks",
        "task_trace_id": "shared-id-string-is-not-trustworthy",
        "timestamp": timestamp,
        "transport_or_task_status": "started",
        "verified_acceptance": False,
    }


def bus(verified=True, timestamp=BUS_TIME):
    return {
        "schema": "affectcontrol/bus-origin-bound-v1",
        "correlation_id": TOKEN,
        "request_sha256": REQ,
        "trace_id": "shared-id-string-is-not-trustworthy",
        "task_id": "task-not-private",
        "run_id": "run-a",
        "event_id": "bus-observation-1",
        "agent_id": "bot",
        "event_type": "agent_message",
        "timestamp": timestamp,
        "parent_event_ids": [],
        "unresolved_reply_to": None,
        "bus_type": "result",
        "bus_status_at_capture": "completed",
        "content_length": 0,
        "evidence_ref": "",
        "evidence_sha256": "d"*64,
        "provenance": "test-metadata",
        "payload_captured": False,
        "actor_identity_verified": verified,
        "model_tool_calls_observed": False,
    }


def write(tmp_path, rows):
    a = tmp_path / "s1.jsonl"
    b = tmp_path / "bus.jsonl"
    a.write_text("".join(json.dumps(x)+"\n" for x in [rows[0]]))
    b.write_text("".join(json.dumps(x)+"\n" for x in [rows[1]]))
    return a,b


def cert(role, **payload):
    return {**payload, "signature": sign(role,payload,KEYS[role])}


def proof():
    return {
        "schema": PROTOCOL,
        "intake": cert("intake", correlation_id=TOKEN,
                       request_sha256=REQ, issued_at=ISSUED),
        "s1": cert("s1", correlation_id=TOKEN,
                   request_sha256=REQ, event_id="s1-observation-1",
                   observed_at=S1_TIME, source_event_sha256=digest(canonical(s1()))),
        "bus": cert("bus", correlation_id=TOKEN,
                     request_sha256=REQ, event_id="bus-observation-1",
                     observed_at=BUS_TIME, source_event_sha256=digest(canonical(bus()))),
    }


def test_ordinary_matching_source_ids_never_mean_authenticated_join(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    result=audit(a,b)
    assert result["n_exact_id_overlaps_untrusted"] == 1
    assert result["n_verified_s1_bus_event_joins"] == 0
    assert result["n_submitted_dual_proofs"] == 0
    assert result["independent_agent_task_outcome_verified"] is None
    assert TOKEN not in json.dumps(result)
    assert "shared-id-string-is-not-trustworthy" not in json.dumps(result)


def test_valid_three_role_signed_evidence_links_exact_two_events(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    result=audit(a,b,proofs=[proof()],keys=KEYS)
    assert result["n_verified_s1_bus_event_joins"] == 1
    assert result["n_bus_actor_identity_verified"] == 1
    assert result["real_user_deadline_verified"] is None
    assert result["affectcontrol_treatment_verified"] is None


@pytest.mark.parametrize("alter,match", [
    (lambda p:p["s1"].update(request_sha256="b"*64),"signature"),
    (lambda p:p["bus"].update(event_id="forged"),"signature"),
    (lambda p:p["intake"].update(signature="0"*64),"signature"),
    (lambda p:p.update(schema="future-version"),"protocol"),
    (lambda p:p["s1"].update(correlation_id="b"*64),"signature"),
])
def test_tampered_proof_refused(tmp_path,alter,match):
    a,b=write(tmp_path,(s1(),bus()))
    p=proof();alter(p)
    with pytest.raises(ValueError,match=match):
        audit(a,b,proofs=[p],keys=KEYS)


def test_validly_signed_nonexistent_event_is_still_rejected(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    p=proof()
    p["bus"]=cert("bus",correlation_id=TOKEN,request_sha256=REQ,
                  event_id="does-not-exist",observed_at=BUS_TIME,
                  source_event_sha256=digest(canonical(bus())))
    with pytest.raises(ValueError,match="not present"):
        audit(a,b,proofs=[p],keys=KEYS)


def test_unverified_bus_actor_does_not_gain_trust_by_signature(tmp_path):
    a,b=write(tmp_path,(s1(),bus(verified=False)))
    with pytest.raises(ValueError,match="sender identity"):
        audit(a,b,proofs=[proof()],keys=KEYS)


def test_timestamp_mismatch_or_missing_source_time_refused(tmp_path):
    a,b=write(tmp_path,(s1(timestamp=None),bus()))
    with pytest.raises(ValueError,match="content hash mismatch"):
        audit(a,b,proofs=[proof()],keys=KEYS)
    a,b=write(tmp_path,(s1(timestamp="2026-11-01T01:00:01Z"),bus()))
    with pytest.raises(ValueError,match="content hash mismatch"):
        audit(a,b,proofs=[proof()],keys=KEYS)


def test_intake_must_precede_real_source_events(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    p=proof()
    p["intake"]=cert("intake",correlation_id=TOKEN,request_sha256=REQ,
                     issued_at="2026-11-02T00:00:00Z")
    with pytest.raises(ValueError,match="after source event"):
        audit(a,b,proofs=[p],keys=KEYS)


def test_replayed_signed_claim_rejected(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    with pytest.raises(ValueError,match="replayed"):
        audit(a,b,proofs=[proof(),deepcopy(proof())],keys=KEYS)


def test_all_role_keys_must_be_distinct(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    with pytest.raises(ValueError,match="distinct"):
        audit(a,b,proofs=[proof()],keys={"intake":KEYS["s1"],"s1":KEYS["s1"],"bus":KEYS["bus"]})


def test_missing_private_keys_not_silently_accepted(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    with pytest.raises(ValueError,match="without private"):
        audit(a,b,proofs=[proof()])


def test_extra_private_raw_field_rejected(tmp_path):
    item=s1()
    item["original_task_text"]="should remain private"
    a,b=write(tmp_path,(item,bus()))
    with pytest.raises(ValueError,match="unexpected fields"):
        audit(a,b)


def test_unverified_source_time_and_sender_flags_rejected(tmp_path):
    row=bus()
    row["actor_identity_verified"]="true"
    a,b=write(tmp_path,(s1(),row))
    with pytest.raises(ValueError,match="invalid actor_identity_verified"):
        audit(a,b)


def test_bad_s1_event_duplicate_rejected(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    a.write_text(a.read_text()+a.read_text())
    with pytest.raises(ValueError,match="duplicate source event ID"):
        audit(a,b)

def test_validly_signed_but_mutated_bus_status_rejected(tmp_path):
    row=bus()
    row["bus_status_at_capture"]="fabricated_completion"
    a,b=write(tmp_path,(s1(),row))
    with pytest.raises(ValueError,match="Bus source event content hash mismatch"):
        audit(a,b,proofs=[proof()],keys=KEYS)

def test_validly_signed_but_mutated_s1_status_rejected(tmp_path):
    item=s1()
    item["transport_or_task_status"]="fabricated_accepted"
    a,b=write(tmp_path,(item,bus()))
    with pytest.raises(ValueError,match="S1 source event content hash mismatch"):
        audit(a,b,proofs=[proof()],keys=KEYS)

def test_validly_signed_but_changed_bus_evidence_digest_rejected(tmp_path):
    item=bus()
    item["evidence_sha256"]="e"*64
    a,b=write(tmp_path,(s1(),item))
    with pytest.raises(ValueError,match="Bus source event content hash mismatch"):
        audit(a,b,proofs=[proof()],keys=KEYS)

def test_v1_signature_cannot_be_reused_for_v2(tmp_path):
    a,b=write(tmp_path,(s1(),bus()))
    p=proof()
    from hashlib import sha256
    import hmac
    payload={k:p["s1"][k] for k in ("correlation_id","request_sha256","event_id","observed_at","source_event_sha256")}
    p["s1"]["signature"]=hmac.new(KEYS["s1"],b"AffectControl-join-v1\x00s1\x00"+canonical(payload),sha256).hexdigest()
    with pytest.raises(ValueError,match="signature"):
        audit(a,b,proofs=[p],keys=KEYS)

def test_historical_unbound_events_rejected_even_if_retrospectively_signed(tmp_path):
    arow=s1()
    brow=bus()
    arow.pop("correlation_id")
    arow.pop("request_sha256")
    brow.pop("correlation_id")
    brow.pop("request_sha256")
    arow["schema"]="agent-eval/s1-watch-v1"
    brow["schema"]="agent-eval/v1"
    a,b=write(tmp_path,(arow,brow))
    # Retroactive signatures over the literal legacy source events
    # still cannot prove that these were from the registered task.
    p=proof()
    p["s1"]=cert("s1",correlation_id=TOKEN,request_sha256=REQ,
                 event_id=arow["event_id"],observed_at=S1_TIME,
                 source_event_sha256=digest(canonical(arow)))
    p["bus"]=cert("bus",correlation_id=TOKEN,request_sha256=REQ,
                  event_id=brow["event_id"],observed_at=BUS_TIME,
                  source_event_sha256=digest(canonical(brow)))
    with pytest.raises(ValueError,match="lacks prospective task binding"):
        audit(a,b,proofs=[p],keys=KEYS)

def test_in_source_token_must_match_signed_intake_claim(tmp_path):
    changed=s1()
    changed["correlation_id"]="e"*64
    a,b=write(tmp_path,(changed,bus()))
    with pytest.raises(ValueError,match="in-source task binding mismatch"):
        audit(a,b,proofs=[proof()],keys=KEYS)

def test_in_source_request_hash_must_match_signed_intake_claim(tmp_path):
    changed=bus()
    changed["request_sha256"]="d"*64
    a,b=write(tmp_path,(s1(),changed))
    with pytest.raises(ValueError,match="in-source task binding mismatch"):
        audit(a,b,proofs=[proof()],keys=KEYS)

def test_source_binding_required_for_signed_claims_even_with_matching_id(tmp_path):
    first=s1()
    first.pop("correlation_id")
    first.pop("request_sha256")
    first["schema"]="agent-eval/s1-watch-v1"
    a,b=write(tmp_path,(first,bus()))
    with pytest.raises(ValueError,match="lacks prospective task binding"):
        audit(a,b,proofs=[proof()],keys=KEYS)
