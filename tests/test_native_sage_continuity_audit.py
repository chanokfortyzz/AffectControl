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
        "- **状态**：ready\n"
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
    queue.write_text(queue.read_text().replace("native1","other-task"))
    r=audit(*evidence)
    assert r["coverage"].get("mapped_card_explicit_s1_ref_matches",0)==0
    assert r["coverage"]["mapped_card_s1_ref_conflict"]==1


def test_duplicate_queue_card_fails_closed(evidence):
    db,queue,state,results=evidence
    queue.write_text(queue.read_text()+"### [TASK-S1-AAA-20261108-0001]\n")
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
