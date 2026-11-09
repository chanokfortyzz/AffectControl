"""Audit actual local-process receipts and create a conservative trace manifest.

Receipts are observation-only. No deadlines or interruption labels are
invented. Only local root files are opened; output is create-only.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

from affectcontrol.trace_validation import validate_trace
from benchmarks.capture_execution import _SAFE_ID, _write_exclusive, _sha


def build_observation_manifest(root: str | Path) -> tuple[dict, ...]:
    root = Path(root).expanduser().resolve()
    folder = root / "receipts"
    if not folder.is_dir():
        raise ValueError("no receipt directory")
    entries = []
    excluded_outcomes = []
    session_ids = set()
    files = sorted(folder.glob("*.json"))
    if not files:
        raise ValueError("no finalized receipts")
    for item in files:
        if item.is_symlink() or item.resolve().parent != folder.resolve():
            raise ValueError("receipt path is not a local regular file")
        receipt = json.loads(item.read_text(encoding="utf-8"))
        if receipt.get("schema") != "affectcontrol-local-observation-v1":
            raise ValueError("unrecognized receipt schema")
        sid = receipt.get("session_id")
        lineage = receipt.get("lineage_id")
        if not isinstance(sid, str) or not _SAFE_ID.fullmatch(sid):
            raise ValueError("invalid session_id")
        if not isinstance(lineage, str) or not _SAFE_ID.fullmatch(lineage):
            raise ValueError("invalid lineage_id")
        if item.stem != sid or sid in session_ids:
            raise ValueError("filename/session identifier mismatch or duplicate")
        session_ids.add(sid)
        if receipt.get("duration_basis") != "wallclock_proxy":
            raise ValueError("unverified duration basis")
        if receipt.get("deadline_basis") != "none":
            raise ValueError("collector did not observe a deadline")
        if receipt.get("source") != "local-process:opt-in":
            raise ValueError("unexpected source")
        if receipt.get("result") not in ("exited", "timed_out", "launch_error"):
            raise ValueError("unrecognized process outcome")
        if receipt["result"] != "exited":
            excluded_outcomes.append((sid, receipt["result"]))
        start, end = receipt.get("start_utc"), receipt.get("end_utc")
        for field, stamp in [("start_utc", start), ("end_utc", end)]:
            if not isinstance(stamp, str):
                raise ValueError(f"{field} missing")
            dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if dt.utcoffset() is None:
                raise ValueError("timestamps must be timezone-aware")
        if datetime.fromisoformat(end.replace("Z", "+00:00")) < datetime.fromisoformat(start.replace("Z", "+00:00")):
            raise ValueError("time travel in observation")
        trace_file = root / "sessions" / f"{sid}.jsonl"
        if trace_file.is_symlink() or not trace_file.is_file():
            raise ValueError("missing or symlinked session trace")
        raw = trace_file.read_bytes()
        digest = _sha(raw)
        if digest != receipt.get("trace_sha256"):
            raise ValueError("trace no longer matches immutable receipt")
        report = validate_trace(raw)
        if report["n_events"] != 1 or report["n_arrivals"] != 1 or report["n_deadline_events"]:
            raise ValueError("this collector only observes one process without deadline")
        event = json.loads(raw)
        if event["task_id"] != sid:
            raise ValueError("task ID mismatches receipt")
        duration = event["payload"]["duration_s"]
        # Decimal JSON time must agree with receipt (serialized exact float).
        if duration != receipt["duration_wallclock_s"]:
            raise ValueError("duration mismatches receipt")
        if receipt["result"] != "exited":
            continue  # A timeout or launch error has no measured completion duration.
        entries.append({
            "session_id": sid,
            "lineage_id": lineage,
            "trace_file": f"sessions/{sid}.jsonl",
            "sha256": digest,
            "source": "local-process:opt-in",
            "duration_basis": "wallclock_proxy",
            "deadline_basis": "none",
        })
    if not entries:
        raise ValueError("no completed process observations (all censored or launch errors)")
    return tuple(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", help="create-only path to output JSONL manifest")
    args = parser.parse_args()
    rows = build_observation_manifest(args.root)
    output = ("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n").encode()
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_exclusive(path, output)
    else:
        print(output.decode(), end="")


if __name__ == "__main__":
    main()
