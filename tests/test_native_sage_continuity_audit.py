"""Portable fixtures for read-only native S1/Sage continuity evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import pytest

from benchmarks.native_sage_continuity_audit import audit, read_cards


@pytest.fixture
def evidence(tmp_path):
    db=tmp_path/"s1.db"
    con=sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE tasks(id TEXT,due_at TEXT);
    CREATE TABLE agent_executions(s1_task_id TEXT,provider TEXT,provider_task_id TEXT,status TEXT);
    """)
    con.executemany("INSERT INTO tasks VALUES (?,?)",[
        ("native1",""),("native2",""),("native3","")
    ])
    con.executemany("INSERT INTO agent_executions VALUES (?,?,?,?)",[
        ("native1","sage","TASK-S1-AAA-20261108-0001","COMPLETED"),
        ("native2","sage","TASK-S1-BBB-20261108-0002","COMPLETED"),
        ("native3","sage","TASK-S1-CCC-20261108-0003","CREATED"),
    ])
    con.commit();con.close()
    queue=tmp_path/"queue.md"
    queue.write_text(
        "### [TASK-S1-AAA-20261108-0001]\n"
        "- **s1_ref**：native1\n- **状态**：done\n"
        "### [TASK-OTHER-ID]\n"
        "- **状态**：ready\n", encoding="utf-8"
    )
    state=tmp_path/"state.json"
    state.write_text(json.dumps({"tasks":{
        "TASK-S1-AAA-20261108-0001":{"kind":"done"},
        "TASK-OTHER-ID":{"kind":"ready"},
    }}))
    results=tmp_path/"results"
    results.mkdir()
    (results/"TASK-S1-AAA-20261108-0001.md").write_bytes(b"original deliverable A")
    (results/"TASK-S1-BBB-20261108-0002.md").write_bytes(b"original deliverable B")
    return db,queue,state,results


def test_sources_distinguish_provider_and_current_status_and_result(evidence):
    row=audit(*evidence)
    count=row["coverage"]
    assert row["native_to_sage_provider_mapping_count"]==3
    assert row["current_queue_card_count"]==2
    assert row["current_watchdog_task_count"]==2
    assert count["mapped_provider_cards_present"]==1
    assert count["mapped_card_explicit_s1_ref_matches"]==1
    assert count["mapped_provider_cards_absent_from_current_snapshot"]==2
    assert count["mapped_watchdog_entries_present"]==1
    assert count["mapped_watchdog_entries_absent_from_current_snapshot"]==2
    assert count["mapped_nonempty_result_files"]==2
    assert count["db_completed_with_nonempty_result"]==2
    assert count["mapped_result_files_missing"]==1
    assert row["verified_native_s1_to_webclip_message_join_count"]==0
    assert row["independent_task_business_acceptance"] is None
    assert row["natural_deadline_source_authenticated"] is None
    assert "original deliverable A" not in json.dumps(row)
    assert "native1" not in json.dumps(row)


def test_empty_delivery_not_reported_as_accepted(evidence):
    db,queue,state,results=evidence
    (results/"TASK-S1-AAA-20261108-0001.md").write_bytes(b"")
    r=audit(*evidence)
    assert r["coverage"]["mapped_nonempty_result_files"]==1
    assert r["coverage"]["mapped_empty_result_files"]==1
    assert r["independent_task_business_acceptance"] is None


def test_card_ref_mismatch_does_not_create_exact_provenance(evidence):
    db,queue,state,results=evidence
    queue.write_text(queue.read_text(encoding="utf-8").replace("native1","other-task"), encoding="utf-8")
    r=audit(*evidence)
    assert r["coverage"].get("mapped_card_explicit_s1_ref_matches",0)==0
    assert r["coverage"]["mapped_card_s1_ref_conflict"]==1


def test_duplicate_queue_card_fails_closed(evidence):
    db,queue,state,results=evidence
    queue.write_text(queue.read_text(encoding="utf-8")+"### [TASK-S1-AAA-20261108-0001]\n", encoding="utf-8")
    with pytest.raises(ValueError,match="duplicate"):
        audit(*evidence)


def test_provider_mapping_duplicate_fails_closed(evidence):
    db,queue,state,results=evidence
    con=sqlite3.connect(db)
    con.execute("INSERT INTO agent_executions VALUES (?,?,?,?)",(
        "native9","sage","TASK-S1-AAA-20261108-0001","CREATED"))
    con.commit();con.close()
    with pytest.raises(ValueError,match="ambiguously mapped"):
        audit(*evidence)


def test_unsafe_provider_path_rejected(evidence):
    db,queue,state,results=evidence
    con=sqlite3.connect(db)
    con.execute("INSERT INTO agent_executions VALUES (?,?,?,?)",(
        "native9","sage","../../secrets","CREATED"))
    con.commit();con.close()
    with pytest.raises(ValueError,match="unsafe Sage provider task"):
        audit(*evidence)


def test_corrupted_state_fails_closed(evidence):
    db,queue,state,results=evidence
    state.write_text("bad json")
    with pytest.raises(json.JSONDecodeError):
        audit(*evidence)


def test_symlink_result_file_refused(evidence,tmp_path):
    db,queue,state,results=evidence
    target=results/"TASK-S1-AAA-20261108-0001.md"
    target.unlink()
    foreign=tmp_path/"private"
    foreign.write_text("secret")
    try:
        target.symlink_to(foreign)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError,match="symlinked"):
        audit(*evidence)


