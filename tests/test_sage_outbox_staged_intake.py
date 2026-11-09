"""Regression suite for opt-in, non-production Outbox -> staging card flow."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from benchmarks.sage_outbox_staged_intake import bootstrap, parse_append, stage, SCHEMA


def s1_block(task, native, goal="safe local synthetic coding task"):
    return (
        f"\n\n### [2026-11-09 01:00:00 请求：{task}]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        f"- **s1_ref**：{native}\n"
        f"- **任务ID（建议）**：{task}\n"
        f"- **目标**：{goal}\n"
        "- **risk（建议）**：low\n"
    )


@pytest.fixture
def source(tmp_path):
    outbox=tmp_path/"outbox.md"
    old=s1_block("TASK-S1-OLD-0001","s1-old","historic must never replay")
    outbox.write_text(old+"\n",encoding="utf-8")
    queue=tmp_path/"queue.md"
    queue.write_text("### [TASK-PREVIOUS]\n- **状态**：queued\n",encoding="utf-8")
    baseline=tmp_path/"baseline.json"
    bootstrap(outbox,baseline)
    return outbox,queue,baseline,tmp_path


def test_real_append_only_stage_creates_one_private_non_dispatchable_card(source):
    outbox,queue,baseline,root=source
    old=outbox.read_bytes()
    outbox.write_bytes(old+s1_block("TASK-S1-NEW-0002","s1-new").encode())
    result=stage(outbox,baseline,queue,root/"rendered")
    assert result["new_candidate_count"]==1
    assert result["auto_dispatch_enabled"] is False
    assert result["real_receiver_accepted"] is None
    assert result["real_webclip_message_id"] is None
    card=(root/"rendered"/"staged-queue.md").read_text(encoding="utf-8")
    assert "TASK-S1-NEW-0002" in card
    assert "s1-new" in card
    assert "historic must never replay" not in card
    assert "STAGING_NOT_DISPATCHABLE" in card
    assert outbox.read_bytes().startswith(old)
    assert "s1-new" not in json.dumps(result)
    assert "TASK-S1-NEW-0002" not in json.dumps(result)


def test_bootstrap_does_not_replay_existing_requests(source):
    outbox,queue,baseline,root=source
    manifest=json.loads(baseline.read_text())
    assert manifest["historical_requests_replayed"]==0
    with pytest.raises(ValueError,match="no new S1 requests"):
        stage(outbox,baseline,queue,root/"none")


def test_prefix_tampering_blocks_stage(source):
    outbox,queue,baseline,root=source
    data=outbox.read_bytes()
    outbox.write_bytes(data.replace(b"historic",b"modified")+s1_block(
        "TASK-S1-NEW-0002","s1-new").encode())
    with pytest.raises(ValueError,match="prefix has been changed"):
        stage(outbox,baseline,queue,root/"modified")


def test_result_replies_do_not_create_new_task_cards(source):
    outbox,queue,baseline,root=source
    with outbox.open("a",encoding="utf-8") as f:
        f.write("\n\n### [2026-11-09 01:03:00 回复：TASK-S1-NEW-0002]\n"
                "- **类型**：local-worker 自动处理\n")
    with pytest.raises(ValueError,match="no new S1 requests"):
        stage(outbox,baseline,queue,root/"none")


def test_duplicate_new_native_id_rejected(source):
    outbox,queue,baseline,root=source
    with outbox.open("a",encoding="utf-8") as f:
        f.write(s1_block("TASK-S1-A","same-s1"))
        f.write(s1_block("TASK-S1-B","same-s1"))
    with pytest.raises(ValueError,match="duplicate native"):
        stage(outbox,baseline,queue,root/"dup")


def test_duplicate_new_provider_id_rejected(source):
    outbox,queue,baseline,root=source
    with outbox.open("a",encoding="utf-8") as f:
        f.write(s1_block("TASK-S1-A","s1-a"))
        f.write(s1_block("TASK-S1-A","s1-b"))
    with pytest.raises(ValueError,match="duplicate provider"):
        stage(outbox,baseline,queue,root/"dup")


def test_header_field_provider_mismatch_rejected(source):
    outbox,queue,baseline,root=source
    with outbox.open("a",encoding="utf-8") as f:
        f.write(s1_block("TASK-S1-A","s1-a").replace(
            "**任务ID（建议）**：TASK-S1-A","**任务ID（建议）**：TASK-S1-B"))
    with pytest.raises(ValueError,match="provider ID mismatch"):
        stage(outbox,baseline,queue,root/"mismatch")


def test_existing_queue_task_id_rejected(source):
    outbox,queue,baseline,root=source
    queue.write_text("### [TASK-S1-A]\n- **状态**：queued\n",encoding="utf-8")
    with outbox.open("a",encoding="utf-8") as f:
        f.write(s1_block("TASK-S1-A","s1-a"))
    with pytest.raises(ValueError,match="already in queue"):
        stage(outbox,baseline,queue,root/"collision")


def test_no_output_overwrite_on_repeated_stage(source):
    outbox,queue,baseline,root=source
    with outbox.open("a",encoding="utf-8") as f:
        f.write(s1_block("TASK-S1-A","s1-a"))
    stage(outbox,baseline,queue,root/"rendered")
    with pytest.raises(FileExistsError):
        stage(outbox,baseline,queue,root/"rendered")


def test_requires_complete_snapshot_at_bootstrap(tmp_path):
    source=tmp_path/"outbox"
    source.write_bytes(b"### [TASK-INCOMPLETE]")
    with pytest.raises(ValueError,match="incomplete Outbox"):
        bootstrap(source,tmp_path/"baseline.json")


def test_goal_cannot_cause_card_heading_injection(source):
    outbox,queue,baseline,root=source
    with outbox.open("a",encoding="utf-8") as f:
        f.write(s1_block("TASK-S1-A","s1-a","### [TASK-INJECTED]"))
    with pytest.raises(ValueError,match="task goal"):
        stage(outbox,baseline,queue,root/"unsafe")


def test_wrong_baseline_schema_rejected(source):
    outbox,queue,baseline,root=source
    data=json.loads(baseline.read_text())
    data["schema"]="fake-schema"
    baseline.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="unsupported baseline"):
        stage(outbox,baseline,queue,root/"wrong")


def test_source_symlink_is_refused(source):
    outbox,queue,baseline,root=source
    clone=root/"source-link"
    try:
        clone.symlink_to(outbox)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError,match="unsafe"):
        stage(clone,baseline,queue,root/"link")
