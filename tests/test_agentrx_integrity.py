from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1] / "benchmarks" / "agentrx_integrity.py"
spec = importlib.util.spec_from_file_location("agentrx_integrity", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def sample():
    traces = [{
        "task_id": 17,
        "reward": 0.0,
        "traj": [{"index": 1, "role": "system"},
                 {"index": 2, "role": "assistant"}],
    }]
    labels = [{
        "trajectory_id": 17,
        "failures": [{
            "failure_id": 4, "step_number": 2,
            "failure_category": "Invalid Invocation",
        }],
        "root_cause": {"failure_id": 4},
    }]
    return traces, labels


def test_pinned_external_shape_audit_has_no_efficacy_claim():
    out = mod.audit(*sample())
    assert out["n_labeled_trajectories"] == 1
    assert out["n_failure_annotations"] == 1
    assert out["n_valid_root_refs"] == 1
    assert out["n_success_rewards"] == 0
    assert out["inference_status"] == "source-integrity-only"


def test_reject_missing_trajectory():
    traces, labels = sample()
    labels[0]["trajectory_id"] = 19
    with pytest.raises(ValueError, match="without trajectory"):
        mod.audit(traces, labels)


def test_reject_bad_step_index():
    traces, labels = sample()
    labels[0]["failures"][0]["step_number"] = 3
    with pytest.raises(ValueError, match="step not found"):
        mod.audit(traces, labels)


def test_reject_inconsistent_root_failure():
    traces, labels = sample()
    labels[0]["root_cause"]["failure_id"] = 99
    with pytest.raises(ValueError, match="root failure_id"):
        mod.audit(traces, labels)


def test_reject_duplicate_trajectories():
    traces, labels = sample()
    with pytest.raises(ValueError, match="duplicate trajectory ID"):
        mod.audit(traces + traces, labels)