def test_unmodified_source_files_and_deterministic_report(evidence):
    db,queue,state,results=evidence
    originals=[x.read_bytes() for x in (db,queue,state)]
    before=audit(*evidence)
    after=audit(*evidence)
    assert before==after
    assert originals==[x.read_bytes() for x in (db,queue,state)]


def _sample_outbox(tmp_path, *, lines=None):
    content = (
        "### [2026-11-08 09:00:00 请求：TASK-S1-AAA-20261108-0001]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：native1\n"
        "- **任务ID（建议）**：TASK-S1-AAA-20261108-0001\n"
        "- **目标**：some private test task content\n"
        "\n"
        "### [2026-11-08 09:01:00 请求：TASK-S1-BBB-20261108-0002]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：native2\n"
        "- **任务ID（建议）**：TASK-S1-BBB-20261108-0002\n"
        "### [2026-11-08 09:02:00 请求：TASK-S1-CCC-20261108-0003]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：native3\n"
        "- **任务ID（建议）**：TASK-S1-CCC-20261108-0003\n"
    )
    path = tmp_path / "outbox.md"
    path.write_bytes((content if lines is None else lines).encode("utf-8"))
    return path


def test_local_outbox_exact_native_and_provider_joint_matches(evidence,tmp_path):
    from benchmarks.native_sage_continuity_audit import read_outbox
    path=_sample_outbox(tmp_path)
    before=path.read_bytes()
    pairs,digest=read_outbox(path)
    assert len(pairs)==3 and len(digest)==64
    row=audit(*evidence,outbox_path=path)
    assert row["local_outbox_evidence_checked"] is True
    assert row["local_outbox_s1_request_entries"]==3
    assert row["coverage"]["matched_native_s1_provider_local_outbox_request"]==3
    assert row["coverage"].get("native_mapping_without_exact_local_outbox_request",0)==0
    assert row["local_outbox_delivery_confirmed"] is None
    assert row["verified_native_s1_to_webclip_message_join_count"]==0
    assert path.read_bytes()==before
    assert "some private test task content" not in json.dumps(row)
    assert "native1" not in json.dumps(row)


def test_outbox_missing_request_is_missing_evidence_not_failed_task(evidence,tmp_path):
    p=_sample_outbox(tmp_path)
    s=p.read_text(encoding="utf-8")
    p.write_bytes(s.split("### [2026-11-08 09:02:00")[0].encode("utf-8"))
    row=audit(*evidence,outbox_path=p)
    assert row["coverage"]["matched_native_s1_provider_local_outbox_request"]==2
    assert row["coverage"]["native_mapping_without_exact_local_outbox_request"]==1
    assert row["independent_task_business_acceptance"] is None


def test_outbox_mismatched_native_ref_is_not_joined(evidence,tmp_path):
    p=_sample_outbox(tmp_path)
    s=p.read_text(encoding="utf-8").replace("**s1_ref**：native2","**s1_ref**：other")
    p.write_bytes(s.encode("utf-8"))
    r=audit(*evidence,outbox_path=p)
    assert r["coverage"]["matched_native_s1_provider_local_outbox_request"]==2
    assert r["coverage"]["outbox_provider_id_native_task_conflict"]==1


def test_outbox_duplicate_exact_request_fails_closed(evidence,tmp_path):
    p=_sample_outbox(tmp_path)
    s=p.read_text(encoding="utf-8")
    duplicate=s.split("### [2026-11-08 09:01:00")[0]
    p.write_bytes((s+duplicate).encode("utf-8"))
    with pytest.raises(ValueError,match="duplicate local"):
        audit(*evidence,outbox_path=p)


def test_outbox_unrelated_message_not_counted_as_submission(evidence,tmp_path):
    p=_sample_outbox(tmp_path)
    s=p.read_text(encoding="utf-8")
    s += (
        "### [2026-11-08 09:10:00 请求：TASK-S1-AAA-20261108-0001]\n"
        "- **类型**：完成报告\n"
        "- **s1_ref**：native1\n"
        "- **任务ID（建议）**：TASK-S1-AAA-20261108-0001\n"
    )
    p.write_bytes(s.encode("utf-8"))
    r=audit(*evidence,outbox_path=p)
    assert r["local_outbox_s1_request_entries"]==3
    assert r["coverage"]["matched_native_s1_provider_local_outbox_request"]==3


def test_malformed_or_non_utf8_outbox_source_rejected(evidence,tmp_path):
    p=_sample_outbox(tmp_path)
    p.write_bytes(b"\xff\xff")
    with pytest.raises(ValueError,match="not UTF-8"):
        audit(*evidence,outbox_path=p)


def test_outbox_not_supplied_remains_unknown_not_zero(evidence):
    row=audit(*evidence)
    assert row["local_outbox_evidence_checked"] is False
    assert row["local_outbox_s1_request_entries"] is None
    assert row["local_outbox_source_sha256"] is None


def test_outbox_unsafe_proposed_provider_id_rejected(evidence,tmp_path):
    p=_sample_outbox(tmp_path)
    s=p.read_text(encoding="utf-8").replace(
        "**任务ID（建议）**：TASK-S1-BBB-20261108-0002",
        "**任务ID（建议）**：../../private"
    )
    p.write_bytes(s.encode("utf-8"))
    with pytest.raises(ValueError,match="safe proposed Sage"):
        audit(*evidence,outbox_path=p)
