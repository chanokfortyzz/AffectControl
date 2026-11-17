"""Read-only, explicit-contract acceptance probes for existing Sage artifacts.

Only checks a human-selected narrow output requirement, not general task success.
No execution, relabeling, dispatch, model output or scheduler mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from .receipt_audit import _within, _hash_file, SUPPORTED_SCOPE

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_RESULT_BYTES = 32 * 1024 * 1024
CONTRACT_KEYS = frozenset({
    "task_id", "archive_request_marker", "expected_chinese_bullets",
    "required_trace_events", "protocol",
})
REQUIRED_TRACE = frozenset({"task-packaged", "task-claimed", "local-worker-finished"})
CHINESE = re.compile(r"[\u3400-\u9fff]")
POINT = re.compile(r"^\s*(?:[-*+]\s+|\d{1,2}[.、)）]\s*)\S")
TOOL_MARKERS = ("<tool_call>", "<function>", "<parameter=arguments>")


def _read_within(path, root, maximum):
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    normalized = p.resolve(strict=False)
    if not _within(normalized, root):
        raise ValueError("input path is outside permitted root")
    if p.is_symlink() or not normalized.is_file():
        raise ValueError("input missing or is symlink")
    if normalized.stat().st_size > maximum:
        raise ValueError("input exceeds size limit")
    return normalized


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as e:
        raise ValueError("invalid UTF-8 JSON input") from e


def _archive_block(archive_text, task_id):
    # The source archive already contains original task packets. Do not use
    # a post-hoc reinterpretation of the task as proof of the task's outcome.
    head = re.compile(r"^###\s+\[" + re.escape(task_id) + r"\](?:\s|$)", re.M)
    hits = list(head.finditer(archive_text))
    if len(hits) != 1:
        raise ValueError("archive must contain exactly one matching task packet")
    start = hits[0].start()
    end = re.search(r"^###\s+\[TASK-[^\]]+\]", archive_text[hits[0].end():], re.M)
    return archive_text[start:hits[0].end() + end.start()] if end else archive_text[start:]


def audit(contract_file, snapshot_file, archive_file, trace_file, artifact_root):
    root = Path(artifact_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("artifact root must be directory")
    contract = _read_json(_read_within(contract_file, root, 16_384))
    if not isinstance(contract, dict) or set(contract) != CONTRACT_KEYS:
        raise ValueError("contract requires exactly five supported fields")
    task_id = contract["task_id"]
    marker = contract["archive_request_marker"]
    count = contract["expected_chinese_bullets"]
    trace_kinds = contract["required_trace_events"]
    if (not isinstance(task_id, str) or not (1 <= len(task_id) <= 128)
            or any(ord(c) < 32 for c in task_id)):
        raise ValueError("invalid task_id")
    if not isinstance(marker, str) or not 4 <= len(marker) <= 120:
        raise ValueError("invalid archive_request_marker")
    if type(count) is not int or count < 1 or count > 10:
        raise ValueError("expected_chinese_bullets out of bounds")
    if (not isinstance(trace_kinds, list) or len(trace_kinds) != 3
            or set(trace_kinds) != REQUIRED_TRACE):
        raise ValueError("this probe supports packaged, claimed and finished only")
    if contract["protocol"] != "exploratory_posthoc_narrow_v1":
        raise ValueError("unsupported protocol; this is not a blinded gold oracle")

    source = _read_within(snapshot_file, root, MAX_FILE_BYTES)
    snapshot = _read_json(source)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("tasks"), dict):
        raise ValueError("malformed snapshot")
    task = snapshot["tasks"].get(task_id)
    if not isinstance(task, dict):
        raise ValueError("task not in snapshot")
    expected = task.get("result_content_sha256")
    if (not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected)
            or task.get("result_hash_scope") != SUPPORTED_SCOPE):
        raise ValueError("task lacks supported result hash")
    result = _read_within(task.get("result_path"), root, MAX_RESULT_BYTES)
    actual_hash = _hash_file(result)
    integrity_ok = actual_hash == expected.lower()

    archive = _read_within(archive_file, root, MAX_FILE_BYTES)
    blob = _archive_block(archive.read_text(encoding="utf-8"), task_id)
    source_marker_ok = marker in blob
    # Task must be truly asking for the stated number of Chinese points, not
    # just an arbitrary contract written after looking at the result.
    if not source_marker_ok:
        raise ValueError("contract marker does not occur in original task packet")
    contents = result.read_text(encoding="utf-8")
    lines = contents.splitlines()
    chinese_bullets = [
        line for line in lines if POINT.match(line) and CHINESE.search(line)
    ]
    tool_call_only = any(s in contents for s in TOOL_MARKERS) and not chinese_bullets
    bullets_ok = len(chinese_bullets) == count and not any(
        s in contents for s in TOOL_MARKERS
    )
    events = Counter()
    event_source = _read_within(trace_file, root, MAX_FILE_BYTES)
    with event_source.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            if len(raw) > 262_144:
                raise ValueError(f"trace line {number} too large")
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except (UnicodeError, ValueError) as e:
                raise ValueError(f"trace line {number} invalid") from e
            if isinstance(row, dict) and row.get("task_id") == task_id:
                kind = row.get("event")
                if isinstance(kind, str) and kind in REQUIRED_TRACE:
                    events[kind] += 1

    # A fail here is a genuine artifact-acceptance defect, not a verdict
    # about AffectControl scheduler efficacy or all other task requirements.
    outcome = ("NOT_EVALUATED_INTEGRITY_MISMATCH" if not integrity_ok else
               "NARROW_ACCEPTANCE_FAIL" if not bullets_ok else
               "NARROW_ACCEPTANCE_PASS")
    return {
        "mode": "posthoc_read_only_narrow_acceptance",
        "case_id": hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:16],
        "contract_sha256": _hash_file(_read_within(contract_file, root, 16_384)),
        "source_snapshot_sha256": _hash_file(source),
        "source_archive_sha256": _hash_file(archive),
        "source_trace_sha256": _hash_file(event_source),
        "result_hash_claim_matches_bytes": integrity_ok,
        "archive_request_marker_present": source_marker_ok,
        "expected_chinese_bullet_count": count,
        "observed_chinese_bullet_count": len(chinese_bullets),
        "tool_call_without_final_bullets": tool_call_only,
        "recorded_trace_event_counts": dict(sorted(events.items())),
        "required_trace_events_observed": all(events[v] > 0 for v in REQUIRED_TRACE),
        "artifact_narrow_verdict": outcome,
        "independent_blinded_gold_labels": 0,
        "dispatch_allowed": False,
        "production_decision": "NOT_APPROVED",
        "caveats": [
            "post-hoc criterion anchored in archived original request, not preregistered",
            "trace markers are executor self-report and do not prove acceptance",
            "a narrow artifact check is not a full task success/failure label",
            "hash agreement is byte integrity, not signer or actor authentication",
            "no raw task text, result content, task identifier or path is emitted",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only Sage artifact contract probe")
    parser.add_argument("--contract", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--artifact-root", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.contract, args.snapshot, args.archive, args.trace,
                               args.artifact_root), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, TypeError) as err:
        print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
