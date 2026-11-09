"""Lab signer: real durable source checks, test-only HMAC, never Sage authority."""
from __future__ import annotations
import json
import os
from pathlib import Path
import pytest

from benchmarks.sage_intake_receipt_lab import issue, verify
from benchmarks.sage_outbox_durable_stage import (
    initialize, tick, recover, InjectedCrash,
)


def request(pid, ref):
    return (
        f"\n\n### [2026-11-09 10:20:00 请求：{pid}]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        f"- **s1_ref**：{ref}\n"
        f"- **任务ID（建议）**：{pid}\n"
        "- **目标**：Synthetic test only\n"
        "- **risk（建议）**：low\n"
    )


@pytest.fixture
def example(tmp_path):
    original=tmp_path/"outbox.md"
    original.write_text(request("TASK-S1-OLD","old-id"),encoding="utf-8")
    queue=tmp_path/"queue.md"
    queue.write_text("### [TASK-EXISTING]\n- **状态**：queued\n",encoding="utf-8")
    root=tmp_path/"isolated-state"
    initialize(original,queue,root)
    secret=tmp_path/"test-key.bin"
    secret.write_bytes(bytes(range(1,33)))
    if os.name!="nt":
        secret.chmod(0o600)
    with original.open("a",encoding="utf-8") as f:
        f.write(request("TASK-S1-TEST-A","s1-a"))
    tick(original,root)
    return original,queue,root,secret


def receipt_paths(example):
    src,_,root,key=example
    return src,root,key,root/"test-receipts.json"


def test_valid_test_only_signed_receipt_and_independent_verifier(example):
    src,root,key,receipt=receipt_paths(example)
    result=issue(root,src,key,receipt)
    assert result["test_receipt_count"]==1
    assert result["production_sage_intake_signed"] is False
    answer=verify(root,src,key,receipt)
    assert answer["test_receipt_count"]==1
    assert answer["source_state_and_queue_verified"] is True
    assert answer["independent_sage_provider_authentication"] is False
    body=receipt.read_text(encoding="utf-8")
    assert "TASK-S1-TEST-A" not in body
    assert "s1-a" not in body
    assert "Synthetic test only" not in body


def test_two_sequential_commits_both_link_back_to_original_source(example):
    src,_,root,key=example
    with src.open("a",encoding="utf-8") as f:
        f.write(request("TASK-S1-TEST-B","s1-b"))
    tick(src,root)
    receipt=root/"multiple.json"
    assert issue(root,src,key,receipt)["test_receipt_count"]==2
    assert verify(root,src,key,receipt)["test_receipt_count"]==2


def test_source_changes_after_intake_are_detected(example):
    src,_,root,key=example
    receipt=root/"signed.json"
    issue(root,src,key,receipt)
    src.write_bytes(src.read_bytes().replace(b"Synthetic",b"Incorrect"))
    with pytest.raises(ValueError,match="original source bytes"):
        verify(root,src,key,receipt)


def test_test_receipt_hmac_cannot_be_edited(example):
    src,_,root,key=example
    receipt=root/"signed.json"
    issue(root,src,key,receipt)
    data=json.loads(receipt.read_text(encoding="utf-8"))
    data["receipts"][0]["message"]["claim"]["claim"]="real_sage_accepted"
    receipt.write_text(json.dumps(data),encoding="utf-8")
    with pytest.raises(ValueError,match="signature mismatch"):
        verify(root,src,key,receipt)


def test_other_secret_does_not_verify(example,tmp_path):
    src,_,root,key=example
    receipt=root/"signed.json"
    issue(root,src,key,receipt)
    fake=tmp_path/"another-test-key"
    fake.write_bytes(b"z"*32)
    if os.name!="nt":
        fake.chmod(0o600)
    with pytest.raises(ValueError,match="metadata|signature mismatch"):
        verify(root,src,fake,receipt)


def test_receipt_claim_replayed_to_different_staging_state_rejected(example,tmp_path):
    src,queue,root,key=example
    receipt=root/"signed.json"
    issue(root,src,key,receipt)
    other=tmp_path/"different-stage"
    # Different original queue and independent initialization.
    src2=tmp_path/"other-outbox.md"
    src2.write_text(request("TASK-S1-HIST","hist"),encoding="utf-8")
    initialize(src2,queue,other)
    with src2.open("a",encoding="utf-8") as f:
        f.write(request("TASK-S1-TEST-X","other-native"))
    tick(src2,other)
    # Receipt must reside inside the root being independently verified.
    (other/"signed.json").write_bytes(receipt.read_bytes())
    with pytest.raises(ValueError,match="signed claims do not match"):
        verify(other,src2,key,other/"signed.json")


def test_staged_card_guard_removed_cannot_be_signed(example):
    src,_,root,key=example
    card=root/"queue.md"
    card.write_bytes(card.read_bytes().replace(b"STAGING_NOT_DISPATCHABLE",b"ALLOW_EXECUTION_NOT_ALLOWED"))
    with pytest.raises(ValueError,match="committed staged queue digest mismatch"):
        issue(root,src,key,root/"never.json")


def test_a_pending_transaction_must_recover_before_sign(example):
    src,_,root,key=example
    with src.open("a",encoding="utf-8") as f:
        f.write(request("TASK-S1-TEST-B","s1-b"))
    with pytest.raises(InjectedCrash):
        tick(src,root,crash_at="after_prepare")
    with pytest.raises(ValueError,match="recover pending"):
        issue(root,src,key,root/"premature.json")
    recover(root)
    assert issue(root,src,key,root/"after-recovery.json")["test_receipt_count"]==2


def test_wrong_receipt_location_rejected(example,tmp_path):
    src,_,root,key=example
    with pytest.raises(ValueError,match="private staging root"):
        issue(root,src,key,tmp_path/"outside.json")


def test_duplicate_receipt_cannot_overwrite(example):
    src,_,root,key=example
    receipt=root/"signed.json"
    issue(root,src,key,receipt)
    data=receipt.read_bytes()
    with pytest.raises(FileExistsError):
        issue(root,src,key,receipt)
    assert receipt.read_bytes()==data


def test_signer_never_reclassifies_historic_task_as_new(example):
    src,_,root,key=example
    receipt=root/"signed.json"
    issue(root,src,key,receipt)
    body=json.loads(receipt.read_text(encoding="utf-8"))
    assert body["production_sage_intake_signed"] is False
    assert body["receipts"][0]["message"]["claim"]["claim"] == (
        "private_staging_card_committed_not_dispatched"
    )
    assert body["signer_role"]=="research_lab_staging_controller_only"
    assert len(body["receipts"])==1


def test_no_zero_task_signed_receipt(tmp_path):
    src=tmp_path/"source.md"
    src.write_text(request("TASK-S1-OLD","old-id"),encoding="utf-8")
    q=tmp_path/"queue.md"
    q.write_text("### [TASK-OTHER]\n",encoding="utf-8")
    root=tmp_path/"root"
    initialize(src,q,root)
    key=tmp_path/"k"
    key.write_bytes(b"y"*32)
    if os.name!="nt":
        key.chmod(0o600)
    with pytest.raises(ValueError,match="cannot sign zero"):
        issue(root,src,key,root/"none.json")


def test_mode_644_test_key_rejected_on_unix(example):
    if os.name=="nt":
        pytest.skip("Unix file modes not available")
    src,_,root,key=example
    key.chmod(0o644)
    with pytest.raises(ValueError,match="permissions"):
        issue(root,src,key,root/"no.json")
