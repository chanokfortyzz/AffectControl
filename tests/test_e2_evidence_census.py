"""Synthetic-schema fixtures only; never invent E2 outcomes for real logs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.e2_evidence_census import census, watch_census, shadow_census, paired_census

def write(path, rows):
    path.write_text("\n".join(json.dumps(x, sort_keys=True) for x in rows)+"\n")
    return path

def watch(ident="a", accepted=False):
    return {
        "captured_utc": "2026-11-08T01:00:00Z",
        "event_id": ident, "event_type": "task_terminal_reported",
        "kind": "first_seen", "observed_fingerprint": "a"*64,
        "schema": "agent-eval/s1-watch-v1", "source_table": "tasks",
        "task_trace_id": "same-apparent-id", "timestamp": "2026-11-08T00:59:00Z",
        "transport_or_task_status": "completed", "verified_acceptance": accepted,
    }

def shadow(accepted=None, evidence=None):
    return {
        "acceptance_verified": accepted, "agent": None, "event_id": "shadow-1",
        "event_type": "task_completed", "parent_event_id": None,
        "reported_status": "completed", "schema": "agent-eval/s1-shadow-v1",
        "source": "test", "source_record_id": None, "source_table": "tasks",
        "task_linked": True, "test_evidence": evidence,
        "timestamp": "2026-11-08T00:59:00Z", "token_usage": None,
        "tool_arguments": None, "tool_name": None,
        "trace_id": "same-apparent-id",
    }

def paired():
    return {
        "task_id": "same-apparent-id", "arm": "B2",
        "model": "model", "seed": 1, "passed": True,
        "workflow_complete": True, "verified_by": "independent_tests",
        "wall_seconds": 3.0,
    }

def fixtures(tmp_path, *, verified=False):
    return (
        write(tmp_path/"watch.jsonl", [watch(accepted=verified)]),
        write(tmp_path/"shadow.jsonl", [shadow(True if verified else None, "self-reported" if verified else None)]),
        [write(tmp_path/"pair.jsonl", [paired()])],
    )

def test_even_optimistic_self_report_does_not_create_eligible_episode(tmp_path):
    a, b, c = fixtures(tmp_path, verified=True)
    report = census(a, b, c)
    assert report["sources"]["s1_watch"]["n_flagged_verified_acceptance"] == 1
    assert report["sources"]["s1_shadow"]["n_records_with_test_evidence"] == 1
    assert report["sources"]["agent_eval"]["n_self_reported_independent_tests"] == 1
    assert report["e2_ready_episodes_demonstrated"] == 0
    assert report["sources"]["s1_watch"]["n_independently_adjudicated_task_outcomes"] is None
    assert report["source_event_counts_are_not_independent_episodes"] is True
    assert report["evidence_level"] == "E1"
    assert "same-apparent-id" not in json.dumps(report)

def test_missing_optional_status_not_failure(tmp_path):
    a, b, c = fixtures(tmp_path)
    report = census(a, b, c)
    assert report["sources"]["s1_shadow"]["n_records_with_nonnull_acceptance"] == 0
    assert report["sources"]["s1_shadow"]["n_independently_adjudicated_task_outcomes"] is None

@pytest.mark.parametrize("source,key,value,phrase", [
    ("watch","verified_acceptance","yes","acceptance"),
    ("watch","task_trace_id",None,"ID"),
    ("shadow","task_linked","true","task link"),
    ("shadow","trace_id",None,"ID"),
    ("paired","workflow_complete","yes","status"),
    ("paired","task_id",None,"ID"),
])
def test_untrustworthy_metadata_rejected(tmp_path, source, key, value, phrase):
    a,b,c=fixtures(tmp_path)
    target={"watch":a, "shadow":b, "paired":c[0]}[source]
    row=json.loads(target.read_text().splitlines()[0])
    row[key]=value
    write(target,[row])
    with pytest.raises(ValueError,match=phrase):
        census(a,b,c)

def test_raw_private_field_never_enter_aggregate(tmp_path):
    a,b,c=fixtures(tmp_path)
    row=json.loads(b.read_text().splitlines()[0])
    row["raw_user_prompt"]="secret"
    write(b,[row])
    with pytest.raises(ValueError,match="unexpected fields"):
        census(a,b,c)

def test_repeated_source_event_id_does_not_fabricate_independence(tmp_path):
    a,b,c=fixtures(tmp_path)
    write(a,[watch(),watch()])
    with pytest.raises(ValueError,match="revisions"):
        census(a,b,c)

def test_duplicate_task_run_rejected(tmp_path):
    a,b,c=fixtures(tmp_path)
    write(c[0],[paired(),paired()])
    with pytest.raises(ValueError,match="duplicate"):
        census(a,b,c)

def test_no_raw_content_in_aggregate(tmp_path):
    a,b,c=fixtures(tmp_path)
    r=census(a,b,c)
    assert all(len(x)==64 for x in (
        r["sources"]["s1_watch"]["source_sha256"],
        r["sources"]["s1_shadow"]["source_sha256"],
        r["sources"]["agent_eval"]["source_sha256"][0],
    ))
    dump=json.dumps(r)
    assert "raw_user_prompt" not in dump
    assert "same-apparent-id" not in dump

def test_invalid_json_refused(tmp_path):
    a,b,c=fixtures(tmp_path)
    a.write_text("not JSON")
    with pytest.raises(ValueError,match="invalid JSON"):
        census(a,b,c)
