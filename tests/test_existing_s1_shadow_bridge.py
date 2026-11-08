"""Isolated fixtures: no historic user data, no Bus network in CI."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from benchmarks.existing_s1_shadow_bridge import audit, canonical, sha, LEDGER_SCHEMA, STAGES


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, sort_keys=True, indent=2) + "\n").encode())
    return path


@pytest.fixture
def historical_fixture(tmp_path):
    db = tmp_path / "lineage.sqlite"
    trial = tmp_path / "trial"
    trial.mkdir()
    shadow = "s1shadow-" + "a"*24
    correlation = "ev-" + "b"*24
    run = "claude-run-" + "c"*12
    request_id = "msg-" + "d"*12
    reply_id = "msg-" + "e"*12
    thread_id = "th-" + "f"*12
    envelope = put(trial / "evidence-envelope.json", {"correlation_id": correlation, "version": 1})
    env_hash = sha(envelope.read_bytes())
    test_receipt = put(trial / "fresh-tests" / "attestation.json",
                       {"schema": "lab-only", "fresh_software_acceptance": True,
                        "code_diff_sha256_after": "9"*64})
    att_hash = sha(test_receipt.read_bytes())
    echo = "ACK " + " ".join((shadow, correlation, run, env_hash))
    put(trial / "bus-request.json", {
        "schema": "agent-eval/s1-shadow-bus-request-v1",
        "shadow_task_id": shadow, "correlation_id": correlation,
        "run_id": run, "request_message_id": request_id,
        "thread_id": thread_id, "evidence_envelope_sha256": env_hash,
    })
    put(trial / "bus-reply-observed.json", {
        "schema": "agent-eval/s1-shadow-bus-response-v1",
        "id": reply_id, "reply_to": request_id, "thread_id": thread_id,
        "from": "sage", "to": "chatgpt", "type": "result", "content": echo,
    })
    provider = put(tmp_path / "provider.json", {
        "schema": "affectcontrol/read-only-provider-thread-snapshot-v1",
        "source": "authenticated_webclip_bus_read_thread",
        "thread_id": thread_id,
        "original_request": {
            "id": request_id, "from": "chatgpt", "to": "sage",
            "type": "task", "thread_id": thread_id,
        },
        "returned_reply": {
            "id": reply_id, "reply_to": request_id,
            "thread_id": thread_id, "from": "sage", "to": "chatgpt",
            "type": "result", "content": echo,
        },
        "checks": {"reply_exactly_present_in_original_task_content": True},
    })

    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE shadow_tasks (shadow_task_id TEXT, correlation_id TEXT, "
                 "eval_task_id TEXT, eval_arm TEXT, run_id TEXT, "
                 "run_manifest_sha256 TEXT, evidence_envelope_sha256 TEXT, "
                 "created_utc TEXT, source_mode TEXT)")
    conn.execute("CREATE TABLE shadow_events (shadow_task_id TEXT, seq INTEGER, "
                 "event_type TEXT, payload_json TEXT, previous_hash TEXT, "
                 "event_hash TEXT, recorded_utc TEXT)")
    run_sha = "7"*64
    conn.execute("INSERT INTO shadow_tasks VALUES (?,?,?,?,?,?,?,?,?)",
                 (shadow, correlation, "PIPELINE-003", "B2", run, run_sha,
                  env_hash, "2026-11-01T00:00:00Z", "isolated_shadow_only"))
    events = [
        {"correlation_id": correlation, "eval_task_id": "PIPELINE-003",
         "run_id": run, "run_manifest_sha256": run_sha,
         "evidence_envelope_sha256": env_hash, "production_s1_task_id": None},
        {"request_id": request_id, "thread_id": thread_id,
         "source": "webclip_send_message_observed"},
        {"reply_id": reply_id, "parent_request_id": request_id,
         "thread_id": thread_id, "echo_evidence_sha256": env_hash,
         "message_source": "webclip_read_thread_observed", "transport_correlated": True},
        {"attestation_sha256": att_hash, "code_diff_sha256": "9"*64,
         "software_tests_passed": True, "real_hardware_verified": False},
        {"transport_correlated": True, "software_tests_passed": True,
         "hardware_verified": False, "s1_production_join_verified": False,
         "production_release_permitted": False},
    ]
    previous = None
    for i, payload in enumerate(events):
        at = f"2026-11-01T00:0{i}:00Z"
        body = {"schema": LEDGER_SCHEMA, "shadow_task_id": shadow, "seq": i,
                "event_type": STAGES[i], "payload": payload,
                "recorded_utc": at, "previous_hash": previous}
        current = sha(canonical(body))
        conn.execute("INSERT INTO shadow_events VALUES (?,?,?,?,?,?,?)",
                     (shadow, i, STAGES[i], canonical(payload).decode(),
                      previous, current, at))
        previous = current
    conn.commit()
    conn.close()
    db.chmod(0o600)
    put(trial / "verification-report.json", {
        "event_tip_hash": previous, "registered_envelope_sha256": env_hash,
        "production_s1_join_verified": False, "actual_s1_task_id": None,
    })
    return db, trial, provider, shadow


def call(paths):
    return audit(*paths)


def test_valid_historical_bridge_is_only_shadow_to_real_bus_claim(historical_fixture):
    result = call(historical_fixture)
    assert result["n_real_bus_transport_roundtrips_correlated"] == 1
    assert result["n_verified_shadow_events"] == 5
    assert result["archived_software_test_result"] == "passed_and_hash_consistent"
    assert result["current_code_reexecution_outcome"] == "not_ascertained_by_this_historical_archive_audit"
    assert result["native_s1_task_id"] is None
    assert result["production_s1_bus_join_verified"] is False
    assert result["provider_snapshot_is_signed"] is False
    assert result["source_business_user_deadline"] is None


def test_archived_bus_provider_reply_tamper_rejected(historical_fixture):
    db,trial,provider,tid = historical_fixture
    data=json.loads(provider.read_text())
    data["returned_reply"]["reply_to"]="msg-fake"
    put(provider,data)
    with pytest.raises(ValueError,match="provider reply reply_to"):
        call(historical_fixture)


def test_archive_message_mismatch_rejected(historical_fixture):
    db,trial,provider,tid = historical_fixture
    p=trial/"bus-reply-observed.json"
    data=json.loads(p.read_text());data["content"] += " forged"
    put(p,data)
    with pytest.raises(ValueError,match="exact acknowledgement"):
        call(historical_fixture)


def test_changed_archived_test_receipt_rejected(historical_fixture):
    db,trial,provider,tid = historical_fixture
    p=trial/"fresh-tests"/"attestation.json"
    p.write_bytes(p.read_bytes()+b" ")
    with pytest.raises(ValueError,match="archived test receipt"):
        call(historical_fixture)


def test_changed_shadow_chain_refused(historical_fixture):
    db,trial,provider,tid = historical_fixture
    conn=sqlite3.connect(db)
    conn.execute("UPDATE shadow_events SET payload_json=? WHERE seq=2",
                 ('{"transport_correlated":false}',))
    conn.commit();conn.close()
    with pytest.raises(ValueError,match="hash chain"):
        call(historical_fixture)


def test_forged_native_s1_link_rejected(historical_fixture):
    db,trial,provider,tid = historical_fixture
    p=trial/"verification-report.json"
    data=json.loads(p.read_text());data["production_s1_join_verified"]=True
    put(p,data)
    with pytest.raises(ValueError,match="native S1 link"):
        call(historical_fixture)


def test_snapshot_source_not_accepted_without_provider_label(historical_fixture):
    db,trial,provider,tid = historical_fixture
    data=json.loads(provider.read_text());data["source"]="self_reported_by_agent"
    put(provider,data)
    with pytest.raises(ValueError,match="provider snapshot"):
        call(historical_fixture)


def test_database_is_read_only_not_updated_by_audit(historical_fixture):
    db,trial,provider,tid=historical_fixture
    before=sha(db.read_bytes())
    call(historical_fixture)
    assert sha(db.read_bytes())==before


def test_unexpected_shadow_id_refused(historical_fixture):
    db,trial,provider,tid=historical_fixture
    with pytest.raises(ValueError,match="invalid shadow task ID"):
        audit(db,trial,provider,"native-s1-task-1")
