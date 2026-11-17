import hashlib
import json
import pytest

from affectcontrol.coverage_audit import audit, main


def _fixture(tmp_path, rows):
    p = tmp_path / "sage-observation.jsonl"
    p.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows),
        encoding="utf-8",
    )
    return p


def _base(**extra):
    return {
        "source": "sage-observational-v1",
        "kind": "state_snapshot",
        "anon_task_id": "anon-1",
        "preemptible": True,
        "explicit_override": False,
        "priority": "P2",
        **extra,
    }


def test_existing_source_shape_is_insufficient_for_interrupt(tmp_path):
    p = _fixture(tmp_path, [
        _base(),
        _base(anon_task_id="anon-2"),
        {"kind": "task-finished", "task_id": "task-1", "preemptible": True},
    ])
    before = p.read_bytes()
    result = audit(p)
    assert p.read_bytes() == before
    assert result["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert result["rows"] == 3
    assert result["distinct_anonymized_snapshot_ids"] == 2
    assert result["distinct_event_task_ids"] == 1
    assert result["source_preemptible_rows_not_equivalent_to_running_task"] == 3
    assert result["structured_context"]["complete_rows"] == 0
    assert result["structured_context"]["abstain_rows"] == 3
    assert result["dispatch_allowed"] is False
    assert result["production_decision"] == "NOT_APPROVED"


def test_complete_context_requires_five_exact_fields(tmp_path):
    full = {
        "current_task_running": True,
        "current_task_preemptible": False,
        "task_blocked": False,
        "estimated_work_seconds": 10,
        "seconds_until_deadline": 5,
    }
    p = _fixture(tmp_path, [
        _base(context=full),
        _base(anon_task_id="anon-2", context={"current_task_running": True}),
        _base(anon_task_id="anon-3", context=None),
    ])
    result = audit(p)
    assert result["structured_context"]["complete_rows"] == 1
    assert result["structured_context"]["partial_rows"] == 1
    assert result["structured_context"]["abstain_rows"] == 2
    assert result["structured_context"]["complete_coverage"] == 1/3


def test_reject_invalid_context_without_touching_input(tmp_path):
    p = _fixture(tmp_path, [_base(context={"current_task_running": "yes"})])
    before = p.read_bytes()
    with pytest.raises(ValueError, match="boolean"):
        audit(p)
    assert p.read_bytes() == before


def test_reject_non_jsonl_and_empty(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"valid":true}\nnot-json\n')
    with pytest.raises(ValueError, match="line 2"):
        audit(p)
    p.write_text("\n")
    with pytest.raises(ValueError, match="empty"):
        audit(p)


def test_claimed_gold_labels_not_treated_as_verified(tmp_path):
    p = _fixture(tmp_path, [{
        "kind": "task-finished",
        "label_origin": "independent_human",
        "split": "holdout",
        "should_interrupt": False,
    }])
    result = audit(p)
    assert result["label_shape_claimed_rows_not_independently_verified"] == 1
    assert result["production_decision"] == "NOT_APPROVED"


def test_cli_never_emits_task_id(tmp_path, capsys):
    p = _fixture(tmp_path, [_base(anon_task_id="private-id-do-not-leak")])
    assert main(["--input", str(p)]) == 0
    result = capsys.readouterr().out
    assert "private-id-do-not-leak" not in result
    assert json.loads(result)["rows"] == 1


def test_snapshot_hints_are_counts_only_not_inferred_permission(tmp_path):
    p = _fixture(tmp_path, [
        _base(process_alive=True, claimed=True, packet_status="working",
              urgency=0.9, appraisal_provider="reference"),
        _base(anon_task_id="anon-2", process_alive=False, claimed=False,
              packet_status="queued", urgency=None),
    ])
    r = audit(p)
    hints = r["snapshot_hint_coverage"]
    assert hints["snapshot_rows"] == 2
    assert hints["non_null_field_rows"]["process_alive"] == 2
    assert hints["non_null_field_rows"]["claimed"] == 2
    assert hints["non_null_field_rows"]["urgency"] == 1
    assert r["structured_context"]["complete_rows"] == 0
    assert r["structured_context"]["abstain_rows"] == 2
    assert "working" not in json.dumps(hints)
