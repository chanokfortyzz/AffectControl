from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1] / "benchmarks" / "appraisal_compare.py"
spec = importlib.util.spec_from_file_location("appraisal_compare_cluster", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def row(cid, i, pa, pb):
    return {
        "id": f"{cid}:{i}", "cluster_id": cid, "label": 0,
        "predictions": {"a": pa, "b": pb},
    }


def test_cluster_unit_prevents_long_sessions_dominating_effect():
    # One 10-event session versus two one-event sessions.
    rows = [row("long", i, 1, 0) for i in range(10)]
    rows += [row("short1", 0, 0, 1), row("short2", 0, 0, 1)]
    out = mod.paired_brier_bootstrap(rows, "a", "b", samples=1000)
    assert out["n"] == 12 and out["n_clusters"] == 3
    assert out["resampling_unit"] == "session"
    assert out["delta_brier_a_minus_b"] == pytest.approx(-1 / 3)
    assert out["ci95"][0] <= out["delta_brier_a_minus_b"] <= out["ci95"][1]
    assert out == mod.paired_brier_bootstrap(rows, "a", "b", samples=1000)


def test_no_cluster_produces_point_only():
    rows = [{"id": "s1", "label": 0, "predictions": {"a": 0.1, "b": 0.2}}]
    result = mod.paired_brier_bootstrap(rows, "a", "b")
    assert result["ci95"] == [None, None]
    assert result["resampling_unit"] == "descriptive_rows"


def test_one_cluster_insufficient_for_ci():
    rows = [row("only", i, 0.1, 0.2) for i in range(4)]
    result = mod.paired_brier_bootstrap(rows, "a", "b")
    assert result["n_clusters"] == 1
    assert result["ci95"] == [None, None]


def test_partial_cluster_ids_fail_closed():
    rows = [row("x", 1, 0.1, 0.2),
            {"id": "y", "label": 0, "predictions": {"a": 0.1, "b": 0.2}}]
    with pytest.raises(ValueError, match="partial cluster"):
        mod.paired_brier_bootstrap(rows, "a", "b")


def test_same_id_rejected_and_nonfinite_scores_rejected(tmp_path):
    p = tmp_path / "rows.jsonl"
    row0 = row("x", 1, 0.1, 0.2)
    p.write_text("\n".join(json.dumps(x) for x in [row0, row0]))
    with pytest.raises(ValueError, match="duplicate case id"):
        mod.compare(p)
    row0["predictions"]["a"] = float("nan")
    p.write_text(json.dumps(row0))
    with pytest.raises(ValueError, match="outside"):
        mod.compare(p)


def test_session_id_alias_and_common_case_subset(tmp_path):
    rows = [row("x", 1, 0.1, 0.2), row("y", 1, 0.9, 0.2)]
    for r in rows:
        r["session_id"] = r.pop("cluster_id")
    rows.append({"id": "missing", "session_id": "z", "label": 0,
                 "predictions": {"a": 0.2}})
    p = tmp_path / "rows.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in rows))
    result = mod.compare(p)
    pair = result["paired_brier"]["a__vs__b"]
    assert pair["n"] == 2
    assert pair["n_clusters"] == 2
    assert pair["resampling_unit"] == "session"
    assert result["providers"]["a"]["n"] == 3
    assert result["providers"]["b"]["n"] == 2


def test_invalid_cluster_identifier_rejected(tmp_path):
    data = row("x", 1, 0.1, 0.2)
    data["cluster_id"] = ""
    p = tmp_path / "rows.jsonl"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="cluster_id"):
        mod.compare(p)
