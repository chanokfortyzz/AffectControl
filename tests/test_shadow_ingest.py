import json
import hashlib
import pytest
from affectcontrol.pilot import ShadowPilot
from affectcontrol.shadow_ingest import run, read_input, main


def _rows(path, data):
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in data) + "\n",
                    encoding="utf-8")
    return path


def test_batch_end_to_end_and_idempotency(tmp_path):
    db = tmp_path / "pilot.sqlite3"
    inp = _rows(tmp_path / "input.jsonl", [
        {"event_id":"a","task_id":"task-a","text":"routine work"},
        {"event_id":"b","task_id":"task-b","text":"urgent deadline submit today","priority":"P1"},
    ])
    out = tmp_path / "recommendations.jsonl"
    result = run(db, inp, output=out)
    assert result["decisions"] == 2 and result["dispatch_allowed"] is False
    assert result["input_sha256"] == hashlib.sha256(inp.read_bytes()).hexdigest()
    records = [json.loads(x) for x in out.read_text().splitlines()]
    assert [r["event_id"] for r in records] == ["a", "b"]
    assert all(r["mode"] == "shadow" and not r["dispatch_allowed"] for r in records)
    with ShadowPilot(db) as pilot:
        assert pilot.report()["scopes"] == 2
    second = run(db, inp)
    assert second["output_sha256"] == result["output_sha256"]
    with ShadowPilot(db) as pilot:
        assert pilot.report()["decisions"] == 2
        assert pilot.db.execute("SELECT payload FROM pilot_states WHERE scope='task-a'").fetchone()


def test_validation_fail_closed_before_mutating(tmp_path):
    db = tmp_path / "p.db"
    inp = _rows(tmp_path / "bad.jsonl", [
        {"event_id":"ok","task_id":"t","text":"routine"},
        {"event_id":"bad","task_id":"x","text":"task","immediate":True},
    ])
    with pytest.raises(ValueError, match="explicit immediate"):
        run(db, inp)
    assert not db.exists()
    with pytest.raises(ValueError, match="immediate"):
        run(db, _rows(tmp_path / "bool.jsonl", [
            {"event_id":"bad","task_id":"a","text":"yes","immediate":"true"}]))


def test_allow_explicit_override_still_no_dispatch(tmp_path):
    inp = _rows(tmp_path / "input.jsonl", [
        {"event_id":"override","task_id":"t","text":"不急","immediate":True},
    ])
    db = tmp_path / "pilot.db"
    run(db, inp, allow_immediate=True)
    with ShadowPilot(db) as pilot:
        row = pilot.db.execute("SELECT response FROM pilot_decisions").fetchone()[0]
        data = json.loads(row)
        assert data["recommendation"]["effective_priority"] == "P0"
        assert not data["dispatch_allowed"]


def test_refuse_duplicate_inputs_and_overwrite(tmp_path):
    row = {"event_id":"a","task_id":"t","text":"task"}
    inp = _rows(tmp_path / "dup.jsonl", [row,row])
    with pytest.raises(ValueError, match="duplicate"):
        read_input(inp)
    inp = _rows(tmp_path / "in.jsonl", [row])
    out = tmp_path / "out.jsonl"
    out.write_text("existing",encoding="utf-8")
    with pytest.raises(ValueError, match="exists"):
        run(tmp_path / "p.db", inp, output=out)
    assert out.read_text() == "existing"


def test_empty_and_oversized_input(tmp_path):
    empty = tmp_path / "empty.jsonl"; empty.write_text("")
    with pytest.raises(ValueError, match="empty"):
        read_input(empty)
    huge = tmp_path / "huge.jsonl"; huge.write_bytes(b"x" * (1024*1024+1))
    with pytest.raises(ValueError, match="exceeds"):
        read_input(huge)


def test_cli_report(tmp_path, capsys):
    inp = _rows(tmp_path / "input.jsonl", [{"event_id":"cli","task_id":"t","text":"task"}])
    assert main(["--db", str(tmp_path / "p.db"),"--input",str(inp)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert json.loads(lines[0])["event_id"] == "cli"
    assert json.loads(lines[-1])["batch_report"]["decisions"] == 1
