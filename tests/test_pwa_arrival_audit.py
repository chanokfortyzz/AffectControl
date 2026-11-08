"""Public SWF data-contract tests. No task deadline is invented."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from benchmarks.pwa_arrival_audit import parse_swf, summarize, HORIZONS


def line(job, submit, runtime, *, cpu="72.00", requested=60, status=1):
    items = [
        str(job), str(submit), "0", str(runtime),
        "1", str(cpu), "-1", "1", str(requested), "-1",
        str(status), "11", "11", "-1", "-1", "-1", "-1", "-1",
    ]
    assert len(items) == 18
    return " ".join(items)


def file(tmp_path, lines, *, version="2.2"):
    content = (
        f"; Version: {version}\n"
        "; Installation: Independent external system\n"
        "; Note: THIS IS A CLEANED VERSION OF THE LOG!\n"
        + "\n".join(lines) + "\n"
    )
    path = tmp_path / "test.swf"
    encoded = content.encode("utf-8")
    # Windows text-mode writes translate LF to CRLF; the fixture's expected
    # source digest must be over the bytes actually written on every OS.
    path.write_bytes(encoded)
    return path, hashlib.sha256(encoded).hexdigest()


def test_swf_float_cpu_and_cleaned_header_accepted(tmp_path):
    path, digest = file(tmp_path, [
        line(1, 0, 2),
        line(2, 10, 3),
        line(3, 20, 4),
    ])
    result = parse_swf(path, expected_hash=digest)
    assert result["n_swf_jobs"] == 3
    assert result["submit_times"] == [0, 10, 20]
    assert result["is_cleaned_log"]
    summary = summarize(result)
    # Horizons at event times are not uniform-in-time probabilities.
    assert summary["arrival_within_seconds"]["5"]["next_arrival_within_horizon_at_job_submit_fraction"] == 0.0
    assert summary["arrival_within_seconds"]["5"]["next_arrival_within_horizon_at_uniform_time_fraction"] == 0.5
    assert summary["arrival_within_seconds"]["10"]["next_arrival_within_horizon_at_job_submit_fraction"] == 1.0
    assert summary["deadline_status"] == "not_available_requested_runtime_is_resource_limit"
    assert summary["independent_agent_acceptance"] is None


def test_simultaneous_submissions_counted_as_new_job_events(tmp_path):
    path, _ = file(tmp_path, [
        line(1, 0, 2), line(2, 0, 5), line(3, 10, 6),
    ])
    result = summarize(parse_swf(path))
    assert result["n_zero_interarrival_gaps"] == 1
    assert result["arrival_within_seconds"]["1"]["next_arrival_within_horizon_at_job_submit_fraction"] == 0.5
    assert result["arrival_within_seconds"]["1"]["next_arrival_within_horizon_at_uniform_time_fraction"] == 0.1


def test_invalid_runtime_is_excluded_not_replaced(tmp_path):
    path, _ = file(tmp_path, [
        line(1, 0, 3), line(2, 5, -1),
        line(3, 10, 4),
    ])
    r = parse_swf(path)
    assert r["n_swf_jobs"] == 3
    assert r["n_valid_arrival_and_runtime_jobs"] == 2
    assert r["n_missing_or_invalid_runtime_jobs"] == 1
    assert summarize(r)["n_valid_jobs"] == 2


def test_checksum_mismatch_fails_closed(tmp_path):
    path, _ = file(tmp_path, [line(1, 0, 1), line(2, 10, 1)])
    with pytest.raises(ValueError, match="checksum"):
        parse_swf(path, expected_hash="0"*64)


def test_duplicate_job_number_rejected(tmp_path):
    path, _ = file(tmp_path, [line(1, 0, 1), line(1, 10, 1)])
    with pytest.raises(ValueError, match="duplicate job number"):
        parse_swf(path)


def test_non_numeric_and_wrong_field_count_rejected(tmp_path):
    path, _ = file(tmp_path, [line(1, 0, 1), "bad line"])
    with pytest.raises(ValueError, match="expected 18"):
        parse_swf(path)
    path, _ = file(tmp_path, [line(1, 0, 1), line(2, "tomorrow", 3)])
    with pytest.raises(ValueError, match="nonnumeric"):
        parse_swf(path)


def test_fractional_integral_field_rejected(tmp_path):
    path, _ = file(tmp_path, [line(1, 0, 1), line(2, 3.2, 3)])
    with pytest.raises(ValueError, match="fractional integral"):
        parse_swf(path)


def test_missing_well_defined_time_range_rejected(tmp_path):
    path, _ = file(tmp_path, [line(1, 0, 1), line(2, 0, 1)])
    with pytest.raises(ValueError, match="zero observed time"):
        summarize(parse_swf(path))


def test_unexpected_swf_version_rejected(tmp_path):
    path, _ = file(tmp_path, [line(1, 0, 1), line(2, 10, 1)], version="0.0")
    with pytest.raises(ValueError, match="format version 2.2"):
        parse_swf(path)


def test_input_does_not_invent_deadlines_from_requested_time(tmp_path):
    path, _ = file(tmp_path, [
        line(1, 0, 20, requested=3),
        line(2, 30, 10, requested=999),
    ])
    result = summarize(parse_swf(path))
    assert "deadline" not in str(result["arrival_within_seconds"])
    assert result["deadline_status"] == "not_available_requested_runtime_is_resource_limit"
    assert len(HORIZONS) == 6
