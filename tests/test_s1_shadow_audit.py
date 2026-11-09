from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.s1_shadow_audit import audit_shadow


def event(n, kind="task_started", *,
          trace="pseudo-trace-A",
          timestamp="2026-10-07T22:05:49+08:00",
          captured="2026-11-01T03:52:27+00:00",
          fingerprint=None):
    return {
        "captured_utc": captured,
        "event_id": f"pseudonymous-{n}",
        "event_type": kind,
        "kind": "first_seen",
        "observed_fingerprint": fingerprint or (f"{n:064x}"),
        "schema": "agent-eval/s1-watch-v1",
        "source_table": "tasks",
        "task_trace_id": trace,
        "timestamp": timestamp,
        "transport_or_task_status": "completed",
        "verified_acceptance": False,
    }


def write(tmp_path, rows):
    p = tmp_path / "pseudonymous.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_real_status_span_is_not_task_duration_or_verified_completion(tmp_path):
    rows = [
        event(1),
        event(2, "task_terminal_reported", timestamp="2026-10-07T22:12:16+08:00"),
        event(3, "log_recorded", trace="pseudo-trace-B"),
    ]
    out = audit_shadow(write(tmp_path, rows))
    assert out["n_unique_events"] == 3
    assert out["n_distinct_trace_ids"] == 2
    assert out["n_trace_spans_unambiguous"] == 1
    assert out["status_event_span_seconds"]["minimum"] == 387.0
    assert out["n_trace_spans_missing_start_or_end"] == 1
    assert out["n_observed_active_execution_durations"] is None
    assert out["n_independently_accepted"] is None
    assert out["inferential_status"] == "source-coverage-and-status-span-only"
    assert "pseudo-trace-A" not in json.dumps(out)


def test_crash_safe_append_retry_not_counted_as_new_event(tmp_path):
    old = event(1)
    retry = {**old, "captured_utc": "2026-11-02T03:52:27+00:00"}
    result = audit_shadow(write(tmp_path, [old, retry]))
    assert result["n_source_records"] == 2
    assert result["n_unique_events"] == 1
    assert result["n_duplicate_append_retries"] == 1


def test_metadata_update_same_id_preserves_lineage(tmp_path):
    first = event(1)
    updated = {**first, "kind": "metadata_updated",
               "observed_fingerprint": "f" * 64,
               "captured_utc": "2026-11-02T03:52:27+00:00",
               "transport_or_task_status": "failed"}
    out = audit_shadow(write(tmp_path, [first, updated]))
    assert out["n_metadata_revisions"] == 1
    assert out["reported_status_counts"] == {"failed": 1}


def test_reassignment_to_other_trace_is_rejected(tmp_path):
    a = event(1)
    b = {**a, "kind": "metadata_updated",
         "observed_fingerprint": "e" * 64,
         "captured_utc": "2026-11-02T03:52:27+00:00",
         "task_trace_id": "another-lineage"}
    with pytest.raises(ValueError, match="changed task lineage"):
        audit_shadow(write(tmp_path, [a, b]))


@pytest.mark.parametrize("mutation,match", [
    ({"schema": "other"}, "wrong metadata schema"),
    ({"verified_acceptance": "false"}, "boolean"),
    ({"observed_fingerprint": "short"}, "fingerprint"),
    ({"timestamp": "2026-10-07T22:05:49"}, "missing timezone"),
    ({"captured_utc": "2026-11-01T03:52:27"}, "missing timezone"),
    ({"event_type": ""}, "event_type"),
    ({"transport_or_task_status": 1}, "reported status"),
    ({"kind": "secret_kind"}, "unknown update kind"),
])
def test_invalid_input_rejected(tmp_path, mutation, match):
    with pytest.raises(ValueError, match=match):
        audit_shadow(write(tmp_path, [{**event(1), **mutation}]))


def test_raw_private_fields_are_blocked_before_export(tmp_path):
    raw = {**event(1), "task_title": "sensitive content"}
    with pytest.raises(ValueError, match="raw-content leakage"):
        audit_shadow(write(tmp_path, [raw]))


def test_conflicting_first_seen_is_rejected(tmp_path):
    first = event(1)
    second = {**first, "observed_fingerprint": "f" * 64}
    with pytest.raises(ValueError, match="conflicting first_seen"):
        audit_shadow(write(tmp_path, [first, second]))


def test_backdated_update_rejected(tmp_path):
    first = event(1)
    second = {**first, "kind": "metadata_updated",
              "observed_fingerprint": "f" * 64,
              "captured_utc": "2026-10-30T00:00:00+00:00"}
    with pytest.raises(ValueError, match="backdated"):
        audit_shadow(write(tmp_path, [first, second]))


def test_update_without_original_rejected(tmp_path):
    a = {**event(1), "kind": "metadata_updated"}
    with pytest.raises(ValueError, match="without original"):
        audit_shadow(write(tmp_path, [a]))


def test_ambiguous_starts_not_paired(tmp_path):
    rows = [
        event(1),
        event(2, timestamp="2026-10-07T22:06:00+08:00"),
        event(3, "task_terminal_reported",
              timestamp="2026-10-07T22:12:16+08:00"),
    ]
    out = audit_shadow(write(tmp_path, rows))
    assert out["n_trace_spans_ambiguous"] == 1
    assert out["n_trace_spans_unambiguous"] == 0


def test_backward_pair_flagged_not_used(tmp_path):
    rows = [
        event(1),
        event(2, "task_terminal_reported",
              timestamp="2026-10-07T22:03:00+08:00"),
    ]
    out = audit_shadow(write(tmp_path, rows))
    assert out["n_trace_spans_backward"] == 1
    assert out["status_event_span_seconds"]["median"] is None


def test_future_timestamp_is_not_silently_validated(tmp_path):
    row = event(1, timestamp="2026-11-08T01:00:00Z")
    out = audit_shadow(write(tmp_path, [row]))
    assert out["n_event_timestamp_after_capture"] == 1


def test_empty_rows_rejected(tmp_path):
    with pytest.raises(ValueError, match="empty source"):
        audit_shadow(write(tmp_path, []))



def test_duplicate_fingerprint_cannot_hide_changed_status(tmp_path):
    first = event(1)
    second = {**first, "transport_or_task_status": "failed",
              "captured_utc": "2026-11-02T03:52:27+00:00"}
    with pytest.raises(ValueError, match="conflicting retry metadata"):
        audit_shadow(write(tmp_path, [first, second]))



def test_even_sample_median_is_arithmetic_midpoint(tmp_path):
    rows = [
        event(1, trace="trace-a", timestamp="2026-10-07T20:00:00Z"),
        event(2, "task_terminal_reported", trace="trace-a",
              timestamp="2026-10-07T20:01:00Z"),
        event(3, trace="trace-b", timestamp="2026-10-07T20:00:00Z"),
        event(4, "task_terminal_reported", trace="trace-b",
              timestamp="2026-10-07T20:03:00Z"),
    ]
    out = audit_shadow(write(tmp_path, rows))
    assert out["status_event_span_seconds"]["median"] == 120.0
