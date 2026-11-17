import json
import pytest
from affectcontrol.context_gate import normalize_context, assess_context
from affectcontrol.pilot import ShadowPilot, main
from affectcontrol.shadow_ingest import run


def _context(**changes):
    row = dict(
        current_task_running=True, current_task_preemptible=True,
        task_blocked=False, seconds_until_deadline=60,
        estimated_work_seconds=100,
    )
    row.update(changes)
    return row


def test_missing_context_abstains_not_negative(tmp_path):
    with ShadowPilot(tmp_path / "p.db") as p:
        d = p.decide(event_id="1", task_id="t", text="same words")
        assert d["operational_gate"]["verdict"] == "abstain"
        assert d["operational_gate"]["would_interrupt"] is None
        assert len(d["operational_gate"]["missing_fields"]) == 5
        assert p.report()["context_gate"]["abstained"] == 1


def test_context_changes_same_text_decision_with_transparent_slack(tmp_path):
    with ShadowPilot(tmp_path / "p.db") as p:
        critical = p.decide(event_id="a", task_id="t1", text="same words", context=_context())
        relaxed = p.decide(event_id="b", task_id="t2", text="same words",
                           context=_context(seconds_until_deadline=500))
        assert critical["recommendation"] == relaxed["recommendation"]
        assert critical["baseline"] == relaxed["baseline"]
        assert critical["operational_gate"]["verdict"] == "propose_interrupt"
        assert critical["operational_gate"]["deadline_slack_s"] == -40
        assert relaxed["operational_gate"]["verdict"] == "do_not_interrupt"
        assert relaxed["operational_gate"]["deadline_slack_s"] == 400
        assert p.report()["context_gate"]["proposed_interruptions"] == 1


@pytest.mark.parametrize("ctx,verdict", [
    (_context(task_blocked=True), "blocked_task"),
    (_context(current_task_running=False), "no_active_task"),
    (_context(current_task_preemptible=False), "safety_hold"),
    (_context(), "propose_interrupt"),
])
def test_safety_precedes_immediate(ctx, verdict):
    result = assess_context(ctx, explicit_user_immediate=True)
    assert result["verdict"] == verdict and not result["dispatch_allowed"]


@pytest.mark.parametrize("bad", [
    {"current_task_running": 1},
    {"current_task_running": "yes"},
    {"estimated_work_seconds": float("nan")},
    {"seconds_until_deadline": -1},
    {"seconds_until_deadline": float("inf")},
    {"seconds_until_deadline": 10 ** 2000},
    {"user_authorized_action": True},
])
def test_reject_unsafe_metadata(bad):
    with pytest.raises(ValueError):
        normalize_context(_context(**bad))


def test_idempotent_context_hash_and_collision(tmp_path):
    with ShadowPilot(tmp_path / "p.db") as p:
        first = p.decide(event_id="1", task_id="t", text="same", context=_context())
        second = p.decide(event_id="1", task_id="t", text="same", context=dict(reversed(list(_context().items()))))
        assert first == second and first["state_step"] == 1
        with pytest.raises(ValueError, match="collision"):
            p.decide(event_id="1", task_id="t", text="same",
                     context=_context(seconds_until_deadline=500))
        assert p.report()["decisions"] == 1


def test_batch_context_ingest_and_bad_field_all_or_none(tmp_path):
    inp = tmp_path / "in.jsonl"; db = tmp_path / "p.db"; out = tmp_path / "out.jsonl"
    row = dict(event_id="one", task_id="t", text="do task", context=_context())
    inp.write_text(json.dumps(row) + "\n")
    result = run(db, inp, output=out)
    assert result["decisions"] == 1
    assert json.loads(out.read_text())["operational_gate"]["would_interrupt"] is True
    inp2 = tmp_path / "bad.jsonl"
    inp2.write_text(json.dumps(row) + "\n" + json.dumps({
        **row, "event_id": "bad", "context": _context(seconds_until_deadline=-2)
    }) + "\n")
    db2 = tmp_path / "bad.db"
    with pytest.raises(ValueError):
        run(db2, inp2)
    assert not db2.exists()


def test_cli_context_file(tmp_path, capsys):
    ctx = tmp_path / "ctx.json"
    ctx.write_text(json.dumps(_context()), encoding="utf-8")
    ret = main(["--db", str(tmp_path / "p.db"), "decide", "--event-id", "c",
                "--task-id", "t", "--text", "task", "--context-file", str(ctx)])
    assert ret == 0
    data = json.loads(capsys.readouterr().out)
    assert data["operational_gate"]["verdict"] == "propose_interrupt"
    assert data["dispatch_allowed"] is False
