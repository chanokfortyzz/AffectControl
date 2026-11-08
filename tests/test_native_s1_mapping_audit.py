"""Synthetic private SQLite fixtures: source-free native mapping tests."""
from __future__ import annotations
import json
import sqlite3
import pytest

from benchmarks.native_s1_mapping_audit import audit


@pytest.fixture
def native(tmp_path):
    db=tmp_path/"s1.db"
    c=sqlite3.connect(db)
    c.executescript("""
    CREATE TABLE tasks(id TEXT, created_at TEXT, due_at TEXT, status TEXT);
    CREATE TABLE agent_executions(s1_task_id TEXT,provider TEXT,provider_task_id TEXT,status TEXT);
    CREATE TABLE events(task_id TEXT,meta TEXT);
    """)
    c.executemany("INSERT INTO tasks VALUES (?,?,?,?)",[
        ("task-a","2026-11-08T00:00Z","","completed"),
        ("task-b","2026-11-08T00:00Z","2026-11-10T20:00Z","running"),
        ("task-c","2026-11-08T00:00Z","","pending"),
    ])
    c.executemany("INSERT INTO agent_executions VALUES (?,?,?,?)",[
        ("task-a","sage","SAGE-001","COMPLETED"),
        ("task-b","sage","SAGE-002","CREATED"),
    ])
    c.execute("INSERT INTO events VALUES (?,?)",
              ("task-a",json.dumps({"thread_id":"th-unverified","request_id":"msg-unverified"})))
    c.execute("INSERT INTO events VALUES (?,?)",
              (None,json.dumps({"thread_id":"th-no-task","reply_message_id":"msg-unmatched"})))
    c.commit();c.close()
    return db


def test_native_provider_mapping_not_confused_with_bus_proof(native):
    result=audit(native)
    assert result["native_task_count"]==3
    assert result["native_s1_sage_provider_mapping_rows"]==2
    assert result["native_task_due_at_nonempty"]==1
    assert result["mapped_task_due_at_nonempty"]==1
    assert result["native_provider_reported_status_counts"]=={"COMPLETED":1,"CREATED":1}
    assert result["mapped_task_event_bus_meta_key_counts"]["thread_id"]==1
    assert result["verified_native_s1_to_real_bus_message_joins"]==0
    assert result["independent_agent_business_acceptance"] is None
    assert result["original_deadline_source_attested"] is None
    assert result["affectcontrol_policy_trial"] is None
    assert "task-a" not in json.dumps(result)
    assert "SAGE-001" not in json.dumps(result)


def test_invalid_source_schema_rejected(native):
    conn=sqlite3.connect(native)
    conn.execute("DROP TABLE agent_executions")
    conn.commit();conn.close()
    with pytest.raises(ValueError,match="unrecognized source schema"):
        audit(native)


def test_missing_native_task_reference_remains_coverage_issue(native):
    conn=sqlite3.connect(native)
    conn.execute("INSERT INTO agent_executions VALUES (?,?,?,?)",
                 ("orphan","sage","SAGE-003","CREATED"))
    conn.commit();conn.close()
    result=audit(native)
    assert result["missing_native_task_foreign_refs"]==1
    assert result["verified_native_s1_to_real_bus_message_joins"]==0


def test_unreadable_event_metadata_is_ignored_not_joined(native):
    conn=sqlite3.connect(native)
    conn.execute("INSERT INTO events VALUES (?,?)",("task-a","not-json"))
    conn.commit();conn.close()
    result=audit(native)
    assert result["mapped_task_event_bus_meta_key_counts"]["thread_id"]==1


def test_symlink_database_refused(native,tmp_path):
    target=tmp_path/"alias.db"
    try:
        target.symlink_to(native)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError,match="existing regular"):
        audit(target)
