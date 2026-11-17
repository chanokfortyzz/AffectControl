import json
from affectcontrol.pilot import ShadowPilot
from affectcontrol.shadow_eval import evaluate


def _context(remaining, deadline):
    return {
        "current_task_running": True,
        "current_task_preemptible": True,
        "task_blocked": False,
        "estimated_work_seconds": remaining,
        "seconds_until_deadline": deadline,
    }


def _labels(path, items):
    path.write_text(
        "".join(json.dumps({
            "event_id": event_id, "should_interrupt": truth,
            "reviewer_id": "independent-reviewer",
            "split": "holdout", "label_origin": "independent_human",
        }) + "\n" for event_id, truth in items))
    return path


def test_context_evaluation_has_explicit_abstention_and_fair_subset(tmp_path):
    db = tmp_path / "p.db"
    with ShadowPilot(db) as p:
        p.decide(event_id="urgent", task_id="t1", text="same words",
                 context=_context(80, 20))
        p.decide(event_id="safe", task_id="t2", text="same words",
                 context=_context(20, 80))
        p.decide(event_id="absent", task_id="t3", text="same words")
    labels = _labels(tmp_path / "labels.jsonl", [
        ("urgent", True), ("safe", False), ("absent", True)])
    out = evaluate(db, labels, minimum=3)
    assert out["context_gate"]["non_override_eligible"] == 2
    assert out["context_gate"]["non_override_coverage"] == 2 / 3
    assert out["context_gate"]["verdict_counts"]["abstain"] == 1
    subset = out["context_gate"]["matched_subset"]
    assert subset["context_gate"]["accuracy"] == 1.0
    assert subset["affective"]["n"] == 2
    assert subset["urgency_only"]["n"] == 2
    assert out["production_decision"] == "NOT_APPROVED"
    assert out["label_trust"].startswith("self-declared")


def test_context_safety_hold_refuses_urgent_preemption(tmp_path):
    db = tmp_path / "p.db"
    with ShadowPilot(db) as p:
        result = p.decide(event_id="unsafe", task_id="t1", text="submit today",
                          immediate=True, context={
                              **_context(120, 10), "current_task_preemptible": False
                          })
        assert result["recommendation"]["effective_priority"] == "P0"
        assert result["operational_gate"]["verdict"] == "safety_hold"
        assert result["operational_gate"]["would_interrupt"] is False
        assert result["dispatch_allowed"] is False
