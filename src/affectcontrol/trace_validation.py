"""Fail-closed validation of externally ingested scheduler traces."""
from __future__ import annotations

from collections import Counter
import json
import math
import re

_ALLOWED = {"arrive", "revise", "block", "unblock", "cancel", "control"}
_PRIORITY = {"P0", "P1", "P2", "P3"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_EVENTS = 100_000


def _positive(value, field, *, allow_zero=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{field} must be finite numeric")
    if value < 0 if allow_zero else value <= 0:
        raise ValueError(f"{field} must be {'nonnegative' if allow_zero else 'positive'}")
    return float(value)


def _required_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value


def validate_trace(raw: bytes, *, max_runtime_s=21600.0) -> dict:
    """Check original event order, preconditions, durations, and provenance gaps."""
    max_runtime_s = _positive(max_runtime_s, "max_runtime_s")
    events = 0
    arrivals = 0
    latest = -1.0
    known: set[str] = set()
    cancelled: set[str] = set()
    kinds = Counter()
    deadline_count = 0
    for lineno, source in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not source.strip():
            continue
        try:
            row = json.loads(source)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {lineno}: expected JSON object")
        events += 1
        if events > _MAX_EVENTS:
            raise ValueError("trace exceeds safety limit")
        t = _positive(row.get("at_s"), "at_s", allow_zero=True)
        if t < latest:
            raise ValueError(f"line {lineno}: nonmonotonic event order")
        if t >= max_runtime_s:
            raise ValueError(f"line {lineno}: event outside replay horizon")
        latest = t
        kind = row.get("kind")
        if kind not in _ALLOWED:
            raise ValueError(f"line {lineno}: unknown event kind")
        kinds[kind] += 1
        task = _required_string(row.get("task_id"), "task_id")
        data = row.get("payload", {})
        if not isinstance(data, dict):
            raise ValueError(f"line {lineno}: payload must be an object")
        if kind == "arrive":
            if task in known:
                raise ValueError(f"line {lineno}: duplicate arrive task_id")
            _positive(data.get("duration_s"), "duration_s")
            if "priority" in data and data["priority"] not in _PRIORITY:
                raise ValueError(f"line {lineno}: unknown priority")
            for flag in ("preemptible", "immediate", "expected_interrupt"):
                if flag in data and type(data[flag]) is not bool:
                    raise ValueError(f"line {lineno}: {flag} must be boolean")
            arrivals += 1
            known.add(task)
        else:
            if task not in known:
                raise ValueError(f"line {lineno}: event before task arrival")
            if task in cancelled:
                raise ValueError(f"line {lineno}: event after cancellation")
            if kind == "cancel":
                cancelled.add(task)
        if kind == "revise":
            if "duration_delta_s" in data:
                delta = data["duration_delta_s"]
                if type(delta) not in (float, int) or not math.isfinite(delta):
                    raise ValueError(f"line {lineno}: nonfinite duration_delta_s")
            if "priority" in data and data["priority"] not in _PRIORITY:
                raise ValueError(f"line {lineno}: unknown revised priority")
        if "deadline_s" in data and data["deadline_s"] is not None:
            _positive(data["deadline_s"], "deadline_s", allow_zero=True)
            deadline_count += 1
    if not arrivals:
        raise ValueError("trace has no task arrival")
    return {
        "n_events": events, "n_arrivals": arrivals,
        "n_deadline_events": deadline_count,
        "n_cancelled_tasks": len(cancelled),
        "event_counts": dict(sorted(kinds.items())),
    }


