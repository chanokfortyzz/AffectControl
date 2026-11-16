"""Bounded JSONL batch ingress for shadow-only AffectControl decisions."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from .pilot import ShadowPilot

ALLOWED = frozenset({"event_id", "task_id", "text", "priority", "immediate"})
MAX_BYTES = 1024 * 1024
MAX_ROWS = 1000


def _validate(row, number, *, allow_immediate=False):
    if not isinstance(row, dict):
        raise ValueError(f"line {number}: expected JSON object")
    unknown = set(row).difference(ALLOWED)
    if unknown:
        raise ValueError(f"line {number}: unsupported fields")
    for k in ("event_id", "task_id", "text"):
        if not isinstance(row.get(k), str):
            raise ValueError(f"line {number}: {k} must be string")
    priority = row.get("priority", "P2")
    if priority not in ("P0", "P1", "P2", "P3"):
        raise ValueError(f"line {number}: priority invalid")
    immediate = row.get("immediate", False)
    if type(immediate) is not bool:
        raise ValueError(f"line {number}: immediate must be bool")
    if immediate and not allow_immediate:
        raise ValueError(
            f"line {number}: explicit immediate requires --allow-explicit-user-immediate")
    return {
        "event_id": row["event_id"], "task_id": row["task_id"],
        "text": row["text"], "priority": priority, "immediate": immediate,
    }


def read_input(path, *, allow_immediate=False):
    p = Path(path)
    if not p.is_file():
        raise ValueError("input JSONL not found")
    if p.stat().st_size > MAX_BYTES:
        raise ValueError("input JSONL exceeds 1 MiB limit")
    content = p.read_bytes()
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError as e:
        raise ValueError("input must be UTF-8") from e
    rows = []
    ids = set()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if len(rows) >= MAX_ROWS:
            raise ValueError("input exceeds 1000 task limit")
        try:
            row = _validate(json.loads(line), number, allow_immediate=allow_immediate)
        except json.JSONDecodeError as e:
            raise ValueError(f"line {number}: invalid JSON") from e
        if row["event_id"] in ids:
            raise ValueError(f"line {number}: duplicate event_id")
        ids.add(row["event_id"])
        rows.append(row)
    if not rows:
        raise ValueError("input is empty")
    return rows, hashlib.sha256(content).hexdigest()


def run(db, input_path, *, output=None, allow_immediate=False):
    rows, source_sha256 = read_input(input_path, allow_immediate=allow_immediate)
    if output is not None:
        source, target = Path(input_path).resolve(), Path(output).resolve()
        dbpath = Path(db).resolve()
        if target == source or target == dbpath:
            raise ValueError("output must not overwrite input or DB")
        if target.exists():
            raise ValueError("output already exists (refusing overwrite)")
    decisions = []
    # Per-row durable transactions. On a crash, retry the exact file:
    # unchanged event IDs replay idempotently. No task is dispatched.
    with ShadowPilot(db) as pilot:
        for number, row in enumerate(rows, 1):
            try:
                decisions.append(pilot.decide(**row))
            except (ValueError, OSError) as e:
                raise ValueError(
                    f"decision {number} failed; prior decisions may be committed; "
                    f"retry with same input: {e}") from e
    encoded = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                      for row in decisions)
    if output is None:
        for line in encoded.splitlines():
            print(line)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation + atomic rename prevents output truncation.
        temp = target.with_name(target.name + f".{os.getpid()}.tmp")
        try:
            with temp.open("x", encoding="utf-8") as f:
                f.write(encoded)
                f.flush()
                os.fsync(f.fileno())
            if target.exists():
                raise ValueError("output exists (concurrent writer)")
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
    return {
        "mode": "shadow", "dispatch_allowed": False,
        "input_sha256": source_sha256, "decisions": len(decisions),
        "output_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "output_path": str(Path(output).resolve()) if output else None,
        "production_decision": "NOT_APPROVED",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="AffectControl bounded shadow JSONL ingress")
    ap.add_argument("--db", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output")
    ap.add_argument("--allow-explicit-user-immediate", action="store_true")
    args = ap.parse_args(argv)
    try:
        report = run(args.db, args.input, output=args.output,
                     allow_immediate=args.allow_explicit_user_immediate)
        print(json.dumps({"batch_report": report}, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
