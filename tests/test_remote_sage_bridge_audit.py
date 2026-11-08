"""Offline tests of exact remote Bridge source parsing and trust boundaries."""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

from benchmarks import remote_sage_bridge_audit as module


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "bridge"
    path.mkdir()
    (path / "04-MAC_OUTBOX.md").write_text(
        "### [2026-11-08 09:01:00 请求：TASK-ONE]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：n-one\n"
        "- **任务ID（建议）**：TASK-ONE\n"
        "### [2026-11-08 09:02:00 请求：TASK-TWO]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：n-two\n"
        "- **任务ID（建议）**：TASK-TWO\n"
        "### [2026-11-08 09:03:00 请求：TASK-THREE]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：n-three\n"
        "- **任务ID（建议）**：TASK-THREE\n",
        encoding="utf-8",
    )
    (path / "02-MAC_TASK_QUEUE.md").write_text(
        "### [TASK-ONE]\n- **s1_ref**：n-one\n- **状态**：queued\n"
        "### [TASK-TWO]\n- **状态**：queued\n", encoding="utf-8")
    (path / "02-MAC_TASK_QUEUE-ARCHIVE.md").write_text(
        "### [TASK-ONE]\n- **状态**：done\n"
        "### [TASK-ONE]\n- **状态**：done\n", encoding="utf-8")
    (path / "07-MAC_TASK_STATE.json").write_text(
        json.dumps({"tasks":{"TASK-ONE":{"kind":"done"},"TASK-OTHER":{}}}),
        encoding="utf-8")
    return path


@pytest.fixture
def mapping():
    return [
        ("n-one","TASK-ONE","COMPLETED",None),
        ("n-two","TASK-TWO","COMPLETED",None),
        ("n-three","TASK-THREE","CREATED",None),
    ]


def test_source_inspection_read_only_and_disambiguated(source,mapping):
    paths=list(source.iterdir())
    before={p:p.read_bytes() for p in paths}
    r=module.inspect_local_snapshot(source,mapping)
    assert r["native_s1_mapping_rows_examined"]==3
    assert r["exact_remote_outbox_submission_matches"]==3
    assert r["remote_outbox_missing_exact_pairs"]==0
    assert r["remote_queue_provider_id_present"]==2
    assert r["remote_queue_matching_s1_ref"]==1
    assert r["remote_archive_provider_id_present"]==1
    assert r["remote_archive_duplicate_card_ids"]==1
    assert r["remote_archive_done_raw_untrusted"]==1
    assert r["remote_archive_done_source_grain_admissible"]==0
    assert r["remote_watchdog_provider_id_present"]==1
    assert before=={p:p.read_bytes() for p in paths}
    assert "n-one" not in json.dumps(r)
    assert "TASK-ONE" not in json.dumps(r)


def test_missing_exact_pair_is_not_remote_receipt(source,mapping):
    path=source/"04-MAC_OUTBOX.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "**s1_ref**：n-two","**s1_ref**：n-unrelated"),encoding="utf-8")
    r=module.inspect_local_snapshot(source,mapping)
    assert r["exact_remote_outbox_submission_matches"]==2
    assert r["remote_outbox_missing_exact_pairs"]==1


def test_duplicate_outbox_submission_never_counts_as_unique(source,mapping):
    path=source/"04-MAC_OUTBOX.md"
    s=path.read_text(encoding="utf-8")
    path.write_text(s+s.split("### [2026-11-08 09:02:00")[0],encoding="utf-8")
    r=module.inspect_local_snapshot(source,mapping)
    assert r["exact_remote_outbox_submission_matches"]==2
    assert r["remote_outbox_duplicate_exact_pairs"]==1


def test_conflicting_card_ref_is_not_exact(source,mapping):
    path=source/"02-MAC_TASK_QUEUE.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "**s1_ref**：n-one","**s1_ref**：someone-else"),encoding="utf-8")
    r=module.inspect_local_snapshot(source,mapping)
    assert r["remote_queue_provider_id_present"]==2
    assert r["remote_queue_matching_s1_ref"]==0


def test_no_duplicate_archive_admits_only_source_status_not_acceptance(source,mapping):
    path=source/"02-MAC_TASK_QUEUE-ARCHIVE.md"
    path.write_text("### [TASK-ONE]\n- **状态**：done\n",encoding="utf-8")
    r=module.inspect_local_snapshot(source,mapping)
    assert r["remote_archive_duplicate_card_ids"]==0
    assert r["remote_archive_done_source_grain_admissible"]==1
    # This only means the archive contains a 'done' state, not independent acceptance.


def test_untrusted_missing_remote_file_is_error(source,mapping):
    (source/"04-MAC_OUTBOX.md").unlink()
    with pytest.raises(ValueError,match="isolated source snapshot program"):
        module.inspect_local_snapshot(source,mapping)


def test_remote_program_rejects_symlinked_source(source,mapping,tmp_path):
    p=source/"04-MAC_OUTBOX.md"
    p.rename(tmp_path/"original.md")
    try:
        p.symlink_to(tmp_path/"original.md")
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError,match="isolated source snapshot program"):
        module.inspect_local_snapshot(source,mapping)


def test_ssh_config_parse_does_not_eval_shell(tmp_path):
    p=tmp_path/"push.sh"
    p.write_text("VPS_HOST='safe.example'\nVPS_BRIDGE='/safe/base'\n",encoding="utf-8")
    assert module._ssh_settings(p)=={"VPS_HOST":"safe.example","VPS_BRIDGE":"/safe/base"}
    p.write_text("VPS_HOST='$(unsafe)'\nVPS_BRIDGE='/safe/base'\n",encoding="utf-8")
    with pytest.raises(ValueError,match="unsupported"):
        module._ssh_settings(p)


def test_sha_field_and_mapping_cardinality_validation(source,mapping,monkeypatch,tmp_path):
    import sqlite3
    db=tmp_path/"s1.db"
    conn=sqlite3.connect(db)
    conn.executescript("""CREATE TABLE tasks(id TEXT,due_at TEXT);
        CREATE TABLE agent_executions(
        s1_task_id TEXT,provider TEXT,provider_task_id TEXT,status TEXT);""")
    conn.executemany("INSERT INTO agent_executions VALUES (?,?,?,?)",[
        (native,"sage",provider,status) for native,provider,status,_ in mapping])
    conn.commit();conn.close()
    push=tmp_path/"push.sh"
    push.write_text("VPS_HOST='fake'\nVPS_BRIDGE='/fake'\n",encoding="utf-8")
    sample=module.inspect_local_snapshot(source,mapping)
    def fake_run(args,**kwargs):
        assert kwargs.get("encoding") == "utf-8"
        return SimpleNamespace(returncode=0,stdout=json.dumps(sample),stderr="")
    monkeypatch.setattr(module.subprocess,"run",fake_run)
    actual=module.audit(db,push)
    assert actual["provider_source_receipt_cryptographically_signed"] is False
    assert actual["native_s1_to_webclip_message_join_verified"] is None
    sample["remote_bridge_files"]["04-MAC_OUTBOX.md"]["sha256"]="wrong"
    with pytest.raises(ValueError,match="source file digest"):
        module.audit(db,push)
