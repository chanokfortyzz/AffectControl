"""Independent of pilot predictions; only validates a declared output requirement."""
import hashlib
import json
from pathlib import Path

import pytest

from affectcontrol.acceptance_probe import audit, main


def _fixture(tmp_path, result_text, *, marker="三条中文要点", correct_hash=True):
    root = tmp_path / "vault"
    root.mkdir()
    rid = "TASK-TEST-LOCAL"
    result = root / "out.md"
    result.write_text(result_text, encoding="utf-8")
    hash_text = hashlib.sha256(result.read_bytes()).hexdigest()
    (root / "state.json").write_text(json.dumps({"tasks": {
        rid: {"result_path": str(result),
              "result_content_sha256": hash_text if correct_hash else "0" * 64,
              "result_hash_scope": "utf8-file-bytes-v1"}
    }}), encoding="utf-8")
    (root / "queue-archive.md").write_text(
        f"### [{rid}] 干净的任务\n- **描述**:整理成三条中文要点\n"
        "- **验收标准**:必须包含三条中文要点；轨迹必须有 packaged, claimed, finished\n"
        "### [TASK-OTHER] 另一任务\n- **描述**:不要关联\n",
        encoding="utf-8")
    (root / "trace.jsonl").write_text("".join(json.dumps({
        "task_id": rid, "event": ev}) + "\n" for ev in (
            "task-packaged", "task-claimed", "local-worker-finished"
        )), encoding="utf-8")
    contract = {
        "task_id": rid,
        "archive_request_marker": marker,
        "expected_chinese_bullets": 3,
        "required_trace_events": [
            "task-packaged", "task-claimed", "local-worker-finished"
        ],
        "protocol": "exploratory_posthoc_narrow_v1",
    }
    (root / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    return root


def _audit(root):
    return audit(root / "contract.json", root / "state.json",
                 root / "queue-archive.md", root / "trace.jsonl", root)


def test_tool_call_only_is_actual_narrow_acceptance_failure(tmp_path):
    root = _fixture(tmp_path, """# result
<tool_call>
<function>read_file</function>
<parameter=arguments>{"path": "state"}</parameter>
""")
    out = _audit(root)
    assert out["result_hash_claim_matches_bytes"] is True
    assert out["required_trace_events_observed"] is True
    assert out["recorded_trace_event_counts"]["local-worker-finished"] == 1
    assert out["artifact_narrow_verdict"] == "NARROW_ACCEPTANCE_FAIL"
    assert out["observed_chinese_bullet_count"] == 0
    assert out["tool_call_without_final_bullets"] is True
    assert out["independent_blinded_gold_labels"] == 0


def test_well_formed_three_chinese_bullets_pass_narrowly(tmp_path):
    root = _fixture(tmp_path, "1. 中文甲\n2. 中文乙\n3. 中文丙\n")
    out = _audit(root)
    assert out["artifact_narrow_verdict"] == "NARROW_ACCEPTANCE_PASS"
    assert out["observed_chinese_bullet_count"] == 3
    assert out["independent_blinded_gold_labels"] == 0


def test_hash_mismatch_is_not_scored(tmp_path):
    root = _fixture(tmp_path, "- 中文甲\n- 中文乙\n- 中文丙\n", correct_hash=False)
    out = _audit(root)
    assert out["artifact_narrow_verdict"] == "NOT_EVALUATED_INTEGRITY_MISMATCH"


def test_marker_must_anchor_original_task_packet(tmp_path):
    root = _fixture(tmp_path, "- 中文甲\n- 中文乙\n- 中文丙\n",
                    marker="此任务从未提出这项要求")
    with pytest.raises(ValueError, match="marker"):
        _audit(root)


def test_symlink_result_outside_root_rejected(tmp_path):
    root = _fixture(tmp_path, "- 中文甲\n- 中文乙\n- 中文丙\n")
    original = root / "out.md"
    original.unlink()
    outside = tmp_path / "external.txt"
    outside.write_text("outside")
    original.symlink_to(outside)
    with pytest.raises(ValueError, match="outside permitted root"):
        _audit(root)


def test_unknown_task_fail_closed(tmp_path):
    root = _fixture(tmp_path, "- 中文甲\n- 中文乙\n- 中文丙\n")
    p = root / "contract.json"
    d = json.loads(p.read_text())
    d["task_id"] = "OTHER-UNKNOWN"
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="task not in snapshot"):
        _audit(root)


def test_cli_outputs_only_redacted_provenance(tmp_path, capsys):
    root = _fixture(tmp_path, "- 中文甲\n- 中文乙\n- 中文丙\n")
    assert main(["--contract", str(root / "contract.json"),
                 "--snapshot", str(root / "state.json"),
                 "--archive", str(root / "queue-archive.md"),
                 "--trace", str(root / "trace.jsonl"),
                 "--artifact-root", str(root)]) == 0
    text = capsys.readouterr().out
    assert "TASK-TEST-LOCAL" not in text
    assert str(root) not in text
    assert json.loads(text)["production_decision"] == "NOT_APPROVED"
