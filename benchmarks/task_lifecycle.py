"""Opt-in, research-only task lifecycle ledger linked to real process receipts.

Each state transition is appended with a SHA-256 chain and monotonic timestamp.
This supports observational run/pause/resume evidence, NOT CPU-utilization,
human acceptance, randomized treatment, or AffectControl efficacy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from benchmarks.capture_execution import _safe_id, _write_exclusive, _sha

SCHEMA = "affectcontrol-task-lifecycle-v1"
KINDS = ("start", "pause", "resume", "finish", "fail", "check")
INITIAL = {"start"}
TRANSITIONS = {
    "start": {"pause", "finish", "fail"},
    "pause": {"resume"},
    "resume": {"pause", "finish", "fail"},
    "finish": {"check"},
    "fail": {"check"},
    "check": set(),
}
PHASE_END = {"pause", "finish", "fail", "check"}
RAW_KEYS = frozenset({
    "schema", "task_id", "lineage_id", "sequence", "kind",
    "monotonic_ns", "observed_utc", "previous_sha256",
    "receipt_id", "receipt_sha256", "event_sha256",
})


def _json(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode()


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("observed_utc must be a string")
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("bad ISO timestamp") from exc
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("timezone required")
    return ts


def audit(data: bytes, *, receipts_root=None):
    """Verify chain, transitions and receipt hashes, hiding all task IDs."""
    lines = data.decode("utf-8").splitlines()
    events = []
    previous = None
    task_id = lineage_id = None
    last_clock = None
    active_start = None
    paused_start = None
    active_ns = paused_ns = 0
    receipts_verified = 0
    used_receipts = set()
    observed_successes = 0
    checks_passed = 0
    for index, line in enumerate(lines):
        if not line.strip():
            raise ValueError("blank line in immutable ledger")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid ledger JSON") from exc
        if not isinstance(row, dict) or set(row) != RAW_KEYS or row["schema"] != SCHEMA:
            raise ValueError("unexpected ledger schema/fields")
        _safe_id(row["task_id"], "task_id")
        _safe_id(row["lineage_id"], "lineage_id")
        if task_id is None:
            task_id, lineage_id = row["task_id"], row["lineage_id"]
        if (row["task_id"], row["lineage_id"]) != (task_id, lineage_id):
            raise ValueError("task/lineage changed within ledger")
        if type(row["sequence"]) is not int or row["sequence"] != index + 1:
            raise ValueError("invalid sequence number")
        kind = row["kind"]
        if kind not in KINDS:
            raise ValueError("unknown lifecycle event")
        if kind not in (INITIAL if not events else TRANSITIONS[events[-1]["kind"]]):
            raise ValueError("invalid lifecycle transition")
        moment = row["monotonic_ns"]
        if type(moment) is not int or moment < 0 or (last_clock is not None and moment < last_clock):
            raise ValueError("monotonic clock went backward")
        _timestamp(row["observed_utc"])
        if row["previous_sha256"] != previous:
            raise ValueError("broken ledger hash chain")
        digest = row["event_sha256"]
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("invalid event digest")
        computed = _sha(_json({k: v for k, v in row.items() if k != "event_sha256"}))
        if computed != digest:
            raise ValueError("event content hash mismatch")
        receipt_id, receipt_sha = row["receipt_id"], row["receipt_sha256"]
        if kind in PHASE_END:
            _safe_id(receipt_id, "receipt_id")
            if receipt_id in used_receipts:
                raise ValueError("same receipt reused across phases or local check")
            used_receipts.add(receipt_id)
            if not isinstance(receipt_sha, str) or len(receipt_sha) != 64:
                raise ValueError("receipt hash required")
            if receipts_root is not None:
                base = Path(receipts_root).resolve()
                if (base / "receipts").is_symlink():
                    raise ValueError("linked receipt directory must not be symlinked")
                path = base / "receipts" / f"{receipt_id}.json"
                if path.is_symlink() or not path.is_file() or path.resolve().parent != (base / "receipts").resolve():
                    raise ValueError("missing or redirected receipt")
                raw = path.read_bytes()
                if _sha(raw) != receipt_sha:
                    raise ValueError("linked process receipt modified")
                receipt = json.loads(raw)
                if receipt.get("session_id") != receipt_id or receipt.get("lineage_id") != lineage_id:
                    raise ValueError("linked process receipt belongs to different session/lineage")
                if receipt.get("schema") != "affectcontrol-local-observation-v1":
                    raise ValueError("unknown process receipt")
                receipts_verified += 1
                if kind in ("pause", "finish") and (
                        receipt.get("result") != "exited" or receipt.get("exit_code") != 0):
                    raise ValueError("successful phase event needs a successful linked process")
                if kind == "check":
                    checks_passed += receipt.get("result") == "exited" and receipt.get("exit_code") == 0
                else:
                    observed_successes += receipt.get("result") == "exited" and receipt.get("exit_code") == 0
        elif receipt_id is not None or receipt_sha is not None:
            raise ValueError("unexpected receipt on start/resume")
        # The controller clock measures intervals between event emissions.
        # Do not confuse with actively consuming CPU or Agent execution.
        if kind in ("start", "resume"):
            if paused_start is not None:
                paused_ns += moment - paused_start
                paused_start = None
            active_start = moment
        elif kind in ("pause", "finish", "fail"):
            active_ns += moment - active_start
            active_start = None
            if kind == "pause":
                paused_start = moment
        last_clock = moment
        previous = digest
        events.append({"kind": kind})
    if not events:
        raise ValueError("empty lifecycle ledger")
    final_kind = events[-1]["kind"]
    completed = final_kind in ("finish", "fail", "check")
    return {
        "protocol": SCHEMA,
        "n_lifecycle_events": len(events),
        "n_work_phases": sum(x["kind"] in ("pause", "finish", "fail") for x in events),
        "n_pauses": sum(x["kind"] == "pause" for x in events),
        "terminal_state_recorded": completed,
        "terminal_kind": next((x["kind"] for x in reversed(events)
                              if x["kind"] in ("finish", "fail")), None),
        "controller_observed_running_s": active_ns / 1e9 if completed else None,
        "controller_observed_paused_s": paused_ns / 1e9 if completed else None,
        "receipt_links_verified": receipts_verified if receipts_root is not None else None,
        "n_phase_exit_zero": observed_successes if receipts_root is not None else None,
        "n_local_checks_exit_zero": checks_passed if receipts_root is not None else None,
        "independent_task_acceptance": None,
        "causal_scheduler_benefit": None,
        "ledger_final_sha256": previous,
        "evidence_level": "E1-research-instrumentation",
        "warning": (
            "Controller-observed running intervals include command startup, blocking and "
            "I/O; they do not establish CPU work time. Exit code zero or a separate local "
            "check is NOT independently verified acceptance. This ledger has no independent "
            "signature and cannot prove causal scheduling benefit."
        ),
    }


def append(root, task_id, lineage_id, kind, *, receipt_id=None):
    """Append one event, never replace an existing ledger or rerun a command."""
    task_id = _safe_id(task_id, "task_id")
    lineage_id = _safe_id(lineage_id, "lineage_id")
    if kind not in KINDS:
        raise ValueError("unknown lifecycle event")
    root = Path(root).resolve()
    child = root / "lifecycles"
    if child.is_symlink():
        raise ValueError("lifecycle directory must not be symlinked")
    child.mkdir(parents=True, exist_ok=True)
    filename = child / f"{task_id}.jsonl"
    if filename.is_symlink():
        raise ValueError("lifecycle file must not be symlinked")
    old = filename.read_bytes() if filename.exists() else b""
    if old:
        audit(old, receipts_root=root)
        last = json.loads(old.splitlines()[-1])
        if (last["task_id"], last["lineage_id"]) != (task_id, lineage_id):
            raise ValueError("lineage mismatch")
        if kind not in TRANSITIONS[last["kind"]]:
            raise ValueError("invalid lifecycle transition")
    elif kind != "start":
        raise ValueError("first lifecycle event must be start")
    receipt_sha = None
    if kind in PHASE_END:
        if (root / "receipts").is_symlink():
            raise ValueError("receipt directory must not be symlinked")
        receipt_id = _safe_id(receipt_id, "receipt_id")
        path = root / "receipts" / f"{receipt_id}.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("linked receipt missing")
        raw = path.read_bytes()
        receipt = json.loads(raw)
        if receipt.get("lineage_id") != lineage_id or receipt.get("session_id") != receipt_id:
            raise ValueError("linked receipt identity mismatch")
        if receipt.get("schema") != "affectcontrol-local-observation-v1":
            raise ValueError("invalid receipt type")
        if kind in ("pause", "finish") and (
                receipt.get("result") != "exited" or receipt.get("exit_code") != 0):
            raise ValueError("successful phase event needs a successful linked process")
        receipt_sha = _sha(raw)
    elif receipt_id is not None:
        raise ValueError("unexpected receipt on start/resume")
    record = {
        "schema": SCHEMA,
        "task_id": task_id,
        "lineage_id": lineage_id,
        "sequence": (last["sequence"] + 1) if old else 1,
        "kind": kind,
        "monotonic_ns": time.perf_counter_ns(),
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "previous_sha256": last["event_sha256"] if old else None,
        "receipt_id": receipt_id,
        "receipt_sha256": receipt_sha,
    }
    record["event_sha256"] = _sha(_json(record))
    new_line = _json(record) + b"\n"
    if old:
        # Single-controller prototype. Hash chain detects accidental
        # concurrent collisions, but is not a cross-process transaction.
        with filename.open("ab") as stream:
            stream.write(new_line)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        _write_exclusive(filename, new_line)
    return audit(filename.read_bytes(), receipts_root=root)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--lineage-id", required=True)
    p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--receipt-id")
    a = p.parse_args()
    print(json.dumps(append(a.root, a.task_id, a.lineage_id, a.kind,
                            receipt_id=a.receipt_id), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
