import json
import hashlib
import pytest
from affectcontrol.lifecycle_audit import audit, main


def _write(path, rows):
    path.write_text("".join(json.dumps(v) + "\n" for v in rows), encoding="utf-8")
    return path


def test_aggregate_without_exposing_ids_or_claiming_success(tmp_path):
    path = _write(tmp_path / "obs.jsonl", [
        {"kind": "state_snapshot", "anon_task_id": "secret-snapshot-1"},
        {"kind": "task-claimed", "task_id": "secret-task-A"},
        {"kind": "task-finished", "task_id": "secret-task-A"},
        {"kind": "review-passed", "task_id": "secret-task-A"},
        {"kind": "task-finished-by-lease", "task_id": "secret-task-B"},
        {"kind": "task-reopened-for-retry", "task_id": "secret-task-B"},
        {"kind": "task-packaged", "task_id": "secret-task-C"},
        {"kind": "task-claimed", "task_id": ""},
        {"kind": "unknown", "task_id": "secret-task-D"},
    ])
    before = path.read_bytes()
    report = audit(path)
    assert path.read_bytes() == before
    assert report["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert report["rows"] == 9
    assert report["task_lineages_with_events"] == 3
    assert report["tasks_with_recorded_terminal_event"] == 2
    assert report["tasks_with_recorded_review_passed"] == 1
    assert report["tasks_with_both_terminal_event_and_review_marker"] == 1
    assert report["tasks_with_retry_event"] == 1
    assert report["tasks_with_lease_terminal_without_explicit_finish"] == 1
    assert report["snapshot_rows_excluded_from_event_lineage"] == 1
    assert report["recognized_event_rows_without_task_id"] == 1
    assert report["unknown_or_unrecognized_kind_rows"] == 1
    assert report["independently_verified_successes"] == 0
    assert "secret" not in json.dumps(report)


def test_invalid_json_and_oversized_line_fail_closed(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"kind":"task-claimed"}\nnot-json\n')
    with pytest.raises(ValueError, match="line 2"):
        audit(path)
    path.write_bytes(b"x" * (256 * 1024 + 5) + b"\n")
    with pytest.raises(ValueError, match="size limit"):
        audit(path)


def test_empty_source_and_non_object(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("")
    with pytest.raises(ValueError, match="empty"):
        audit(path)
    path.write_text("[]\n")
    with pytest.raises(ValueError, match="object"):
        audit(path)


def test_cli_never_prints_task_ids(tmp_path, capsys):
    path = _write(tmp_path / "private.jsonl", [{
        "kind": "task-finished-by-lease", "task_id": "private-task",
    }])
    assert main(["--input", str(path)]) == 0
    result = capsys.readouterr().out
    assert "private-task" not in result
    assert json.loads(result)["production_decision"] == "NOT_APPROVED"
