"""Evidence safeguards and paired evaluation smoke tests."""
import hashlib
import json
import pytest

from affectcontrol.pilot import ShadowPilot
from affectcontrol.shadow_eval import evaluate, main


def _labels(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")
    return path


def _label(event, truth, **extras):
    return {
        "event_id": event, "should_interrupt": truth, "reviewer_id": "external-rater-1",
        "split": "holdout", "label_origin": "independent_human", **extras,
    }


def test_paired_decisions_and_override_are_separate(tmp_path):
    db = tmp_path / "pilot.sqlite3"
    with ShadowPilot(db) as pilot:
        pilot.decide(event_id="a", task_id="task-a", text="routine report")
        pilot.decide(event_id="b", task_id="task-b", text="urgent deadline submit today")
        pilot.decide(event_id="c", task_id="task-c", text="不急", immediate=True)
    labels = _labels(tmp_path / "labels.jsonl", [
        _label("a", False), _label("b", True), _label("c", True)])
    result = evaluate(db, labels, minimum=2)
    assert result["pilot_decisions"] == 3
    assert result["oracle_labels"] == 3
    assert result["non_override"]["affective"]["n"] == 2
    assert result["explicit_user_override"]["n"] == 1
    assert result["explicit_user_override"]["affective_compliance"] == 1
    assert result["sample_gate_met"] is True
    assert result["production_decision"] == "NOT_APPROVED"
    assert result["non_override"]["cluster_bootstrap_95ci_delta"] is not None


def test_no_labels_for_unseen_event_and_duplicates(tmp_path):
    db = tmp_path / "pilot.sqlite3"
    with ShadowPilot(db) as pilot:
        pilot.decide(event_id="a", task_id="task-a", text="routine report")
    with pytest.raises(ValueError, match="unknown decisions"):
        evaluate(db, _labels(tmp_path / "bad.jsonl", [_label("missing", True)]))
    with pytest.raises(ValueError, match="duplicate"):
        evaluate(db, _labels(tmp_path / "dup.jsonl", [_label("a", False), _label("a", True)]))


@pytest.mark.parametrize("bad", [
    {"should_interrupt": 1},
    {"split": "train"},
    {"label_origin": "synthetic"},
    {"reviewer_id": ""},
])
def test_reject_unreviewed_or_non_holdout_labels(tmp_path, bad):
    db = tmp_path / "p.db"
    with ShadowPilot(db) as pilot:
        pilot.decide(event_id="a", task_id="task", text="review")
    row = _label("a", False)
    row.update(bad)
    with pytest.raises(ValueError):
        evaluate(db, _labels(tmp_path / "bad.jsonl", [row]))


def test_hash_provenance_and_tampering(tmp_path):
    db = tmp_path / "p.db"
    artifact = tmp_path / "proof.json"
    artifact.write_text('{"ok":true}', encoding="utf-8")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with ShadowPilot(db) as pilot:
        pilot.decide(event_id="a", task_id="task", text="review")
    row = _label("a", True, evidence_file=str(artifact), evidence_sha256=sha)
    labels = _labels(tmp_path / "labels.jsonl", [row])
    result = evaluate(db, labels)
    assert result["artifact_hash_checked_labels"] == 1
    assert result["sample_gate_met"] is False
    artifact.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch"):
        evaluate(db, labels)


def test_never_write_during_evaluation(tmp_path):
    db = tmp_path / "p.db"
    with ShadowPilot(db) as pilot:
        pilot.decide(event_id="a", task_id="task", text="review")
        snapshot = pilot.db.execute("SELECT payload FROM pilot_states WHERE scope='task'").fetchone()[0]
    result = evaluate(db, _labels(tmp_path / "labels.jsonl", [_label("a", False)]))
    with ShadowPilot(db) as pilot:
        assert pilot.db.execute("SELECT payload FROM pilot_states WHERE scope='task'").fetchone()[0] == snapshot
        assert pilot.report()["reported_outcomes"] == 0
    assert result["label_coverage"] == 1.0


def test_cli_and_small_sample_gate(tmp_path, capsys):
    db = tmp_path / "p.db"
    with ShadowPilot(db) as pilot:
        pilot.decide(event_id="a", task_id="task", text="review")
    labels = _labels(tmp_path / "labels.jsonl", [_label("a", False)])
    assert main(["--db", str(db), "--labels", str(labels)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["sample_gate_met"] is False
    assert result["production_decision"] == "NOT_APPROVED"
