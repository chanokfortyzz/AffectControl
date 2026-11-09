"""Read-only S1/Bus join admissibility and prospective dual-source proof gate.

A matching pseudonym, timing proximity, transport "completed" state, or
claim of task linkage is never accepted as a trusted cross-system join.
The optional proof protocol requires a trusted intake and TWO independent
source attestations, each signed with a distinct domain-separated HMAC key.
No real source identities, prompts, or secrets are emitted.

A successful proof joins *two observed event records* for the same
registered task; it does NOT prove Agent task completion or a deadline.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

from benchmarks.capture_execution import _write_exclusive

PROTOCOL = "affectcontrol-s1-bus-origin-bound-join-v3"
WATCH_SCHEMA = "agent-eval/s1-watch-v1"
BUS_SCHEMA = "agent-eval/v1"
WATCH_BOUND_SCHEMA = "affectcontrol/s1-origin-bound-v1"
BUS_BOUND_SCHEMA = "affectcontrol/bus-origin-bound-v1"
ORIGIN_FIELDS = frozenset({"correlation_id", "request_sha256"})
WATCH_FIELDS = frozenset({
    "captured_utc", "event_id", "event_type", "kind",
    "observed_fingerprint", "schema", "source_table",
    "task_trace_id", "timestamp", "transport_or_task_status",
    "verified_acceptance",
})
BUS_FIELDS = frozenset({
    "schema", "trace_id", "task_id", "run_id", "event_id", "agent_id",
    "event_type", "timestamp", "parent_event_ids", "unresolved_reply_to",
    "bus_type", "bus_status_at_capture", "content_length", "evidence_ref",
    "evidence_sha256", "provenance", "payload_captured",
    "actor_identity_verified", "model_tool_calls_observed",
})
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_SOURCE_BYTES = 20_000_000
MAX_RECORDS = 100_000
SIGNABLE = {
    "intake": frozenset({"correlation_id", "request_sha256", "issued_at"}),
    "s1": frozenset({"correlation_id", "request_sha256", "event_id", "observed_at", "source_event_sha256"}),
    "bus": frozenset({"correlation_id", "request_sha256", "event_id", "observed_at", "source_event_sha256"}),
}


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _time(value):
    if not isinstance(value, str):
        raise ValueError("missing ISO timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid ISO timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone missing from timestamp")
    return dt.astimezone(timezone.utc)


def _source(path, label, fields, schema):
    raw = Path(path).read_bytes()
    if not raw or len(raw) > MAX_SOURCE_BYTES:
        raise ValueError(f"{label}: empty or oversized source")
    rows = []
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: invalid source encoding") from exc
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if len(rows) >= MAX_RECORDS:
            raise ValueError(f"{label}: too many rows")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label}: invalid JSON on line {lineno}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{label}: invalid source object")
        prospective_schema = WATCH_BOUND_SCHEMA if label == "S1" else BUS_BOUND_SCHEMA
        if row.get("schema") == schema:
            expected_fields = fields
        elif row.get("schema") == prospective_schema:
            expected_fields = fields | ORIGIN_FIELDS
        else:
            raise ValueError(f"{label}: unsupported source schema")
        if set(row) != expected_fields:
            raise ValueError(f"{label}: unexpected fields/schema (possibly private raw data)")
        if row.get("schema") == prospective_schema:
            if not all(
                    isinstance(row.get(key), str) and HEX64.fullmatch(row[key])
                    for key in ORIGIN_FIELDS):
                raise ValueError(f"{label}: invalid in-source task correlation binding")
        if not isinstance(row["event_id"], str) or not row["event_id"]:
            raise ValueError(f"{label}: missing event identifier")
        # Historical watcher has an event whose source timestamp is null.
        # Retain it in coverage but never let it enter a timestamp-bound join.
        if row["timestamp"] is None and label == "S1":
            pass
        else:
            _time(row["timestamp"])
        if label == "S1":
            if not isinstance(row["task_trace_id"], str) or not row["task_trace_id"]:
                raise ValueError("S1: missing pseudonymous trace")
            if type(row["verified_acceptance"]) is not bool:
                raise ValueError("S1: invalid verified acceptance flag")
        else:
            for field in ("actor_identity_verified", "payload_captured", "model_tool_calls_observed"):
                if type(row[field]) is not bool:
                    raise ValueError(f"Bus: invalid {field} flag")
        rows.append(row)
    if not rows:
        raise ValueError(f"{label}: no event records")
    ids = [r["event_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{label}: duplicate source event ID; revisions require separate audit")
    return rows, digest(raw)


def sign(role, payload, key):
    """Test/prospective-emitter helper; DO NOT put signing keys in task logs."""
    if role not in SIGNABLE or set(payload) != SIGNABLE[role]:
        raise ValueError("unknown attestation role/fields")
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("attestation key must be 32+ private bytes")
    return hmac.new(key, b"AffectControl-join-v3\x00" + role.encode()
                    + b"\x00" + canonical(payload), hashlib.sha256).hexdigest()


def _validate_attestation(role, record, key):
    if not isinstance(record, dict) or set(record) != SIGNABLE[role] | {"signature"}:
        raise ValueError(f"{role}: invalid attestation envelope")
    for k in SIGNABLE[role]:
        if not isinstance(record[k], str) or not record[k]:
            raise ValueError(f"{role}: missing {k}")
    for k in ("correlation_id", "request_sha256", "source_event_sha256"):
        if k == "source_event_sha256" and role == "intake":
            continue
        if not HEX64.fullmatch(record[k]):
            raise ValueError(f"{role}: invalid {k}")
    _time(record["issued_at"] if role == "intake" else record["observed_at"])
    expected = sign(role, {k: record[k] for k in SIGNABLE[role]}, key)
    if not isinstance(record["signature"], str) or not hmac.compare_digest(
            expected, record["signature"]):
        raise ValueError(f"{role}: signature invalid")
    return record


def verify_proof(proof, s1_by_event, bus_by_event, keys):
    if not isinstance(proof, dict) or set(proof) != {"schema", "intake", "s1", "bus"}:
        raise ValueError("invalid join proof envelope")
    if proof["schema"] != PROTOCOL:
        raise ValueError("unsupported join proof protocol")
    if not isinstance(keys, dict) or set(keys) != set(SIGNABLE):
        raise ValueError("all three independent attestation key roles required")
    if len(set(keys.values())) != 3:
        raise ValueError("attestation roles must use distinct keys")
    parts = {
        role: _validate_attestation(role, proof[role], keys[role])
        for role in ("intake", "s1", "bus")
    }
    if len({p["correlation_id"] for p in parts.values()}) != 1:
        raise ValueError("source attestations disagree on correlation ID")
    if len({p["request_sha256"] for p in parts.values()}) != 1:
        raise ValueError("source attestations disagree on request digest")
    s1 = s1_by_event.get(parts["s1"]["event_id"])
    bus = bus_by_event.get(parts["bus"]["event_id"])
    if s1 is None or bus is None:
        raise ValueError("attested event not present in its source log")
    if not bus["actor_identity_verified"]:
        raise ValueError("Bus sender identity is not verified")
    # A signature constructed *after the event* could claim any arbitrary
    # task token. It is not adequate unless the two SOURCE EVENT ROWS
    # themselves carried the matching, pre-issued correlation ID and request
    # digest when their trusted reporters observed the events.
    for role, row, allowed in (
            ("s1", s1, WATCH_BOUND_SCHEMA),
            ("bus", bus, BUS_BOUND_SCHEMA)):
        if row["schema"] != allowed:
            raise ValueError(f"{role}: source event lacks prospective task binding")
        for field in ("correlation_id", "request_sha256"):
            if row[field] != parts["intake"][field]:
                raise ValueError(f"{role}: in-source task binding mismatch")
    # Sign canonical *entire event rows*, not only the event ID / timestamp.
    # Otherwise unrelated metadata could be replaced after signature issuance
    # while preserving the fields the original v1 protocol did check.
    if parts["s1"]["source_event_sha256"] != digest(canonical(s1)):
        raise ValueError("S1 source event content hash mismatch")
    if parts["bus"]["source_event_sha256"] != digest(canonical(bus)):
        raise ValueError("Bus source event content hash mismatch")
    if s1["timestamp"] is None:
        raise ValueError("S1 source event lacks timestamp needed for join")
    if _time(parts["s1"]["observed_at"]) != _time(s1["timestamp"]):
        raise ValueError("S1 attested event time does not match source")
    if _time(parts["bus"]["observed_at"]) != _time(bus["timestamp"]):
        raise ValueError("Bus attested event time does not match source")
    origin = _time(parts["intake"]["issued_at"])
    if origin > _time(s1["timestamp"]) or origin > _time(bus["timestamp"]):
        raise ValueError("intake registration occurs after source event")
    return {
        "correlation_id": parts["intake"]["correlation_id"],
        "s1_event_id": parts["s1"]["event_id"],
        "bus_event_id": parts["bus"]["event_id"],
    }


def audit(s1_path, bus_path, *, proofs=None, keys=None):
    watch, watch_digest = _source(s1_path, "S1", WATCH_FIELDS, WATCH_SCHEMA)
    bus, bus_digest = _source(bus_path, "Bus", BUS_FIELDS, BUS_SCHEMA)
    watch_traces = {x["task_trace_id"] for x in watch}
    bus_identifiers = {
        str(row[key]) for row in bus for key in ("trace_id", "task_id", "run_id", "event_id")
        if row[key] is not None
    }
    unverified_overlap = len(watch_traces & bus_identifiers)
    # Even exact collisions are not trustworthy: the namespaces, HMAC salts,
    # subject origins and actor identity are not jointly authenticated.
    verified = []
    if proofs is not None:
        if keys is None:
            raise ValueError("cannot verify supplied proof without private role keys")
        used_tokens, s1_events, bus_events = set(), set(), set()
        watch_by = {x["event_id"]: x for x in watch}
        bus_by = {x["event_id"]: x for x in bus}
        for proof in proofs:
            claim = verify_proof(proof, watch_by, bus_by, keys)
            if (claim["correlation_id"] in used_tokens or
                    claim["s1_event_id"] in s1_events or
                    claim["bus_event_id"] in bus_events):
                raise ValueError("duplicate or replayed task event join")
            used_tokens.add(claim["correlation_id"])
            s1_events.add(claim["s1_event_id"])
            bus_events.add(claim["bus_event_id"])
            verified.append(claim)
    return {
        "protocol": PROTOCOL,
        "s1_source_sha256": watch_digest,
        "bus_source_sha256": bus_digest,
        "n_s1_events": len(watch),
        "n_s1_pseudonymous_trace_ids": len(watch_traces),
        "n_bus_message_events": len(bus),
        "n_bus_actor_identity_verified": sum(x["actor_identity_verified"] for x in bus),
        "n_s1_events_with_origin_binding": sum(x["schema"] == WATCH_BOUND_SCHEMA for x in watch),
        "n_bus_events_with_origin_binding": sum(x["schema"] == BUS_BOUND_SCHEMA for x in bus),
        "n_exact_id_overlaps_untrusted": unverified_overlap,
        "n_submitted_dual_proofs": len(proofs) if proofs is not None else 0,
        "n_verified_s1_bus_event_joins": len(verified),
        "real_user_deadline_verified": None,
        "independent_agent_task_outcome_verified": None,
        "affectcontrol_treatment_verified": None,
        "evidence_level": "E1-cross-source-join-readiness-only",
        "warning": (
            "Exact string identity and temporal proximity cannot prove a join. "
            "Only origin-bound source events and separately signed intake/S1/Bus attestations bound to "
            "full source event content are admissible. HMAC is symmetric: keys require "
            "separate trusted custody; this prototype is not an audited "
            "production identity/authorization layer. A verified join "
            "still does not prove task success, actual deadline or policy effect."
        ),
    }


def _read_proofs(path):
    raw = Path(path).read_bytes()
    if not raw or len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("invalid proof file")
    records = []
    for i, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid proof on line {i}") from exc
        if len(records) > MAX_RECORDS:
            raise ValueError("too many attestation proofs")
    if not records:
        raise ValueError("no proof rows")
    return records


def _keys_from_env():
    keys = {}
    for role in SIGNABLE:
        value = os.environ.get("AFFECTCONTROL_JOIN_" + role.upper() + "_KEY_HEX")
        if value is None:
            raise ValueError("missing one of the three private role keys")
        try:
            keys[role] = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("attestation key is not hex encoded") from exc
    return keys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s1-watch", required=True)
    parser.add_argument("--bus", required=True)
    parser.add_argument("--proofs", help="optional private JSONL attestation proofs")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = audit(
        args.s1_watch, args.bus,
        proofs=_read_proofs(args.proofs) if args.proofs else None,
        keys=_keys_from_env() if args.proofs else None,
    )
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(dest, (json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({
        "s1_events": result["n_s1_events"],
        "bus_events": result["n_bus_message_events"],
        "verified_bus_actors": result["n_bus_actor_identity_verified"],
        "verified_joins": result["n_verified_s1_bus_event_joins"],
        "evidence_level": result["evidence_level"],
    }, indent=2))


if __name__ == "__main__":
    main()
