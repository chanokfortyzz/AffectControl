"""Shadow CLI tests: durable state, safety, idempotency, artifact integrity."""
import hashlib
import json
import sqlite3
import pytest

from affectcontrol.pilot import ShadowPilot, main


def test_decision_idempotence_scope_and_audit(tmp_path):
    db = tmp_path / "pilot.sqlite3"
    with ShadowPilot(db) as pilot:
        a = pilot.decide(event_id="a1", task_id="alpha", text="routine work")
        again = pilot.decide(event_id="a1", task_id="alpha", text="routine work")
        b = pilot.decide(event_id="b1", task_id="beta", text="urgent: submit today")
        assert a == again and a["state_step"] == 1
        assert b["scope"] == "beta"
        assert pilot.report()["decisions"] == 2
        assert pilot.report()["scopes"] == 2
        assert a["dispatch_allowed"] is False
    with ShadowPilot(db) as pilot:
        assert pilot.decide(event_id="a1", task_id="alpha", text="routine work") == a
        assert pilot.decide(event_id="a2", task_id="alpha", text="routine work")["state_step"] == 2
        assert pilot.report()["tasks"] == 2


def test_explicit_user_override_is_not_demoted(tmp_path):
    with ShadowPilot(tmp_path / "p.db") as p:
        out = p.decide(event_id="i", task_id="urgent", text="不急，不用马上",
                       priority="P3", immediate=True)
        assert out["recommendation"]["effective_priority"] == "P0"
        assert out["recommendation"]["should_interrupt"] is True
        assert out["baseline"]["should_interrupt"] is True


def test_replay_collision_does_not_mutate_state(tmp_path):
    with ShadowPilot(tmp_path / "p.db") as p:
        p.decide(event_id="id", task_id="a", text="routine")
        with pytest.raises(ValueError, match="collision"):
            p.decide(event_id="id", task_id="a", text="changed")
        assert p.report()["decisions"] == 1
        assert p.db.execute("SELECT COUNT(*) FROM pilot_states").fetchone()[0] == 1


def test_feedback_is_atomic_and_reports_only_provenance(tmp_path):
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("checked bytes", encoding="utf-8")
    expected = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with ShadowPilot(tmp_path / "p.db") as p:
        p.decide(event_id="result", task_id="a", text="produce an artifact")
        before = p.db.execute("SELECT payload FROM pilot_states WHERE scope='a'").fetchone()[0]
        with pytest.raises(ValueError, match="mismatch"):
            p.feedback(event_id="result", status="success", evidence_file=artifact,
                       expected_sha256="0" * 64)
        assert p.db.execute("SELECT payload FROM pilot_states WHERE scope='a'").fetchone()[0] == before
        out = p.feedback(event_id="result", status="success", evidence_file=artifact,
                         expected_sha256=expected)
        assert out["artifact_integrity_checked"] is True
        assert out["outcome_independently_verified"] is False
        assert p.feedback(event_id="result", status="success", evidence_file=artifact,
                          expected_sha256=expected)["idempotent_replay"] is True
        assert p.report()["reported_outcomes"] == 1
        assert p.report()["artifact_hash_checks"] == 1
        with pytest.raises(ValueError, match="immutable"):
            p.feedback(event_id="result", status="failure")


def test_feedback_unknown_event_and_missing_evidence(tmp_path):
    with ShadowPilot(tmp_path / "p.db") as p:
        with pytest.raises(ValueError, match="unknown"):
            p.feedback(event_id="unknown", status="success")
        p.decide(event_id="known", task_id="a", text="task")
        with pytest.raises(ValueError, match="together"):
            p.feedback(event_id="known", status="success", evidence_file="/does/not/exist")
        assert p.report()["reported_outcomes"] == 0


def test_invalid_scope_and_text_fail_closed(tmp_path):
    with ShadowPilot(tmp_path / "p.db") as p:
        with pytest.raises(ValueError):
            p.decide(event_id="bad", task_id="", text="task")
        with pytest.raises(ValueError):
            p.decide(event_id="bad", task_id="a", text=" ")
        with pytest.raises(ValueError):
            p.decide(event_id="bad", task_id="a", text="valid", priority="P8")
        assert p.report()["decisions"] == 0


def test_cli_workflow(tmp_path, capsys):
    db = str(tmp_path / "cli.sqlite3")
    assert main(["--db", db, "decide", "--event-id", "cli1", "--task-id", "job1",
                 "--text", "review this"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "shadow"
    assert main(["--db", db, "feedback", "--event-id", "cli1", "--status", "partial"]) == 0
    assert main(["--db", db, "report"]) == 0
    data = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert data["reported_statuses"]["partial"] == 1
    assert data["independently_verified_outcomes"] == 0
