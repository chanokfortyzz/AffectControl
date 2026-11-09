from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1] / "benchmarks" / "trace_paired_eval.py"
spec = importlib.util.spec_from_file_location("trace_paired_eval", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def fixture(tmp_path, count=10, *, duration_basis="measured"):
    # Authored simulation test only; NOT external research evidence.
    manifest = []
    for i in range(count):
        tid = f"case-{i}"
        events = [
            {"at_s": 0, "kind": "arrive", "task_id": f"{tid}-background",
             "payload": {"text": "finish a routine report", "duration_s": 18,
                         "deadline_s": 80, "priority": "P2"}},
            {"at_s": 5, "kind": "arrive", "task_id": f"{tid}-urgent",
             "payload": {"text": "please review right now", "duration_s": 3,
                         "deadline_s": 12, "priority": "P3", "immediate": True}},
        ]
        raw = ("\n".join(json.dumps(x) for x in events) + "\n").encode()
        path = tmp_path / f"{tid}.jsonl"
        path.write_bytes(raw)
        manifest.append({
            "session_id": tid, "lineage_id": tid,
            "source": "unit-test-authored-not-external",
            "trace_file": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "duration_basis": duration_basis,
            "deadline_basis": "observed",
        })
    path = tmp_path / "manifest.jsonl"
    path.write_text("\n".join(map(json.dumps, manifest)))
    return path


def test_validation_partition_runs_two_real_implementations(tmp_path):
    manifest = fixture(tmp_path)
    report = mod.paired_replay(tmp_path, manifest)
    assert report["partition"] == "validation"
    assert report["n_eligible_sessions"] >= 1
    assert report["n_excluded_unverified_sessions"] == 0
    assert report["primary_metric"] == "deadline_miss_rate"
    assert report["inferential_status"] == "offline-exogenous-replay-only"
    assert report["paired_results"]["deadline_miss_rate"]["n_lineages"] >= 1
    assert report["paired_results"]["deadline_miss_rate"]["delta"] is not None
    assert report["split_sha256"] == mod.paired_replay(tmp_path, manifest)["split_sha256"]


def test_test_data_requires_explicit_unlock(tmp_path):
    manifest = fixture(tmp_path)
    with pytest.raises(ValueError, match="held-out test is locked"):
        mod.paired_replay(tmp_path, manifest, partition="test")
    result = mod.paired_replay(tmp_path, manifest, partition="test", unlock_test=True)
    assert result["partition"] == "test"


def test_synthetic_duration_is_excluded(tmp_path):
    manifest = fixture(tmp_path, duration_basis="synthetic")
    result = mod.paired_replay(tmp_path, manifest)
    assert result["n_eligible_sessions"] == 0
    assert result["n_excluded_unverified_sessions"] > 0
    assert result["paired_results"]["deadline_miss_rate"]["delta"] is None


def test_equal_lineage_weighting_not_event_weighting():
    rows = [
        {"lineage_id": "big", "affective": {"deadline_miss_rate": 1.0},
         "urgency": {"deadline_miss_rate": 0.0}}
        for _ in range(10)
    ]
    rows += [
        {"lineage_id": "small", "affective": {"deadline_miss_rate": 0.0},
         "urgency": {"deadline_miss_rate": 1.0}}
    ]
    stats = mod.lineage_paired_interval(rows, metric="deadline_miss_rate", samples=1000)
    assert stats["n_lineages"] == 2
    assert stats["delta"] == 0
    assert stats["ci95"] == [-1.0, 1.0]


def test_single_lineage_withholds_interval():
    rows = [
        {"lineage_id": "one", "affective": {"deadline_miss_rate": 0.4},
         "urgency": {"deadline_miss_rate": 0.2}}
    ]
    out = mod.lineage_paired_interval(rows, metric="deadline_miss_rate")
    assert out["n_lineages"] == 1
    assert out["delta"] == pytest.approx(0.2)
    assert out["ci95"] == [None, None]
