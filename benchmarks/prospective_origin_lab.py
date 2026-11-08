"""Real local subprocess + *staging* origin-bound event lifecycle pilot.

This is opt-in, local only: not connected to Sage Bus or production S1.
The single lab controller holds all three EPHEMERAL test-only HMAC keys,
so passing this test does NOT establish independent production key custody.
No task deadlines, human acceptance, or policy causality are inferred.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import secrets
import sys

from benchmarks.capture_execution import _write_exclusive, capture
from benchmarks.s1_bus_join_gate import (
    PROTOCOL, WATCH_BOUND_SCHEMA, BUS_BOUND_SCHEMA, audit, canonical,
    digest, sign,
)

LAB_SCHEMA = "affectcontrol-staging-origin-bound-live-subprocess-v1"
TASK_MODULE = "tests/test_core.py"


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def save_json(path: Path, payload):
    _write_exclusive(path, (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode())


def save_jsonl(path: Path, payload):
    _write_exclusive(path, canonical(payload) + b"\n")


def envelope(role, value, secret):
    return {**value, "signature": sign(role, value, secret)}


def _keys(path):
    data = json.loads(path.read_bytes())
    if set(data) != {"schema", "roles"} or data["schema"] != "test-only-local-hmac-key-material":
        raise ValueError("not the staging key file")
    roles = {r: bytes.fromhex(data["roles"][r]) for r in ("intake", "s1", "bus")}
    if len(set(roles.values())) != 3 or any(len(k) != 32 for k in roles.values()):
        raise ValueError("invalid test key material")
    return roles


def verify(root):
    """Re-evaluate immutable staged source events and actual process receipt."""
    root = Path(root).resolve()
    keys = _keys(root / "lab-only-keys.json")
    registration = json.loads((root / "intake.json").read_bytes())
    proof = json.loads((root / "proof.json").read_bytes())
    receipt_file = root / "execution" / "receipts" / "lab-process-1.json"
    raw = receipt_file.read_bytes()
    receipt = json.loads(raw)
    s1 = json.loads((root / "s1-events.jsonl").read_bytes())
    bus = json.loads((root / "bus-events.jsonl").read_bytes())
    if registration.get("schema") != LAB_SCHEMA:
        raise ValueError("invalid lab registration")
    if registration.get("runner_source_sha256") != digest(Path(__file__).read_bytes()):
        raise ValueError("staging runner source bytes do not match original pilot")
    if registration.get("correlation_id") != proof["intake"]["correlation_id"]:
        raise ValueError("source registration token mismatch")
    if registration.get("request_sha256") != proof["intake"]["request_sha256"]:
        raise ValueError("source request digest mismatch")
    if registration.get("original_user_deadline") is not None:
        raise ValueError("no real user deadline is available in lab")
    if registration.get("independent_business_acceptance") is not None:
        raise ValueError("no independent acceptance in lab")
    if s1["correlation_id"] != registration["correlation_id"] or bus["correlation_id"] != registration["correlation_id"]:
        raise ValueError("original event correlation mismatch")
    if s1["observed_fingerprint"] != digest(raw) or bus["evidence_sha256"] != digest(raw):
        raise ValueError("source events do not match the real process receipt bytes")
    if receipt.get("session_id") != "lab-process-1":
        raise ValueError("wrong observed process receipt")
    if receipt.get("deadline_basis") != "none" or receipt.get("oracle_status") != "exit-code-only-not-independent-adjudication":
        raise ValueError("process receipt claiming nonexistent acceptance or deadline")
    if registration["source_commit"] != receipt["lineage_id"].split("lab-")[-1]:
        raise ValueError("source commit and local lineage mismatch")
    result = audit(root / "s1-events.jsonl", root / "bus-events.jsonl",
                   proofs=[proof], keys=keys)
    if result["n_verified_s1_bus_event_joins"] != 1:
        raise ValueError("origin-bound staging join failed")
    return {
        "protocol": LAB_SCHEMA,
        "real_process": True,
        "process_exit_zero": receipt["result"] == "exited" and receipt["exit_code"] == 0,
        "one_origin_bound_join_verified": True,
        "actual_production_s1_bus_joins": None,
        "independent_human_task_acceptance": None,
        "naturally_observed_user_deadline": None,
        "causal_scheduler_effect": None,
        "trust_separation": "not_met_single_local_lab_controller_has_all_test_keys",
        "evidence_level": "E1-isolated-source-writer-exercise-only",
    }


def run(repo, root):
    repo = Path(repo).resolve()
    root = Path(root)
    if not (repo / TASK_MODULE).is_file() or not (repo / "pyproject.toml").is_file():
        raise ValueError("not the research repository")
    if root.exists():
        raise FileExistsError("pilot output exists; refuse overwrite/re-execution")
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    # Record task intent and a full original git SHA BEFORE executing anything.
    import subprocess
    source_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True, timeout=10
    ).strip()
    if len(source_sha) != 40:
        raise ValueError("unverifiable research source commit")
    token = secrets.token_hex(32)
    request = {
        "source_commit": source_sha,
        "purpose": "Run safe existing repository unit tests in a local-only pilot",
        "approved_test_module": TASK_MODULE,
        "user_task": False,
    }
    request_hash = digest(canonical(request))
    now = utc()
    registration = {
        "schema": LAB_SCHEMA, "correlation_id": token,
        "request_sha256": request_hash, "issued_at": now,
        "source_commit": source_sha,
        "runner_source_sha256": digest(Path(__file__).read_bytes()),
        "original_user_deadline": None,
        "independent_business_acceptance": None,
    }
    keys = {role: secrets.token_bytes(32) for role in ("intake", "s1", "bus")}
    save_json(root / "lab-only-keys.json", {
        "schema": "test-only-local-hmac-key-material",
        "roles": {role: value.hex() for role, value in keys.items()},
    })
    save_json(root / "intake.json", registration)
    intake = envelope("intake", {
        "correlation_id": token, "request_sha256": request_hash,
        "issued_at": now,
    }, keys["intake"])
    # This executes a real OS subprocess; the stdout/stderr stays hashed.
    receipt = capture(
        root / "execution", "lab-process-1", "lab-" + source_sha,
        [sys.executable, "-m", "pytest", "-q", TASK_MODULE],
        cwd=repo, timeout_s=45.0,
    )
    receipt_raw = (root / "execution" / "receipts" / "lab-process-1.json").read_bytes()
    receipt_hash = digest(receipt_raw)
    # TWO staging *source-format* event records. These are not events from
    # live Sage Bus or live S1, even though their schema matches a planned
    # prospective protocol. Do not promote to production attribution.
    s1_event = {
        "schema": WATCH_BOUND_SCHEMA, "correlation_id": token,
        "request_sha256": request_hash,
        "captured_utc": utc(), "event_id": "lab-s1-" + secrets.token_hex(8),
        "event_type": "local-verification-process-ended", "kind": "first_seen",
        "observed_fingerprint": receipt_hash, "source_table": "isolated-lab",
        "task_trace_id": "staging-observed-process",
        "timestamp": utc(), "transport_or_task_status": receipt["result"],
        "verified_acceptance": False,
    }
    save_jsonl(root / "s1-events.jsonl", s1_event)
    bus_event = {
        "schema": BUS_BOUND_SCHEMA, "correlation_id": token,
        "request_sha256": request_hash,
        "trace_id": "staging-observed-process", "task_id": "lab-process-1",
        "run_id": "isolated-lab", "event_id": "lab-bus-" + secrets.token_hex(8),
        "agent_id": "staging-source-reporter", "event_type": "lab-process-receipt",
        "timestamp": utc(), "parent_event_ids": [], "unresolved_reply_to": None,
        "bus_type": "lab-report", "bus_status_at_capture": receipt["result"],
        "content_length": 0, "evidence_ref": "local-only-process-receipt",
        "evidence_sha256": receipt_hash, "provenance": "test-only-local",
        "payload_captured": False,
        "actor_identity_verified": True,  # verified local lab role, NOT real Bus actor
        "model_tool_calls_observed": False,
    }
    save_jsonl(root / "bus-events.jsonl", bus_event)
    proof = {
        "schema": PROTOCOL, "intake": intake,
        "s1": envelope("s1", {
            "correlation_id": token, "request_sha256": request_hash,
            "event_id": s1_event["event_id"], "observed_at": s1_event["timestamp"],
            "source_event_sha256": digest(canonical(s1_event)),
        }, keys["s1"]),
        "bus": envelope("bus", {
            "correlation_id": token, "request_sha256": request_hash,
            "event_id": bus_event["event_id"], "observed_at": bus_event["timestamp"],
            "source_event_sha256": digest(canonical(bus_event)),
        }, keys["bus"]),
    }
    save_json(root / "proof.json", proof)
    status = verify(root)
    save_json(root / "verification.json", status)
    return status


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    q = sub.add_parser("run")
    q.add_argument("--repo", default=".")
    q.add_argument("--root", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--root", required=True)
    a = p.parse_args()
    result = run(a.repo, a.root) if a.action == "run" else verify(a.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
