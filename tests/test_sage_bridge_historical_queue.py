"""Source-free historical queue fixtures. Duplicated archives are excluded."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3

import pytest

from benchmarks.sage_bridge_historical_queue import audit, parse_snapshot


@pytest.fixture
def sources(tmp_path):
    db=tmp_path/"s1.db"
    connection=sqlite3.connect(db)
    connection.executescript("""
        CREATE TABLE tasks(id TEXT,due_at TEXT);
        CREATE TABLE agent_executions(
            s1_task_id TEXT,provider TEXT,provider_task_id TEXT,status TEXT);
    """)
    connection.executemany("INSERT INTO tasks VALUES (?,?)",
                           [("s1-one",None),("s1-two",None),("s1-three",None)])
    connection.executemany("INSERT INTO agent_executions VALUES (?,?,?,?)",[
        ("s1-one","sage","TASK-S1-ONE","COMPLETED"),
        ("s1-two","sage","TASK-S1-TWO","COMPLETED"),
        ("s1-three","sage","TASK-S1-THREE","CREATED"),
    ])
    connection.commit();connection.close()
    bridge=tmp_path/"bridge"
    bridge.mkdir()
    # The first card contains true in-card s1_ref, the second is only
    # the same provider ID in an old queue; third never had a card.
    (bridge/"02-MAC_TASK_QUEUE.md.bak-1").write_bytes(
        ("### [TASK-S1-ONE]\n- **s1_ref**：s1-one\n"
         "- **状态**：queued\n- **目标**：private text never exported\n").encode("utf-8")
    )
    (bridge/"02-MAC_TASK_QUEUE.md.bak-2").write_bytes(
        ("### [TASK-S1-TWO]\n- **状态**：queued\n").encode("utf-8")
    )
    # An archive can include a tempting "done" with duplicate same-card
    # sections. Its status must never count as usable evidence.
    (bridge/"02-MAC_TASK_QUEUE-ARCHIVE.md").write_bytes(
        ("### [TASK-S1-ONE]\n- **状态**：done\n"
         "### [TASK-S1-ONE]\n- **状态**：done\n").encode("utf-8")
    )
    outbox=bridge/"04-MAC_OUTBOX.md"
    outbox.write_bytes((
        "### [2026-11-08 09:00:00 请求：TASK-S1-ONE]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：s1-one\n- **任务ID（建议）**：TASK-S1-ONE\n"
        "### [2026-11-08 09:01:00 请求：TASK-S1-TWO]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：s1-two\n- **任务ID（建议）**：TASK-S1-TWO\n"
        "### [2026-11-08 09:02:00 请求：TASK-S1-THREE]\n"
        "- **类型**：新任务请求（来自 S1）\n"
        "- **s1_ref**：s1-three\n- **任务ID（建议）**：TASK-S1-THREE\n"
    ).encode("utf-8"))
    return db, bridge, outbox


def test_three_stage_history_does_not_justify_remote_ack_or_success(sources):
    db,bridge,outbox=sources
    result=audit(db,bridge,outbox)
    counts=result["coverage"]
    assert counts["mapped_native_s1_tasks"]==3
    assert counts["mapped_tasks_with_historical_provider_id_card"]==2
    assert counts["mapped_tasks_with_explicit_matching_s1_ref_card"]==1
    assert counts["mapped_tasks_with_provider_id_only_card"]==1
    assert counts["mapped_tasks_without_any_historical_queue_card"]==1
    assert counts["mapped_tasks_with_historical_queued_card"]==2
    assert counts.get("mapped_tasks_with_historical_done_card",0)==0
    assert counts["duplicate_card_snapshots_excluded"]==1
    assert counts["eligible_historical_queue_snapshots"]==2
    assert result["historical_queue_snapshots_examined"]==3
    assert result["outbox_evidence"]["exact_local_submission_matches"]==3
    assert result["outbox_evidence"]["remote_delivery_confirmed"] is None
    assert result["independently_authenticated_remote_sage_ack"] is None
    assert result["verified_native_s1_webclip_message_join"] is None
    assert "private text" not in json.dumps(result)
    assert "s1-one" not in json.dumps(result)


def test_unknown_outbox_is_null_not_zero(sources):
    db,bridge,_=sources
    assert audit(db,bridge)["outbox_evidence"] is None


def test_conflicting_s1_ref_card_is_not_exact_match(sources):
    db,bridge,outbox=sources
    path=bridge/"02-MAC_TASK_QUEUE.md.bak-1"
    path.write_bytes(path.read_bytes().replace(b"s1-one",b"wrong"))
    report=audit(db,bridge,outbox)
    c=report["coverage"]
    assert c.get("mapped_tasks_with_explicit_matching_s1_ref_card",0)==0
    assert c["mapped_tasks_with_conflicting_s1_ref_card"]==1


def test_duplicate_card_file_rejected_by_parser(sources):
    _,bridge,_=sources
    with pytest.raises(ValueError,match="duplicate source card"):
        parse_snapshot(bridge/"02-MAC_TASK_QUEUE-ARCHIVE.md")


def test_corrupt_non_utf8_file_is_not_silently_excluded(sources):
    db,bridge,outbox=sources
    (bridge/"02-MAC_TASK_QUEUE.md.bak-1").write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        audit(db,bridge,outbox)


def test_unknown_native_mapping_provider_conflict_fails_closed(sources):
    db,bridge,outbox=sources
    connection=sqlite3.connect(db)
    connection.execute("INSERT INTO agent_executions VALUES (?,?,?,?)",
                       ("another","sage","TASK-S1-ONE","CREATED"))
    connection.commit();connection.close()
    with pytest.raises(ValueError,match="ambiguous"):
        audit(db,bridge,outbox)


def test_duplicate_local_outbox_request_fails_closed(sources):
    db,bridge,outbox=sources
    outbox.write_bytes(outbox.read_bytes()+outbox.read_bytes())
    with pytest.raises(ValueError,match="duplicate native/provider"):
        audit(db,bridge,outbox)


def test_source_snapshots_unchanged_by_audit(sources):
    db,bridge,outbox=sources
    paths=[db,outbox,*sorted(bridge.glob("02-MAC_TASK_QUEUE*"))]
    before={p:p.read_bytes() for p in paths}
    report=audit(db,bridge,outbox)
    assert report==audit(db,bridge,outbox)
    assert before=={p:p.read_bytes() for p in paths}


def test_symlink_archive_rejected_if_present(sources,tmp_path):
    db,bridge,outbox=sources
    filename=bridge/"02-MAC_TASK_QUEUE.md.bak-3"
    try:
        filename.symlink_to(tmp_path/"not-allowed")
    except OSError:
        pytest.skip("symlink unsupported")
    # The audit will not follow a new symlink. It is not counted as a valid
    # snapshot, nor allowed to inject private file contents.
    result=audit(db,bridge,outbox)
    assert result["historical_queue_snapshots_examined"]==3
