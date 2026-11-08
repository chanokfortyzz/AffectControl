"""Pure contract checks; actual historical reruns stay in ignored local evidence."""
from __future__ import annotations
import json
import pytest
from benchmarks.agent_eval_hidden_recheck import _read_archived, parse_unittest, sha, TASK_SPECS, ARMS

def archive(tmp_path, passed=True, hidden_count=2):
    folder = tmp_path/"evaluator"
    folder.mkdir()
    (folder/"hidden.log").write_bytes(b"hidden logs")
    (folder/"public.log").write_bytes(b"public logs")
    data = {
        "passed":passed,"workflow_complete":passed,
        "hidden":{"passed":passed,"tests_run":hidden_count,"log_sha256":sha(b"hidden logs")},
        "public":{"passed":True,"tests_run":27,"log_sha256":sha(b"public logs")}
    }
    path=folder/"acceptance.json"
    path.write_text(json.dumps(data))
    return path

def test_success_with_complete_count():
    assert parse_unittest(b"Ran 3 tests in 0.003s\n\nOK\n",0,expected_count=3)["oracle_pass"]

@pytest.mark.parametrize("data,exitcode", [
    (b"Ran 3 tests in 0.1s\nOK\n",1),
    (b"Ran 2 tests in 0.1s\nOK\n",0),
    (b"Ran 3 tests in 0.1s\nFAILED (failures=1)\n",1),
    (b"",0),
])
def test_false_or_incomplete_results_not_promoted(data,exitcode):
    assert not parse_unittest(data,exitcode,expected_count=3)["oracle_pass"]

def test_archived_sha_verification(tmp_path):
    row, proof=_read_archived(archive(tmp_path),2)
    assert all(proof.values()) and row["hidden"]["passed"] is True
    assert "hidden logs" not in str(proof)

def test_tampered_archived_hidden_log_rejected(tmp_path):
    path=archive(tmp_path)
    (path.parent/"hidden.log").write_bytes(b"tampered")
    with pytest.raises(ValueError,match="diverges"):
        _read_archived(path,2)

def test_expected_count_fails_on_archive_conflict(tmp_path):
    with pytest.raises(ValueError,match="count"):
        _read_archived(archive(tmp_path,hidden_count=3),2)

def test_invalid_archived_hidden_outcome_rejected(tmp_path):
    path=archive(tmp_path)
    row=json.loads(path.read_text())
    row["hidden"]["passed"]="yes"
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError,match="hidden outcome"):
        _read_archived(path,2)

def test_exact_number_of_source_tasks_and_arms():
    assert len(TASK_SPECS)==3 and ARMS==("B2","B3")
    assert all(len(x[3])==64 and x[4]>0 for x in TASK_SPECS)
