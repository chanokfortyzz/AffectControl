"""Read-only aggregated coverage audit of existing Sage observational JSONL.

No prompt/body/task identifiers are emitted.  Existing exporter is authoritative.
Never converts archived observations into ground-truth labels or dispatches work.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from .context_gate import normalize_context

MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_LINE_BYTES = 256 * 1024
SNAPSHOT_HINT_FIELDS = (
    "process_alive", "claimed", "packet_status",
    "urgency", "salience", "arousal", "interest", "tension",
    "goal_activation", "appraisal_provider", "appraisal_model",
)
CONTEXT_FIELDS = (
    "current_task_running", "current_task_preemptible", "task_blocked",
    "seconds_until_deadline", "estimated_work_seconds",
)


def audit(path):
    p = Path(path)
    if not p.is_file():
        raise ValueError("source JSONL does not exist")
    if p.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("source JSONL exceeds bounded audit limit")
    sha = hashlib.sha256()
    counts = Counter()
    kinds = Counter()
    known_fields = Counter()
    missing = Counter()
    snapshot_hint_presence = Counter()
    task_ids = set()
    anon_ids = set()
    rows_with_labels = 0
    rows_with_context = 0
    complete = 0
    partial = 0
    recognized_preempt = 0

    with p.open("rb") as stream:
        for number, binary in enumerate(stream, 1):
            sha.update(binary)
            if len(binary) > MAX_LINE_BYTES:
                raise ValueError(f"line {number} exceeds row limit")
            if not binary.strip():
                continue
            try:
                row = json.loads(binary)
            except (ValueError, UnicodeDecodeError) as e:
                raise ValueError(f"line {number} not valid UTF-8 JSON") from e
            if not isinstance(row, dict):
                raise ValueError(f"line {number}: record must be an object")
            counts["rows"] += 1
            if row.get("kind") == "state_snapshot":
                for field in SNAPSHOT_HINT_FIELDS:
                    if field in row and row[field] is not None:
                        snapshot_hint_presence[field] += 1
            kind = row.get("kind")
            if isinstance(kind, str):
                kinds[kind] += 1
                if kind in {"preempt", "cooperative_preempt", "cooperative-preemption"}:
                    recognized_preempt += 1
            for name in CONTEXT_FIELDS:
                if name in row:
                    known_fields[name] += 1
            if "preemptible" in row:
                counts["source_preemptible_rows"] += 1
            if row.get("explicit_override") is True:
                counts["explicit_override_true_rows"] += 1
            if isinstance(row.get("task_id"), str) and row["task_id"]:
                task_ids.add(row["task_id"])
            if isinstance(row.get("anon_task_id"), str) and row["anon_task_id"]:
                anon_ids.add(row["anon_task_id"])
            if ("label_origin" in row and "should_interrupt" in row
                    and row.get("split") == "holdout"):
                rows_with_labels += 1
            ctx = row.get("context")
            if ctx is None:
                # Presence of a generic "preemptible" flag is NOT a proof that
                # the CURRENTLY running task is safely preemptible.
                ctx = {name: row[name] for name in CONTEXT_FIELDS if name in row}
            else:
                rows_with_context += 1
            clean = normalize_context(ctx)
            present = set(clean or {})
            for name in CONTEXT_FIELDS:
                if name not in present:
                    missing[name] += 1
            if len(present) == len(CONTEXT_FIELDS):
                complete += 1
            elif present:
                partial += 1
    n = counts["rows"]
    if not n:
        raise ValueError("source JSONL is empty")
    return {
        "source_sha256": sha.hexdigest(),
        "source_size_bytes": p.stat().st_size,
        "rows": n,
        "kinds": dict(sorted(kinds.items())),
        "distinct_event_task_ids": len(task_ids),
        "distinct_anonymized_snapshot_ids": len(anon_ids),
        "source_preemptible_rows_not_equivalent_to_running_task": counts["source_preemptible_rows"],
        "explicit_override_true_rows": counts["explicit_override_true_rows"],
        "label_shape_claimed_rows_not_independently_verified": rows_with_labels,
        "recognized_preemption_event_kind_rows": recognized_preempt,
        "snapshot_hint_coverage": {
            "snapshot_rows": kinds.get("state_snapshot", 0),
            "non_null_field_rows": dict(sorted(snapshot_hint_presence.items())),
            "warning": "process_alive/claimed describe a source snapshot, not authoritative running-task interrupt permission; urgency is NOT deadline slack",
        },
        "structured_context": {
            "explicit_context_field_rows": rows_with_context,
            "complete_rows": complete,
            "partial_rows": partial,
            "abstain_rows": n - complete,
            "complete_coverage": complete / n,
            "missing_required_fields_rows": dict(sorted(missing.items())),
            "required_fields": list(CONTEXT_FIELDS),
        },
        "caveats": [
            "source metadata is not independently authenticated",
            "preemptible refers to source-record task, not a verified running-task preemption permission",
            "absence of recognized event kind does not prove absence of real-world interruption",
            "labels by self-declared field names are not verified independent ground truth",
            "read-only coverage audit: no scheduler outcome or superiority evidence",
        ],
        "mode": "read_only_audit",
        "dispatch_allowed": False,
        "production_decision": "NOT_APPROVED",
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description="Read-only Sage exporter coverage audit")
    cli.add_argument("--input", required=True)
    args = cli.parse_args(argv)
    try:
        print(json.dumps(audit(args.input), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
