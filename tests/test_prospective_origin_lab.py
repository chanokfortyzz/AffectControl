"""Actual local process, origin-bound staging event, and tamper revalidation."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from benchmarks.prospective_origin_lab import run, verify
from benchmarks.s1_bus_join_gate import PROTOCOL, digest, canonical


@pytest.fixture(scope="module")
def completed_lab(tmp_path_factory):
    repo = Path(__file__).resolve().parents[1]
    root = tmp_path_factory.mktemp("origin-lab") / "staged"
    initial = run(repo, root)
    assert initial["real_process"]
    assert initial["one_origin_bound_join_verified"]
    assert initial["process_exit_zero"]
    return root


@pytest.fixture
def copy_lab(completed_lab, tmp_path):
    root = tmp_path / "copy"
    shutil.copytree(completed_lab, root)
    return root


def test_actual_subprocess_and_verified_origin_proof(completed_lab):
    report = verify(completed_lab)
    assert report["one_origin_bound_join_verified"]
    assert report["process_exit_zero"] is True
    assert report["actual_production_s1_bus_joins"] is None
    assert report["independent_human_task_acceptance"] is None
    assert report["naturally_observed_user_deadline"] is None
    assert report["causal_scheduler_effect"] is None
    assert "not_met_single_local_lab_controller" in report["trust_separation"]
    assert "lab-only-keys" not in json.dumps(report)
    proof = json.loads((completed_lab / "proof.json").read_text())
    assert proof["schema"] == PROTOCOL
    registration = json.loads((completed_lab / "intake.json").read_text())
    assert registration["issued_at"] == proof["intake"]["issued_at"]
    s1 = json.loads((completed_lab / "s1-events.jsonl").read_text())
    bus = json.loads((completed_lab / "bus-events.jsonl").read_text())
    assert registration["correlation_id"] == s1["correlation_id"] == bus["correlation_id"]
    assert registration["request_sha256"] == s1["request_sha256"] == bus["request_sha256"]
    assert proof["s1"]["source_event_sha256"] == digest(canonical(s1))
    assert proof["bus"]["source_event_sha256"] == digest(canonical(bus))


def test_no_reuse_or_rerun_when_root_preexists(completed_lab):
    with pytest.raises(FileExistsError, match="refuse overwrite"):
        run(Path(__file__).resolve().parents[1], completed_lab)


def test_tampered_staging_bus_status_rejected(copy_lab):
    file = copy_lab / "bus-events.jsonl"
    row = json.loads(file.read_text())
    row["bus_status_at_capture"] = "completed_with_fabricated_acceptance"
    file.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="Bus source event content hash mismatch"):
        verify(copy_lab)


def test_tampered_s1_process_status_rejected(copy_lab):
    file = copy_lab / "s1-events.jsonl"
    row = json.loads(file.read_text())
    row["transport_or_task_status"] = "forged"
    file.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="S1 source event content hash mismatch"):
        verify(copy_lab)


def test_tampered_real_process_receipt_rejected(copy_lab):
    file = copy_lab / "execution" / "receipts" / "lab-process-1.json"
    file.write_bytes(file.read_bytes() + b" ")
    with pytest.raises(ValueError, match="real process receipt"):
        verify(copy_lab)


def test_lost_private_lab_verification_key_fails_closed(copy_lab):
    file = copy_lab / "lab-only-keys.json"
    row = json.loads(file.read_text())
    row["roles"].pop("bus")
    file.write_text(json.dumps(row))
    with pytest.raises(KeyError):
        verify(copy_lab)


def test_tampered_request_registration_rejected(copy_lab):
    file = copy_lab / "intake.json"
    row = json.loads(file.read_text())
    row["request_sha256"] = "f" * 64
    file.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="source request digest mismatch"):
        verify(copy_lab)


def test_lab_key_material_not_committed_in_research_code(completed_lab):
    key_file = completed_lab / "lab-only-keys.json"
    assert key_file.is_file()
    assert key_file.parent.name == "staged"
    assert key_file.read_text().count("roles") == 1
    # The private lab file is separate from the public repository.
    assert not str(key_file).startswith(str(Path(__file__).resolve().parents[1]))

def test_frozen_execution_program_source_hash_is_required(copy_lab):
    registration = copy_lab / "intake.json"
    data = json.loads(registration.read_text())
    data["runner_source_sha256"] = "0" * 64
    registration.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="runner source bytes"):
        verify(copy_lab)
