"""Read-only, privacy-preserving audit of S1 pseudonymous shadow events.

Only a allowlisted metadata format is accepted. This analyzes *status event
spans* and coverage, never task work time, human labels, or scheduler effects.
No source IDs or task contents appear in the report.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median

SCHEMA = "agent-eval/s1-watch-v1"
FIELDS = frozenset({
    "captured_utc", "event_id", "event_type", "kind",
    "observed_fingerprint", "schema", "source_table",
    "task_trace_id", "timestamp", "transport_or_task_status",
    "verified_acceptance",
})
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 20_000_000
MAX_RECORDS = 100_000
START = "task_started"
TERMINAL = "task_terminal_reported"


def _time(value, field, *, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be ISO 8601 with timezone")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} invalid ISO 8601 timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} timestamp missing timezone")
    return dt.astimezone(timezone.utc)


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(math.ceil(fraction * len(ordered))) - 1)]


def audit_shadow(path: str | Path) -> dict:
    data = Path(path).read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError("source size exceeds audit limit")
    source_digest = hashlib.sha256(data).hexdigest()
    events = {}
    captures = {}
    duplicate_retries = 0
    revisions = 0
    n_records = 0
    for lineno, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        n_records += 1
        if n_records > MAX_RECORDS:
            raise ValueError("too many source records")
        try:
            r = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON") from exc
        if not isinstance(r, dict) or set(r) != FIELDS:
            raise ValueError(f"line {lineno}: unknown/missing metadata fields (possible raw-content leakage)")
        if r["schema"] != SCHEMA:
            raise ValueError(f"line {lineno}: wrong metadata schema")
        if r["kind"] not in ("first_seen", "metadata_updated"):
            raise ValueError(f"line {lineno}: unknown update kind")
        for field in ("event_id", "task_trace_id", "event_type", "source_table"):
            if not isinstance(r[field], str) or not r[field].strip():
                raise ValueError(f"line {lineno}: invalid {field}")
        if not isinstance(r["observed_fingerprint"], str) or not SHA.fullmatch(r["observed_fingerprint"]):
            raise ValueError(f"line {lineno}: invalid observed fingerprint")
        if type(r["verified_acceptance"]) is not bool:
            raise ValueError(f"line {lineno}: verified_acceptance must be boolean")
        if r["transport_or_task_status"] is not None and not isinstance(r["transport_or_task_status"], str):
            raise ValueError(f"line {lineno}: invalid reported status")
        captured = _time(r["captured_utc"], "captured_utc")
        occurred = _time(r["timestamp"], "timestamp", optional=True)
        event_id = r["event_id"]
        if event_id in events:
            previous = events[event_id]
            if captured < captures[event_id]:
                raise ValueError(f"line {lineno}: backdated observation for event_id")
            if r["observed_fingerprint"] == previous["observed_fingerprint"]:
                # Identical fingerprint must not be reused to silently
                # change lineage, status, timestamps, or other source fields.
                if any(r[field] != previous[field]
                       for field in FIELDS - {"captured_utc"}):
                    raise ValueError(f"line {lineno}: conflicting retry metadata")
                duplicate_retries += 1
                continue
            if r["kind"] != "metadata_updated":
                raise ValueError(f"line {lineno}: conflicting first_seen event ID")
            # An update may change source metadata, but an ID cannot be
            # reassigned to a different task trace.
            if r["task_trace_id"] != previous["task_trace_id"]:
                raise ValueError(f"line {lineno}: changed task lineage for same event ID")
            revisions += 1
        elif r["kind"] == "metadata_updated":
            raise ValueError(f"line {lineno}: update without original event")
        events[event_id] = {**r, "_occurred": occurred, "_captured": captured}
        captures[event_id] = captured
    if not events:
        raise ValueError("empty source event history")
    groups = defaultdict(list)
    types = Counter()
    statuses = Counter()
    n_null_timestamp = 0
    n_verified_status = 0
    n_event_after_capture = 0
    for r in events.values():
        groups[r["task_trace_id"]].append(r)
        types[r["event_type"]] += 1
        statuses[str(r["transport_or_task_status"])] += 1
        n_null_timestamp += r["_occurred"] is None
        n_verified_status += r["verified_acceptance"]
        n_event_after_capture += r["_occurred"] is not None and r["_occurred"] > r["_captured"]
    durations = []
    ambiguous = 0
    unpaired = 0
    backwards = 0
    for rows in groups.values():
        starts = [r["_occurred"] for r in rows if r["event_type"] == START]
        ends = [r["_occurred"] for r in rows if r["event_type"] == TERMINAL]
        if len(starts) > 1 or len(ends) > 1:
            ambiguous += 1
            continue
        if not starts or not ends or starts[0] is None or ends[0] is None:
            unpaired += 1
            continue
        seconds = (ends[0] - starts[0]).total_seconds()
        if seconds < 0:
            backwards += 1
            continue
        durations.append(seconds)
    return {
        "protocol": "s1-pseudonymous-coverage-audit-v1",
        "source_sha256": source_digest,
        "n_source_records": n_records,
        "n_unique_events": len(events),
        "n_duplicate_append_retries": duplicate_retries,
        "n_metadata_revisions": revisions,
        "n_distinct_trace_ids": len(groups),
        "n_trace_spans_unambiguous": len(durations),
        "n_trace_spans_ambiguous": ambiguous,
        "n_trace_spans_missing_start_or_end": unpaired,
        "n_trace_spans_backward": backwards,
        "status_event_span_seconds": {
            "n": len(durations),
            "median": median(durations) if durations else None,
            "p95": _percentile(durations, .95),
            "minimum": min(durations) if durations else None,
            "maximum": max(durations) if durations else None,
        },
        "n_null_event_timestamp": n_null_timestamp,
        "n_event_timestamp_after_capture": n_event_after_capture,
        "n_self_reported_verified_acceptance": n_verified_status,
        "n_independently_accepted": None,
        "n_observed_deadlines": None,
        "n_observed_active_execution_durations": None,
        "event_type_counts": dict(sorted(types.items())),
        "reported_status_counts": dict(sorted(statuses.items())),
        "inferential_status": "source-coverage-and-status-span-only",
        "warning": (
            "S1 reports statuses and pseudonymous timestamps, not independently "
            "attested work completion, active compute, deadlines or interruption "
            "preferences. Even an unambiguous start/end interval is elapsed "
            "status-event time (may include idle/blocked periods), not task "
            "execution duration. Trace IDs are not independent sampling units. "
            "Source fingerprints were not independently verified against raw "
            "SQLite rows. No efficacy or causal claim is permitted."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--out", help="optional local JSON summary path")
    a = p.parse_args()
    report = json.dumps(audit_shadow(a.input), indent=2, sort_keys=True) + "\n"
    if a.out:
        output = Path(a.out)
        if output.exists():
            raise FileExistsError("summary path already exists")
        output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
