from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from affectcontrol import load_jsonl_trace
from benchmarks.capture_execution import capture
from benchmarks.observation_manifest import build_observation_manifest


def run(root, name="run-a", command=None, *, timeout_s=20):
    if command is None:
        command = [sys.executable, "-c",
                   "import sys;print('private stdout');print('private stderr',file=sys.stderr)"]
    return capture(root, name, "project-a", command,
                   cwd=root.parent, timeout_s=timeout_s)


def test_real_process_is_measured_without_recording_content(tmp_path):
    root = tmp_path / "observations"
    receipt = run(root)
    assert receipt["result"] == "exited"
    assert receipt["exit_code"] == 0
    assert receipt["duration_wallclock_s"] > 0
    assert receipt["deadline_basis"] == "none"
    assert receipt["duration_basis"] == "wallclock_proxy"
    assert receipt["oracle_status"] == "exit-code-only-not-independent-adjudication"
    assert receipt["stdout_sha256"] == hashlib.sha256(("private stdout" + os.linesep).encode()).hexdigest()
    assert receipt["stderr_sha256"] == hashlib.sha256(("private stderr" + os.linesep).encode()).hexdigest()
    raw = (root / "sessions" / "run-a.jsonl").read_text()
    redacted = (root / "receipts" / "run-a.json").read_text()
    assert "private stdout" not in raw + redacted
    assert "private stderr" not in raw + redacted
    assert receipt["argv_sha256"] in redacted
    trace = load_jsonl_trace(root / "sessions" / "run-a.jsonl")
    assert len(trace.events) == 1 and trace.events[0].task_id == "run-a"
    rows = build_observation_manifest(root)
    assert len(rows) == 1
    assert rows[0]["duration_basis"] == "wallclock_proxy"
    assert rows[0]["deadline_basis"] == "none"
    assert rows[0]["sha256"] == receipt["trace_sha256"]


def test_duplicate_session_id_is_rejected_before_reexecution(tmp_path):
    root = tmp_path / "observations"
    target = tmp_path / "side_effect.txt"
    cmd = [sys.executable, "-c",
           f"from pathlib import Path; Path({str(target)!r}).open('a').write('x')"]
    run(root, command=cmd)
    with pytest.raises(FileExistsError):
        run(root, command=cmd)
    assert target.read_text() == "x"


def test_nonzero_exit_is_observed_not_silently_mapped_to_human_label(tmp_path):
    root = tmp_path / "observations"
    receipt = run(root, command=[sys.executable, "-c", "raise SystemExit(7)"])
    assert receipt["exit_code"] == 7
    assert receipt["result"] == "exited"
    assert "label" not in receipt
    assert build_observation_manifest(root)


def test_timeout_is_recorded_without_false_success(tmp_path):
    root = tmp_path / "observations"
    receipt = run(root, command=[sys.executable, "-c", "import time; time.sleep(1)"],
                  timeout_s=0.03)
    assert receipt["result"] == "timed_out"
    assert receipt["exit_code"] is None
    with pytest.raises(ValueError, match="no completed"):
        build_observation_manifest(root)


@pytest.mark.parametrize("identifier", ["", "..", "../s", "hello/world", " space", "a" * 77])
def test_unsafe_session_identifiers_rejected(tmp_path, identifier):
    with pytest.raises(ValueError, match="session_id"):
        run(tmp_path / "observations", name=identifier)


def test_invalid_command_and_timeout_refused(tmp_path):
    root = tmp_path / "observations"
    with pytest.raises(ValueError, match="argv"):
        run(root, command=[])
    with pytest.raises(ValueError, match="timeout_s"):
        run(root, timeout_s=0)
    assert not root.exists()


def test_shell_metacharacters_are_literal_arguments(tmp_path):
    root = tmp_path / "observations"
    target = tmp_path / "should_not_exist"
    payload = "x; touch " + str(target)
    receipt = run(root, command=[sys.executable, "-c",
                  "import sys; assert len(sys.argv) == 2", payload])
    assert receipt["result"] == "exited" and receipt["exit_code"] == 0
    assert not target.exists()


def test_tampering_with_trace_fails_manifest_audit(tmp_path):
    root = tmp_path / "observations"
    run(root)
    path = root / "sessions" / "run-a.jsonl"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="immutable receipt"):
        build_observation_manifest(root)


def test_missing_session_receipt_rejected(tmp_path):
    root = tmp_path / "observations"
    run(root)
    path = root / "receipts" / "run-a.json"
    data = json.loads(path.read_text())
    data["deadline_basis"] = "observed"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="did not observe a deadline"):
        build_observation_manifest(root)



def test_symlinked_evidence_store_rejected_before_subprocess(tmp_path):
    root = tmp_path / "observations"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (root / "receipts").symlink_to(outside, target_is_directory=True)
    marker = tmp_path / "bad-execution"
    cmd = [sys.executable, "-c", f"from pathlib import Path;Path({str(marker)!r}).touch()"]
    with pytest.raises(ValueError, match="symlink"):
        run(root, command=cmd)
    assert not marker.exists()


def test_observed_one_lineage_not_promoted_to_efficacy_evidence(tmp_path):
    from benchmarks.trace_cohort import build_cohort
    root = tmp_path / "observations"
    run(root)
    rows = build_observation_manifest(root)
    manifest = root / "manifest.jsonl"
    manifest.write_text("\n".join(map(json.dumps, rows)) + "\n")
    with pytest.raises(ValueError, match="at least three independent lineages"):
        build_cohort(root, manifest)
