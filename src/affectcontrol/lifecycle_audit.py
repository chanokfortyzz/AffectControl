"""Read-only task lineage cross-check of Sage observational exports.

Counts what records actually say, not whether an agent fulfilled a goal.
Does not emit raw task IDs, contents or user identifiers.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_ROW_BYTES = 256 * 1024
REVIEW_EVENT = "review-passed"
TERMINAL_EVENT_KINDS = frozenset({"task-finished", "task-finished-by-lease"})
VALID_KINDS = frozenset({
    "task-packaged", "task-claimed", "task-finished", "task-finished-by-lease",
    "review-passed", "task-reopened-for-retry", "finish-rejected",
    "claim-rejected", "route-decided", "route-stamp-consumed", "stale-claim",
    "executor-fallback", "local-worker-claim", "local-worker-finished",
    "resume-needed",
})


def audit(path):
    source = Path(path)
    if not source.is_file():
        raise ValueError("source not found")
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("source too large")
    sha = hashlib.sha256()
    event_counts = Counter()
    lineage = defaultdict(Counter)
    task_type = defaultdict(set)
    source_records = 0
    unlabeled = 0
    not_event = 0
    missing_kind = 0
    for num, raw in enumerate(source.open("rb"), 1):
        sha.update(raw)
        if len(raw) > MAX_ROW_BYTES:
            raise ValueError(f"line {num} exceeds size limit")
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise ValueError(f"line {num}: invalid JSON") from error
        if not isinstance(row, dict):
            raise ValueError(f"line {num}: expected object")
        source_records += 1
        kind = row.get("kind")
        if kind == "state_snapshot":
            not_event += 1
            continue
        if not isinstance(kind, str) or kind not in VALID_KINDS:
            missing_kind += 1
            continue
        event_counts[kind] += 1
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            unlabeled += 1
            continue
        lineage[task_id][kind] += 1
        if isinstance(row.get("task_type"), str):
            task_type[task_id].add(row["task_type"])
    if source_records == 0:
        raise ValueError("empty input")
    count = len(lineage)
    both = sum(c[REVIEW_EVENT] > 0 and any(c[e] > 0 for e in TERMINAL_EVENT_KINDS)
               for c in lineage.values())
    term = sum(any(c[e] > 0 for e in TERMINAL_EVENT_KINDS) for c in lineage.values())
    reviews = sum(c[REVIEW_EVENT] > 0 for c in lineage.values())
    retry = sum(c["task-reopened-for-retry"] > 0 for c in lineage.values())
    lease_only = sum(c["task-finished-by-lease"] > 0 and c["task-finished"] == 0
                     for c in lineage.values())
    return {
        "mode": "read_only_lifecycle_audit",
        "dispatch_allowed": False,
        "production_decision": "NOT_APPROVED",
        "source_sha256": sha.hexdigest(),
        "source_bytes": source.stat().st_size,
        "rows": source_records,
        "snapshot_rows_excluded_from_event_lineage": not_event,
        "recognized_event_counts": dict(sorted(event_counts.items())),
        "unknown_or_unrecognized_kind_rows": missing_kind,
        "recognized_event_rows_without_task_id": unlabeled,
        "task_lineages_with_events": count,
        "tasks_with_recorded_terminal_event": term,
        "tasks_with_recorded_review_passed": reviews,
        "tasks_with_both_terminal_event_and_review_marker": both,
        "tasks_with_retry_event": retry,
        "tasks_with_lease_terminal_without_explicit_finish": lease_only,
        "independently_verified_successes": 0,
        "interpretation": [
            "event markers are from a single observational source, not independent verification",
            "lease-finished and review-passed do not prove goal completion",
            "task counts are distinct IDs only inside recognized event records; snapshots have different anonymity grain",
            "absence of event kind is not proof the event did not occur",
            "this report cannot compute task success rates, task deadlines or interruption labels",
            "never use lineage counts as AffectControl performance evidence",
        ],
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description="Read-only Sage task-event lineage audit")
    cli.add_argument("--input", required=True)
    options = cli.parse_args(argv)
    try:
        print(json.dumps(audit(options.input), indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
