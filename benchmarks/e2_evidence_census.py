"""Fail-closed, aggregate-only census of real Agent task evidence availability.

Reads existing pseudonymous status streams and Agent eval summaries. Never
converts events to independent tasks, assumes cross-system pseudonyms join,
or treats self-reported test success as independently judged acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from benchmarks.capture_execution import _write_exclusive

WATCH_FIELDS = frozenset({
    "captured_utc", "event_id", "event_type", "kind",
    "observed_fingerprint", "schema", "source_table",
    "task_trace_id", "timestamp", "transport_or_task_status",
    "verified_acceptance",
})
SHADOW_FIELDS = frozenset({
    "acceptance_verified", "agent", "event_id", "event_type",
    "parent_event_id", "reported_status", "schema", "source",
    "source_record_id", "source_table", "task_linked", "test_evidence",
    "timestamp", "token_usage", "tool_arguments", "tool_name", "trace_id",
})
MAX_BYTES = 20_000_000
MAX_ROWS = 100_000
REQUIRED_PAIRED = frozenset({
    "task_id", "arm", "model", "seed", "passed", "workflow_complete",
    "verified_by", "wall_seconds",
})


def _rows(path: str | Path, label: str):
    path = Path(path)
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError(f"{label}: invalid or excessive input bytes")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: invalid UTF-8") from exc
    rows = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if len(rows) >= MAX_ROWS:
            raise ValueError(f"{label}: too many rows")
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label}: invalid JSON line {i}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{label}: non-object line {i}")
        rows.append(obj)
    if not rows:
        raise ValueError(f"{label}: no records")
    return rows, hashlib.sha256(raw).hexdigest()


def _check_id(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}: missing pseudonymous ID")


def watch_census(path: str | Path):
    rows, digest = _rows(path, "S1 watcher")
    seen = set()
    traces = set()
    events = Counter()
    for row in rows:
        if set(row) != WATCH_FIELDS:
            raise ValueError("S1 watcher: unexpected fields, possibly raw/private data")
        if row["schema"] != "agent-eval/s1-watch-v1":
            raise ValueError("S1 watcher: unsupported schema")
        _check_id(row["event_id"], "event_id")
        _check_id(row["task_trace_id"], "task_trace_id")
        if row["event_id"] in seen:
            raise ValueError("S1 watcher: revisions require separate bitemporal handling")
        if type(row["verified_acceptance"]) is not bool:
            raise ValueError("S1 watcher: invalid acceptance flag")
        seen.add(row["event_id"])
        traces.add(row["task_trace_id"])
        events[row["event_type"]] += 1
    return {
        "source_sha256": digest,
        "n_events": len(rows), "n_distinct_trace_ids": len(traces),
        "n_flagged_verified_acceptance": sum(r["verified_acceptance"] for r in rows),
        "n_independently_adjudicated_task_outcomes": None,
        "n_natural_user_deadlines": 0,
        "n_verified_cross_system_joins": None,
        "n_missing_event_timestamps": sum(r["timestamp"] is None for r in rows),
        "event_type_counts": dict(sorted(events.items())),
        "source_type": "real-pseudonymous-status-events",
    }


def shadow_census(path: str | Path):
    rows, digest = _rows(path, "S1 shadow")
    traces = set()
    for row in rows:
        if set(row) != SHADOW_FIELDS:
            raise ValueError("S1 shadow: unexpected fields, possibly raw/private data")
        _check_id(row["trace_id"], "trace_id")
        if type(row["task_linked"]) is not bool:
            raise ValueError("S1 shadow: invalid task link flag")
        traces.add(row["trace_id"])
    return {
        "source_sha256": digest,
        "n_events": len(rows), "n_distinct_trace_ids": len(traces),
        "n_task_linked_flags": sum(r["task_linked"] for r in rows),
        "n_records_with_test_evidence": sum(r["test_evidence"] is not None for r in rows),
        "n_records_with_nonnull_acceptance": sum(r["acceptance_verified"] is not None for r in rows),
        "n_independently_adjudicated_task_outcomes": None,
        "n_natural_user_deadlines": 0,
        "n_verified_cross_system_joins": None,
        "source_type": "real-pseudonymous-shadow-events",
    }


def paired_census(paths: list[str | Path]):
    if not paths:
        raise ValueError("Agent eval: no paired summary sources")
    hashes = []
    rows = []
    for path in paths:
        chunk, digest = _rows(path, "Agent eval")
        hashes.append(digest)
        rows.extend(chunk)
    keys = set()
    for row in rows:
        if not REQUIRED_PAIRED.issubset(row):
            raise ValueError("Agent eval: missing required fields")
        for field in ("task_id", "model", "arm", "verified_by"):
            _check_id(row[field], field)
        if type(row["passed"]) is not bool or type(row["workflow_complete"]) is not bool:
            raise ValueError("Agent eval: malformed status")
        key = (row["task_id"], row["model"], row["seed"], row["arm"])
        if key in keys:
            raise ValueError("Agent eval: duplicate task/model/arm/seed")
        keys.add(key)
    return {
        "source_sha256": hashes,
        "n_run_summaries": len(rows),
        "n_test_passed_flags": sum(row["passed"] for row in rows),
        "n_workflow_complete_flags": sum(row["workflow_complete"] for row in rows),
        "n_self_reported_independent_tests": sum(
            row["verified_by"] == "independent_tests" for row in rows),
        "n_independently_adjudicated_task_outcomes": None,
        "n_natural_user_deadlines": 0,
        "n_verified_cross_system_joins": None,
        "source_type": "agent-run-summaries-not-a-task-oracle",
    }


def census(watch, shadow, paired):
    a = watch_census(watch)
    b = shadow_census(shadow)
    c = paired_census(paired)
    return {
        "protocol": "affectcontrol-e2-evidence-readiness-census-v1",
        "sources": {
            "s1_watch": a, "s1_shadow": b, "agent_eval": c,
        },
        "e2_ready_episodes_demonstrated": 0,
        "e2_required_fields": [
            "source-authenticated-user-request-with-arrival-time",
            "naturally-observed-task-deadline-and-original-evidence",
            "execution-events-linked-by-verified-nonforgable-identifier",
            "outcome-verified-independently-from-executor",
            "multiple-independent-task-lineages",
            "prospectively-frozen-comparison-allocation-or-logged-action-propensities",
        ],
        "gates_failed": [
            "no-grounded-natural-task-deadlines",
            "no-independent-agent-task-outcome-oracle",
            "no-trusted-s1-to-bus-task-identity-join",
            "no-prospective-randomized-comparator-evidence",
        ],
        "source_event_counts_are_not_independent_episodes": True,
        "evidence_level": "E1",
        "warning": (
            "No cross-system joins are attempted. Hashes are source-copy "
            "integrity checks, not independently signed attestations. "
            "Agent test pass and workflow complete are self-reported. "
            "All results aggregate-only; no raw task content is emitted."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--s1-watch", required=True)
    p.add_argument("--s1-shadow", required=True)
    p.add_argument("--paired", nargs="+", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    result = census(a.s1_watch, a.s1_shadow, a.paired)
    target = Path(a.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(target, (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode())
    print(json.dumps({
        "s1_events": result["sources"]["s1_watch"]["n_events"],
        "shadow_events": result["sources"]["s1_shadow"]["n_events"],
        "agent_eval_runs": result["sources"]["agent_eval"]["n_run_summaries"],
        "e2_ready_episodes_demonstrated": 0,
        "gates_failed": result["gates_failed"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
