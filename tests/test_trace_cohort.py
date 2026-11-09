from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1] / "benchmarks" / "trace_cohort.py"
spec = importlib.util.spec_from_file_location("trace_cohort", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def row(at, kind, task, payload=None):
    return {"at_s": at, "kind": kind, "task_id": task, "payload": payload or {}}


def trace_rows():
    return [
        row(0.0, "arrive", "a", {"duration_s": 12, "priority": "P2",
                                "deadline_s": 60, "preemptible": True}),
        row(2.0, "arrive", "b", {"duration_s": 4, "priority": "P1",
                                "deadline_s": 25}),
        row(6.0, "revise", "a", {"duration_delta_s": 1}),
        row(7.0, "cancel", "b"),
    ]


def bytes_of(rows):
    return ("\n".join(json.dumps(x) for x in rows) + "\n").encode()


def cohort(tmp_path, *, same_lineage=False):
    entries = []
    for i in range(6):
        session = f"session-{i}"
        filename = f"{session}.jsonl"
        raw = bytes_of([row(0, "arrive", session, {
            "duration_s": 3 + i, "deadline_s": 20, "priority": "P2",
        })])
        (tmp_path / filename).write_bytes(raw)
        entries.append({
            "session_id": session,
            "lineage_id": "same" if same_lineage else f"lineage-{i // 2}",
            "trace_file": filename,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source": "public:example",
            "duration_basis": "measured",
            "deadline_basis": "observed",
        })
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(x) for x in entries))
    return manifest, entries


def test_deterministic_splits_preserve_lineage_and_provenance(tmp_path):
    manifest, entries = cohort(tmp_path)
    report = mod.build_cohort(tmp_path, manifest)
    assert report["n_sessions"] == 6
    assert report["n_lineages"] == 3
    assert report["partition_session_counts"] == {
        "test": 2, "train": 2, "validation": 2,
    }
    mapped = {x["session_id"]: x["partition"] for x in report["sessions"]}
    for i in range(0, 6, 2):
        assert mapped[f"session-{i}"] == mapped[f"session-{i + 1}"]
    assert report["split_sha256"] == mod.build_cohort(tmp_path, manifest)["split_sha256"]
    assert report["inference_status"] == "data-admission-only"
    assert all(x["n_arrivals"] == 1 for x in report["sessions"])


def test_checksum_tamper_fail_closed(tmp_path):
    manifest, _ = cohort(tmp_path)
    with (tmp_path / "session-0.jsonl").open("a") as fh:
        fh.write(" ")
    with pytest.raises(ValueError, match="checksum mismatch"):
        mod.build_cohort(tmp_path, manifest)


def test_fewer_than_three_lineages_rejected(tmp_path):
    manifest, _ = cohort(tmp_path, same_lineage=True)
    with pytest.raises(ValueError, match="independent lineages"):
        mod.build_cohort(tmp_path, manifest)


@pytest.mark.parametrize("bad,match", [
    ([row(-1, "arrive", "x", {"duration_s": 4})], "nonnegative"),
    ([row(float("nan"), "arrive", "x", {"duration_s": 4})], "finite"),
    ([row(0, "arrive", "x", {"duration_s": 0})], "positive"),
    ([row(0, "arrive", "x", {"duration_s": 4}),
      row(0, "arrive", "x", {"duration_s": 4})], "duplicate arrive"),
    ([row(0, "block", "x")], "before task arrival"),
    ([row(1, "arrive", "x", {"duration_s": 4}),
      row(.5, "control", "x")], "nonmonotonic"),
    ([row(0, "arrive", "x", {"duration_s": 4, "immediate": "true"})], "boolean"),
    ([row(0, "arrive", "x", {"duration_s": 4, "priority": "P8"})], "priority"),
    ([row(0, "arrive", "x", {"duration_s": 4}),
      row(1, "cancel", "x"), row(2, "control", "x")], "after cancellation"),
    ([row(0, "arrive", "x", {"duration_s": 4}),
      row(1, "revise", "x", {"duration_delta_s": float("inf")})], "nonfinite"),
    ([row(21600, "arrive", "x", {"duration_s": 4})], "outside replay horizon"),
])
def test_malformed_traces_rejected(bad, match):
    with pytest.raises(ValueError, match=match):
        mod.validate_trace(bytes_of(bad))


def test_valid_complex_trace():
    out = mod.validate_trace(bytes_of(trace_rows()))
    assert out["n_events"] == 4 and out["n_arrivals"] == 2
    assert out["n_cancelled_tasks"] == 1
    assert out["n_deadline_events"] == 2


def test_escape_and_symlink_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(bytes_of(trace_rows()))
    with pytest.raises(ValueError, match="escapes dataset root"):
        mod._inside_root(root, "../outside.jsonl")
    (root / "linked.jsonl").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes dataset root"):
        mod._inside_root(root, "linked.jsonl")


def test_false_deadline_provenance_rejected(tmp_path):
    manifest, entries = cohort(tmp_path)
    entries[0]["deadline_basis"] = "none"
    manifest.write_text("\n".join(map(json.dumps, entries)))
    with pytest.raises(ValueError, match="declared no deadlines"):
        mod.build_cohort(tmp_path, manifest)


def test_duplicate_source_content_rejected(tmp_path):
    manifest, entries = cohort(tmp_path)
    src = tmp_path / entries[0]["trace_file"]
    dst = tmp_path / entries[1]["trace_file"]
    dst.write_bytes(src.read_bytes())
    entries[1]["sha256"] = entries[0]["sha256"]
    manifest.write_text("\n".join(map(json.dumps, entries)))
    with pytest.raises(ValueError, match="duplicate trace content"):
        mod.build_cohort(tmp_path, manifest)


def test_negative_zero_and_non_numeric_duration_rejected():
    for invalid in (False, None, "4", float("inf")):
        with pytest.raises(ValueError, match="duration_s"):
            mod.validate_trace(bytes_of([row(0, "arrive", "x", {"duration_s": invalid})]))


def test_public_trace_loader_cannot_bypass_integrity_guard(tmp_path):
    from affectcontrol import load_jsonl_trace
    data = tmp_path / "trace.jsonl"
    data.write_bytes(bytes_of([row(0, "arrive", "x", {"duration_s": 0})]))
    with pytest.raises(ValueError, match="positive"):
        load_jsonl_trace(data)
    data.write_bytes(bytes_of(trace_rows()))
    trace = load_jsonl_trace(data)
    assert len(trace.events) == 4
