"""Append-only, bitemporal adjudication records for offline evaluation only.

Valid time asks when a label applies to a sample. Recorded time asks when the
researcher learned it. These are different, and later corrections must not be
available to an earlier frozen evaluation. No live policy or permission control.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable


def utc_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a nonempty ISO 8601 string")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO 8601 timestamp: {value!r}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class LabelEvent:
    event_id: str
    sample_id: str
    kind: str
    valid_at: datetime
    recorded_at: datetime
    label: int | None

    @classmethod
    def from_mapping(cls, obj: dict) -> "LabelEvent":
        for name in ("event_id", "sample_id"):
            if not isinstance(obj.get(name), str) or not obj[name].strip():
                raise ValueError(f"{name} must be a nonempty string")
        kind = obj.get("kind")
        if kind not in ("assign", "revoke"):
            raise ValueError("kind must be 'assign' or 'revoke'")
        label = obj.get("label")
        if kind == "assign" and (type(label) is not int or label not in (0, 1)):
            raise ValueError("assign requires binary integer label 0 or 1")
        if kind == "revoke" and "label" in obj:
            raise ValueError("revoke must omit label (not set it to 0)")
        return cls(
            event_id=obj["event_id"], sample_id=obj["sample_id"], kind=kind,
            valid_at=utc_time(obj["valid_at"]),
            recorded_at=utc_time(obj["recorded_at"]),
            label=label if kind == "assign" else None,
        )


def load_events(path: str | Path) -> tuple[LabelEvent, ...]:
    """Read an append-only JSONL log; reject collisions and backdated log order."""
    result: list[LabelEvent] = []
    event_ids: set[str] = set()
    coordinates: set[tuple[str, datetime, datetime]] = set()
    last_recorded: datetime | None = None
    for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            event = LabelEvent.from_mapping(json.loads(raw))
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"line {lineno}: {exc}") from exc
        if event.event_id in event_ids:
            raise ValueError(f"line {lineno}: duplicate event_id")
        coordinate = (event.sample_id, event.valid_at, event.recorded_at)
        if coordinate in coordinates:
            raise ValueError(f"line {lineno}: ambiguous simultaneous events")
        if last_recorded is not None and event.recorded_at < last_recorded:
            raise ValueError(f"line {lineno}: recorded_at must be append-ordered")
        result.append(event)
        event_ids.add(event.event_id)
        coordinates.add(coordinate)
        last_recorded = event.recorded_at
    if not result:
        raise ValueError("empty event log")
    return tuple(result)


def resolve_label(
    events: Iterable[LabelEvent], sample_id: str, *,
    valid_at: str | datetime, known_at: str | datetime,
) -> LabelEvent | None:
    """Return the last applicable event known at the specified knowledge cutoff.

    A returned revoke event has label=None; an absent event means no known label.
    Neither should silently become a negative label.
    """
    valid = utc_time(valid_at) if isinstance(valid_at, str) else _require_aware(valid_at)
    known = utc_time(known_at) if isinstance(known_at, str) else _require_aware(known_at)
    relevant = (
        e for e in events if e.sample_id == sample_id
        and e.valid_at <= valid and e.recorded_at <= known
    )
    return max(relevant, key=lambda e: (e.valid_at, e.recorded_at), default=None)


def _require_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("query datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def load_cases(path: str | Path) -> tuple[tuple[str, datetime], ...]:
    cases = []
    seen = set()
    for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
            sample_id = row["sample_id"]
            if not isinstance(sample_id, str) or not sample_id.strip():
                raise ValueError("sample_id must be nonempty")
            observed_at = utc_time(row["observed_at"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"line {lineno}: {exc}") from exc
        if sample_id in seen:
            raise ValueError(f"line {lineno}: duplicate sample_id")
        cases.append((sample_id, observed_at))
        seen.add(sample_id)
    if not cases:
        raise ValueError("empty cases")
    return tuple(cases)


def audit_revisions(
    events: Iterable[LabelEvent],
    cases: Iterable[tuple[str, datetime]],
    *,
    frozen_at: str | datetime,
    reviewed_at: str | datetime,
) -> dict:
    frozen = utc_time(frozen_at) if isinstance(frozen_at, str) else _require_aware(frozen_at)
    reviewed = utc_time(reviewed_at) if isinstance(reviewed_at, str) else _require_aware(reviewed_at)
    if reviewed < frozen:
        raise ValueError("reviewed_at must be >= frozen_at")
    records = tuple(events)
    changes = []
    count = 0
    missing_at_freeze = 0
    missing_at_review = 0
    for sample_id, observed_at in cases:
        count += 1
        old_event = resolve_label(records, sample_id, valid_at=observed_at, known_at=frozen)
        new_event = resolve_label(records, sample_id, valid_at=observed_at, known_at=reviewed)
        old = old_event.label if old_event else None
        new = new_event.label if new_event else None
        missing_at_freeze += old is None
        missing_at_review += new is None
        if old != new:
            changes.append({
                "sample_id": sample_id, "frozen_label": old, "reviewed_label": new,
                "frozen_event_id": old_event.event_id if old_event else None,
                "reviewed_event_id": new_event.event_id if new_event else None,
            })
    return {
        "n_cases": count, "n_missing_at_freeze": missing_at_freeze,
        "n_missing_at_review": missing_at_review,
        "n_changed": len(changes), "changed_fraction": len(changes) / count if count else None,
        "changes": changes,
        "warning": "Revised adjudication is not ground truth or an identifiable policy effect.",
    }
