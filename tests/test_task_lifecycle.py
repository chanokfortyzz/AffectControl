from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from benchmarks.capture_execution import capture
from benchmarks.task_lifecycle import append, audit


def child(root, session_id, lineage="lineage-a", *, status=0):
    return capture(
        root, session_id, lineage,
        [sys.executable, "-c", f"raise SystemExit({status})"],
        cwd=root.parent, timeout_s=5,
    )


def ledger(root, task="task-a"):
    return (root / "lifecycles" / (task + ".jsonl"))


def test_real_multi_phase_process_observation_and_check(tmp_path):
    root = tmp_path / "evidence"
    first = append(root, "task-a", "lineage-a", "start")
    assert not first["terminal_state_recorded"]
    assert first["controller_observed_running_s"] is None
    child(root, "phase-1")
    after_pause = append(root, "task-a", "lineage-a", "pause", receipt_id="phase-1")
    assert after_pause["n_work_phases"] == 1
    assert after_pause["controller_observed_running_s"] is None
    append(root, "task-a", "lineage-a", "resume")
    child(root, "phase-2")
    result = append(root, "task-a", "lineage-a", "finish", receipt_id="phase-2")
    assert result["n_lifecycle_events"] == 4
    assert result["n_work_phases"] == 2
    assert result["n_pauses"] == 1
    assert result["terminal_kind"] == "finish"
    assert result["controller_observed_running_s"] > 0
    assert result["controller_observed_paused_s"] >= 0
    assert result["n_phase_exit_zero"] == 2
    assert result["independent_task_acceptance"] is None
    child(root, "local-check")
    checked = append(root, "task-a", "lineage-a", "check", receipt_id="local-check")
    assert checked["n_local_checks_exit_zero"] == 1
    assert checked["receipt_links_verified"] == 3
    assert checked["independent_task_acceptance"] is None
    assert "task-a" not in json.dumps(checked)


@pytest.mark.parametrize("sequence,pattern", [
    (("pause",), "first lifecycle event"),
    (("start", "start"), "invalid lifecycle transition"),
    (("start", "resume"), "invalid lifecycle transition"),
    (("start", "finish", "resume"), "invalid lifecycle transition"),
])
def test_invalid_state_transition_rejected(tmp_path, sequence, pattern):
    root = tmp_path / "evidence"
    for kind in sequence[:-1]:
        if kind == "start":
            append(root, "task-a", "lineage-a", "start")
        elif kind == "finish":
            child(root, "terminal")
            append(root, "task-a", "lineage-a", "finish", receipt_id="terminal")
    with pytest.raises(ValueError, match=pattern):
        append(root, "task-a", "lineage-a", sequence[-1])


def test_frozen_ledger_tampering_fails_audit(tmp_path):
    root = tmp_path / "evidence"
    append(root, "task-a", "lineage-a", "start")
    path = ledger(root)
    data = json.loads(path.read_text())
    data["lineage_id"] = "forged"
    path.write_text(json.dumps(data) + "\n")
    with pytest.raises(ValueError, match="content hash mismatch"):
        audit(path.read_bytes())


def test_receipt_tampering_is_rejected(tmp_path):
    root = tmp_path / "evidence"
    append(root, "task-a", "lineage-a", "start")
    child(root, "phase-1")
    append(root, "task-a", "lineage-a", "finish", receipt_id="phase-1")
    path = root / "receipts" / "phase-1.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="linked process receipt modified"):
        audit(ledger(root).read_bytes(), receipts_root=root)


def test_wrong_lineage_receipt_and_bad_path_rejected(tmp_path):
    root = tmp_path / "evidence"
    append(root, "task-a", "lineage-a", "start")
    child(root, "foreign-phase", lineage="lineage-b")
    with pytest.raises(ValueError, match="receipt identity mismatch"):
        append(root, "task-a", "lineage-a", "finish", receipt_id="foreign-phase")
    with pytest.raises(ValueError, match="receipt"):
        append(root, "task-a", "lineage-a", "finish")


def test_unexpected_receipt_on_start_rejected(tmp_path):
    with pytest.raises(ValueError, match="unexpected receipt"):
        append(tmp_path / "evidence", "task-a", "lineage-a", "start", receipt_id="extra")


def test_invalid_directory_symlink_rejected(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    external = tmp_path / "other"
    external.mkdir()
    (root / "lifecycles").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        append(root, "task-a", "lineage-a", "start")


def test_failed_job_has_no_independent_negative_label(tmp_path):
    root = tmp_path / "evidence"
    append(root, "task-a", "lineage-a", "start")
    child(root, "phase-failed", status=7)
    out = append(root, "task-a", "lineage-a", "fail", receipt_id="phase-failed")
    assert out["terminal_kind"] == "fail"
    assert out["n_phase_exit_zero"] == 0
    assert out["independent_task_acceptance"] is None


def test_missing_final_event_is_censored(tmp_path):
    root = tmp_path / "evidence"
    append(root, "task-a", "lineage-a", "start")
    child(root, "phase-1")
    out = append(root, "task-a", "lineage-a", "pause", receipt_id="phase-1")
    assert not out["terminal_state_recorded"]
    assert out["controller_observed_running_s"] is None


def test_task_lineage_change_after_start_rejected(tmp_path):
    root = tmp_path / "evidence"
    append(root, "task-a", "lineage-a", "start")
    with pytest.raises(ValueError, match="lineage mismatch"):
        append(root, "task-a", "lineage-b", "resume")



def test_no_reusing_the_same_receipt_for_independent_local_check(tmp_path):
    root = tmp_path / "evidence"
    append(root, "task-a", "lineage-a", "start")
    child(root, "phase-1")
    append(root, "task-a", "lineage-a", "finish", receipt_id="phase-1")
    with pytest.raises(ValueError, match="same receipt reused"):
        append(root, "task-a", "lineage-a", "check", receipt_id="phase-1")


def test_nonzero_exit_cannot_be_reported_as_successful_phase(tmp_path):
    root = tmp_path / "evidence"
    append(root, "task-a", "lineage-a", "start")
    child(root, "phase-failed", status=3)
    with pytest.raises(ValueError, match="successful phase event"):
        append(root, "task-a", "lineage-a", "finish", receipt_id="phase-failed")
    assert len(ledger(root).read_text().splitlines()) == 1
