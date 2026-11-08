"""Read-only verification of an EXISTING real Bus / S1-SHADOW trial.

This audits previously collected real WebClip transport observations,
the append-only S1 shadow sidecar, and archived local evaluator
artifacts, without modifying any source. Crucially: native S1 remains
unjoined and historical coding artifacts are NOT current re-test passes.
The provider-thread observation is an unsigned API snapshot, not proof
of externally signed data or production Sage/S1 attribution.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

from benchmarks.capture_execution import _write_exclusive

SCHEMA = "affectcontrol-existing-real-shadow-bridge-v1"
LEDGER_SCHEMA = "agent-eval/s1-shadow-lineage-v1"
STAGES = (
    "shadow_registered", "bus_request_linked", "bus_response_linked",
    "fresh_tests_linked", "shadow_closed",
)
SHADOW = re.compile(r"^s1shadow-[0-9a-f]{24}$")
HASH = re.compile(r"^[0-9a-f]{64}$")


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def obj(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("source may not be a symlink")
    return json.loads(path.read_bytes())


def compare(expected, observed, field):
    if observed != expected:
        raise ValueError(f"{field} mismatch")


def read_chain(db_path, shadow_id):
    if not SHADOW.fullmatch(shadow_id):
        raise ValueError("invalid shadow task ID")
    db_path = Path(db_path)
    if not db_path.is_file() or db_path.is_symlink():
        raise ValueError("missing or linked isolated shadow database")
    if os.name != "nt" and db_path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("shadow database is not private mode 0600")
    uri = "file:" + quote(str(db_path.resolve()), safe="/") + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        task = connection.execute(
            "SELECT * FROM shadow_tasks WHERE shadow_task_id=?", (shadow_id,)
        ).fetchone()
        if task is None:
            raise ValueError("no matching shadow task")
        task = dict(task)
        if task["source_mode"] != "isolated_shadow_only":
            raise ValueError("shadow sidecar claims a live task")
        rows = [
            dict(r) for r in connection.execute(
                "SELECT seq,event_type,payload_json,previous_hash,event_hash,recorded_utc "
                "FROM shadow_events WHERE shadow_task_id=? ORDER BY seq", (shadow_id,)
            ).fetchall()
        ]
        if len(rows) != len(STAGES):
            raise ValueError("shadow lineage is not a closed five-stage trace")
        prev = None
        payloads = []
        for idx, row in enumerate(rows):
            if row["seq"] != idx or row["event_type"] != STAGES[idx]:
                raise ValueError("shadow event sequence changed")
            payload = json.loads(row["payload_json"])
            envelope = {
                "schema": LEDGER_SCHEMA, "shadow_task_id": shadow_id,
                "seq": idx, "event_type": row["event_type"],
                "payload": payload, "recorded_utc": row["recorded_utc"],
                "previous_hash": prev,
            }
            if row["previous_hash"] != prev or row["event_hash"] != sha(canonical(envelope)):
                raise ValueError("shadow event hash chain mismatch")
            payloads.append(payload)
            prev = row["event_hash"]
        registered, sent, replied, tests, closed = payloads
        if registered.get("production_s1_task_id") is not None:
            raise ValueError("native S1 task claim forged")
        for key in ("correlation_id", "run_id", "eval_task_id", "run_manifest_sha256"):
            compare(task[key], registered[key], "registered " + key)
        compare(task["evidence_envelope_sha256"], registered["evidence_envelope_sha256"],
                "registered evidence envelope hash")
        if replied["parent_request_id"] != sent["request_id"] or replied["thread_id"] != sent["thread_id"]:
            raise ValueError("shadow Bus request/reply linkage broken")
        compare(task["evidence_envelope_sha256"], replied["echo_evidence_sha256"],
                "Bus echo evidence hash")
        if closed.get("s1_production_join_verified") is not False or closed.get("production_release_permitted") is not False:
            raise ValueError("historical shadow closure falsely claims production")
        if closed["software_tests_passed"] is not tests["software_tests_passed"]:
            raise ValueError("test summary and closure conflict")
        return task, payloads, prev, sha(db_path.read_bytes())
    finally:
        connection.close()


def audit(db_path, trial_dir, provider_snapshot, shadow_id):
    task, events, tip_hash, db_hash = read_chain(db_path, shadow_id)
    trial_dir = Path(trial_dir)
    if not trial_dir.is_dir() or trial_dir.is_symlink():
        raise ValueError("invalid shadow trial folder")
    envelope_file = trial_dir / "evidence-envelope.json"
    envelope = obj(envelope_file)
    compare(task["evidence_envelope_sha256"], sha(envelope_file.read_bytes()),
            "original evidence envelope")
    compare(task["correlation_id"], envelope.get("correlation_id"), "envelope correlation")
    request = obj(trial_dir / "bus-request.json")
    reply = obj(trial_dir / "bus-reply-observed.json")
    attestation_file = trial_dir / "fresh-tests" / "attestation.json"
    attestation = obj(attestation_file)
    report = obj(trial_dir / "verification-report.json")
    provider = obj(provider_snapshot)

    _, sent, responded, accepted, closed = events
    if request.get("schema") != "agent-eval/s1-shadow-bus-request-v1":
        raise ValueError("unexpected archived Bus request schema")
    if reply.get("schema") != "agent-eval/s1-shadow-bus-response-v1":
        raise ValueError("unexpected archived Bus response schema")
    for field, expected in (
        ("request_message_id", sent["request_id"]),
        ("thread_id", sent["thread_id"]),
        ("shadow_task_id", shadow_id),
        ("correlation_id", task["correlation_id"]),
        ("run_id", task["run_id"]),
        ("evidence_envelope_sha256", task["evidence_envelope_sha256"]),
    ):
        compare(expected, request.get(field), "archived Bus request " + field)
    if reply.get("type") != "result" or reply.get("from") != "sage" or reply.get("to") != "chatgpt":
        raise ValueError("archived response sender/recipient invalid")
    for field, expected in (
        ("id", responded["reply_id"]), ("reply_to", sent["request_id"]),
        ("thread_id", sent["thread_id"]),
    ):
        compare(expected, reply.get(field), "archived reply " + field)
    expected_echo = "ACK " + " ".join((
        shadow_id, task["correlation_id"], task["run_id"],
        task["evidence_envelope_sha256"],
    ))
    compare(expected_echo, reply.get("content"), "archived reply exact acknowledgement")

    if provider.get("schema") != "affectcontrol/read-only-provider-thread-snapshot-v1" or provider.get("source") != "authenticated_webclip_bus_read_thread":
        raise ValueError("unexpected provider snapshot")
    compare(sent["thread_id"], provider.get("thread_id"), "live provider thread id")
    remote_req = provider.get("original_request", {})
    remote_reply = provider.get("returned_reply", {})
    for field, expected in (
        ("id", sent["request_id"]), ("from", "chatgpt"), ("to", "sage"),
        ("type", "task"), ("thread_id", sent["thread_id"]),
    ):
        compare(expected, remote_req.get(field), "provider request " + field)
    for field, expected in (
        ("id", responded["reply_id"]), ("from", "sage"), ("to", "chatgpt"),
        ("type", "result"), ("thread_id", sent["thread_id"]),
        ("reply_to", sent["request_id"]), ("content", expected_echo),
    ):
        compare(expected, remote_reply.get(field), "provider reply " + field)
    if provider.get("checks", {}).get("reply_exactly_present_in_original_task_content") is not True:
        raise ValueError("provider request did not contain the expected echo")

    if attestation.get("schema") is None or attestation.get("fresh_software_acceptance") is not True:
        raise ValueError("incomplete archived independent software result")
    compare(accepted["attestation_sha256"], sha(attestation_file.read_bytes()), "archived test receipt")
    compare(accepted["code_diff_sha256"], attestation.get("code_diff_sha256_after"),
            "archived code diff")
    if report.get("production_s1_join_verified") is not False or report.get("actual_s1_task_id") is not None:
        raise ValueError("archived verification claimed native S1 link")
    compare(sha(envelope_file.read_bytes()), report.get("registered_envelope_sha256"),
            "archived report envelope hash")
    compare(tip_hash, report.get("event_tip_hash"), "archived report event tip")
    # The origin dates and task lineage are known from the stored shadow
    # sidecar. An API snapshot of live provider response authenticates the
    # transport data only to the extent that the connected API and the
    # present session are trusted; no external cryptographic signature.
    return {
        "schema": SCHEMA, "source_type": "real-shadow-sidecar-and-live-bus-api-snapshot",
        "shadow_db_sha256": db_hash,
        "shadow_event_tip_sha256": tip_hash,
        "source_envelope_sha256": task["evidence_envelope_sha256"],
        "provider_snapshot_sha256": sha(Path(provider_snapshot).read_bytes()),
        "archived_software_receipt_sha256": sha(attestation_file.read_bytes()),
        "n_real_bus_transport_roundtrips_correlated": 1,
        "n_verified_shadow_events": len(events),
        "archived_software_test_result": "passed_and_hash_consistent",
        "current_code_reexecution_outcome": "not_ascertained_by_this_historical_archive_audit",
        "native_s1_task_id": None, "production_s1_bus_join_verified": False,
        "source_business_user_deadline": None,
        "affectcontrol_scheduler_effect": None,
        "provider_snapshot_is_signed": False,
        "evidence_level": "E1-real-Bus-to-shadow-only",
        "warning": (
            "History-only, read-only cross-check; not current-code revalidation. "
            "The external provider snapshot is unsigned and obtained through "
            "an authenticated client session, not a separate trust root. "
            "Native S1 and autonomous task execution correlation are unproven. "
            "Archived software tests were linked to a PREEXISTING code run."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--shadow-db", required=True)
    p.add_argument("--trial-dir", required=True)
    p.add_argument("--provider-snapshot", required=True)
    p.add_argument("--shadow-id", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    result = audit(a.shadow_db, a.trial_dir, a.provider_snapshot, a.shadow_id)
    target = Path(a.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(target, (json.dumps(result, indent=2, sort_keys=True)+"\n").encode())
    print(json.dumps({
        "n_real_bus_transport_roundtrips_correlated": result["n_real_bus_transport_roundtrips_correlated"],
        "n_verified_shadow_events": result["n_verified_shadow_events"],
        "production_s1_bus_join_verified": False,
        "current_code_reexecution_outcome": result["current_code_reexecution_outcome"],
        "evidence_level": result["evidence_level"],
    }, indent=2))


if __name__ == "__main__":
    main()
