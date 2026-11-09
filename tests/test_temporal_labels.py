from __future__ import annotations

import json

import pytest

from affectcontrol.temporal_labels import (
    LabelEvent, audit_revisions, load_cases, load_events, resolve_label, utc_time,
)


def event(eid, sample, kind, valid, recorded, label=None):
    data = {
        "event_id": eid, "sample_id": sample, "kind": kind,
        "valid_at": valid, "recorded_at": recorded,
    }
    if kind == "assign":
        data["label"] = label
    return data


def test_retroactive_revocation_does_not_leak_into_frozen_past(tmp_path):
    log = [
        event("first", "case-1", "assign", "2026-10-01T09:00:00Z",
              "2026-10-01T10:00:00Z", 1),
        event("revoked", "case-1", "revoke", "2026-10-01T09:00:00Z",
              "2026-10-05T10:00:00Z"),
    ]
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in log))
    events = load_events(path)
    old = resolve_label(events, "case-1", valid_at="2026-10-01T09:00Z",
                        known_at="2026-10-04T00:00Z")
    current = resolve_label(events, "case-1", valid_at="2026-10-01T09:00Z",
                            known_at="2026-10-06T00:00Z")
    assert old.event_id == "first" and old.label == 1
    assert current.event_id == "revoked" and current.label is None


def test_correction_preserves_as_known_and_as_revised():
    events = [
        LabelEvent.from_mapping(event("a", "s", "assign", "2026-11-01T08:00Z",
                                      "2026-11-01T08:10Z", 0)),
        LabelEvent.from_mapping(event("b", "s", "assign", "2026-11-01T08:00Z",
                                      "2026-11-02T08:10Z", 1)),
    ]
    old = resolve_label(events, "s", valid_at="2026-11-01T08:00Z",
                        known_at="2026-11-01T12:00Z")
    new = resolve_label(events, "s", valid_at="2026-11-01T08:00Z",
                        known_at="2026-11-03T12:00Z")
    assert (old.label, new.label) == (0, 1)
    out = audit_revisions(
        events, [("s", utc_time("2026-11-01T08:00Z"))],
        frozen_at="2026-11-01T12:00Z", reviewed_at="2026-11-03T12:00Z")
    assert out["n_changed"] == 1
    assert out["changes"][0]["reviewed_event_id"] == "b"


def test_later_valid_transition_does_not_rewrite_earlier_valid_state():
    events = [
        LabelEvent.from_mapping(event("a", "s", "assign", "2026-11-01T08:00Z",
                                      "2026-11-01T08:01Z", 1)),
        LabelEvent.from_mapping(event("b", "s", "revoke", "2026-11-02T08:00Z",
                                      "2026-11-02T08:01Z")),
    ]
    assert resolve_label(events, "s", valid_at="2026-11-01T09:00Z",
                         known_at="2026-11-03T00:00Z").label == 1
    assert resolve_label(events, "s", valid_at="2026-11-03T00:00Z",
                         known_at="2026-11-03T00:00Z").label is None


def test_knowledge_cutoff_cannot_use_future_record():
    e = LabelEvent.from_mapping(event("a", "s", "assign", "2026-11-01T08:00Z",
                                       "2026-11-03T00:00Z", 1))
    assert resolve_label([e], "s", valid_at="2026-11-01T08:00Z",
                         known_at="2026-11-02T00:00Z") is None


@pytest.mark.parametrize("obj", [
    event("x", "s", "assign", "2026-11-01T08:00", "2026-11-01T09:00Z", 1),
    event("x", "s", "assign", "2026-11-01T08:00Z", "2026-11-01T09:00", 1),
    event("x", "s", "assign", "2026-11-01T08:00Z", "2026-11-01T09:00Z", True),
    event("x", "s", "assign", "2026-11-01T08:00Z", "2026-11-01T09:00Z", 2),
    dict(event("x", "s", "revoke", "2026-11-01T08:00Z",
               "2026-11-01T09:00Z"), label=0),
])
def test_invalid_event_rejected(obj):
    with pytest.raises(ValueError):
        LabelEvent.from_mapping(obj)


def test_duplicate_ids_and_nonmonotone_append_rejected(tmp_path):
    first = event("a", "s", "assign", "2026-11-01T08:00Z",
                  "2026-11-01T10:00Z", 1)
    duplicate = dict(first, valid_at="2026-11-01T09:00Z")
    earlier = event("b", "s", "assign", "2026-11-01T08:00Z",
                    "2026-11-01T09:00Z", 0)
    path = tmp_path / "events.jsonl"
    for bad in (duplicate, earlier):
        path.write_text("\n".join(map(json.dumps, (first, bad))))
        with pytest.raises(ValueError):
            load_events(path)


def test_ambiguous_simultaneous_events_rejected(tmp_path):
    a = event("a", "s", "assign", "2026-11-01T08:00Z",
              "2026-11-01T10:00Z", 1)
    b = dict(a, event_id="b", label=0)
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(map(json.dumps, (a, b))))
    with pytest.raises(ValueError, match="ambiguous"):
        load_events(path)


def test_case_dedup_and_unknown_are_not_zero(tmp_path):
    path = tmp_path / "cases.jsonl"
    row = {"sample_id": "s", "observed_at": "2026-11-01T08:00Z"}
    path.write_text(json.dumps(row))
    cases = load_cases(path)
    result = audit_revisions([], cases, frozen_at="2026-11-01T09:00Z",
                             reviewed_at="2026-11-03T09:00Z")
    assert result["n_missing_at_freeze"] == result["n_missing_at_review"] == 1
    assert result["n_changed"] == 0
    path.write_text("\n".join(map(json.dumps, (row, row))))
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(path)


def test_review_before_freeze_rejected():
    with pytest.raises(ValueError):
        audit_revisions([], [], frozen_at="2026-11-03T09:00Z",
                        reviewed_at="2026-11-02T09:00Z")
