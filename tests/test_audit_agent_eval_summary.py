from __future__ import annotations

import json

import pytest

from benchmarks.audit_agent_eval_summary import audit


def record(task, arm, *, passed=True, complete=False, seconds=20.0, cost=0.1):
    return {
        "task_id": task, "arm": arm, "model": "test-model", "seed": 1,
        "passed": passed, "workflow_complete": complete,
        "wall_seconds": seconds, "api_cost_usd": cost,
        "total_tokens": 100, "verified_by": "independent_tests",
    }


def save(path, rows):
    path.write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    return path


def test_pairing_reports_no_causal_claim(tmp_path):
    rows = [
        record("one", "B2", seconds=10, complete=True),
        record("one", "B3", seconds=30, complete=False),
        record("two", "B2", seconds=20, complete=True),
        record("two", "B3", seconds=40, complete=False),
    ]
    path = save(tmp_path / "paired.jsonl", rows)
    result = audit([path])
    assert result["n_records"] == 4 and result["n_matched_tasks"] == 2
    assert result["descriptive_paired_differences"]["paired_mean_B3_minus_B2_wall_seconds"] == 20
    assert result["per_arm"]["B2"]["workflow_complete"] == 2
    assert result["per_arm"]["B3"]["workflow_complete"] == 0
    assert result["status"] == "observational-agent-run-summary-only"


def test_duplicate_arm_rejected(tmp_path):
    rows = [record("one", "B2"), record("one", "B2")]
    with pytest.raises(ValueError, match="duplicate"):
        audit([save(tmp_path / "duplicate.jsonl", rows)])


def test_unpaired_does_not_fabricate_delta(tmp_path):
    result = audit([save(tmp_path / "unpaired.jsonl", [record("only", "B2")])])
    assert result["n_matched_tasks"] == 0
    assert result["n_unmatched_tasks"] == 1
    assert result["descriptive_paired_differences"]["paired_mean_B3_minus_B2_wall_seconds"] is None


@pytest.mark.parametrize("field,value", [
    ("passed", "true"), ("workflow_complete", 1),
    ("wall_seconds", -1), ("api_cost_usd", float("nan")),
    ("total_tokens", "100"), ("verified_by", ""),
])
def test_invalid_metadata_rejected(tmp_path, field, value):
    item = record("one", "B2")
    item[field] = value
    with pytest.raises(ValueError):
        audit([save(tmp_path / "invalid.jsonl", [item])])
