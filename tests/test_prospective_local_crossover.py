from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.prospective_local_crossover import TASKS, choose, freeze_plan, run


def test_frozen_plan_deterministic_and_has_conspicuous_limits():
    first = freeze_plan(pairs=4, seed=42)
    assert first == freeze_plan(pairs=4, seed=42)
    assert len(first["arm_orders"]) == 4
    assert all(sorted(order) == ["affective", "urgency"] for order in first["arm_orders"])
    assert first["status"] == "exploratory_E1_not_confirmatory"
    assert first["deadline_source"] == "experimental_assignment_not_observed_user_deadline"


@pytest.mark.parametrize("bad", [
    [dict(TASKS[0], test_file="../secret.py"), TASKS[1]],
    [dict(TASKS[0], deadline_s=float("nan")), TASKS[1]],
    [dict(TASKS[0], deadline_s=0), TASKS[1]],
    [TASKS[0], dict(TASKS[1], task_id=TASKS[0]["task_id"])],
])
def test_unsafe_or_ambiguous_workload_rejected(bad):
    with pytest.raises(ValueError):
        freeze_plan(tasks=bad)


def test_selection_uses_same_reference_model_and_does_not_consume_labels():
    selected_a, scores_a = choose(TASKS, "affective", 0.0)
    selected_b, scores_b = choose(TASKS, "urgency", 0.0)
    assert selected_a in TASKS and selected_b in TASKS
    assert set(scores_a) == set(scores_b) == {x["task_id"] for x in TASKS}
    assert all(isinstance(v, float) for v in scores_a.values())
    assert choose(TASKS, "affective", 0.0) == (selected_a, scores_a)


def test_one_pair_mock_processes_are_exploratory_only(tmp_path):
    calls = []
    def fake_capture(root, sid, lineage, argv, *, cwd, timeout_s):
        calls.append((sid, list(argv), lineage, timeout_s))
        return {"result": "exited", "exit_code": 0, "trace_sha256": "f" * 64}
    root = tmp_path / "fresh"
    project = Path(__file__).resolve().parents[1]
    result = run(project, root, pairs=1, tasks=TASKS[:2], runner=fake_capture)
    assert len(calls) == 4
    assert result["n_independent_project_lineages"] == 1
    assert result["independent_outcome_acceptance"] is None
    assert result["evidence_level"] == "E1"
    assert result["ci95"] is None
    assert result["preemptions_observed"] == 0
    frozen = (root / "frozen-plan.json").read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == result["frozen_plan_sha256"]
    assert all(command[1][2] == "pytest" for command in calls)
    assert sorted(t["strategy"] for t in result["trials"]) == ["affective", "urgency"]
    with pytest.raises(FileExistsError):
        run(project, root, pairs=1, tasks=TASKS[:2], runner=fake_capture)
    assert len(calls) == 4


def test_unapproved_test_command_cannot_be_run(tmp_path):
    project = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="allowlist"):
        run(project, tmp_path / "fresh", pairs=1,
            tasks=[TASKS[0], dict(TASKS[1], test_file="etc/passwd")],
            runner=lambda *args, **kwargs: None)
    assert not (tmp_path / "fresh").exists()
