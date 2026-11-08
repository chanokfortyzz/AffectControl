"""Named-task machine checks: validate positive and negative artifact paths."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from benchmarks import task_acceptance as acceptance

PROJECT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case,count", [
    ("override-contract",3),
    ("swf-byte-integrity",2),
])
def test_named_acceptance_actually_executes_only_frozen_tests(tmp_path,case,count):
    out = tmp_path / case
    receipt = acceptance.run_case(case,str(out),repo=PROJECT)
    assert receipt["automated_task_test_outcome"] == "pass"
    assert receipt["junit_results"]["n_passed"] == count
    result = acceptance.verify(out/"receipt.json",out/"results.xml",receipt["research_commit_sha"])
    assert result["n_passed"] == count
    assert result["independent_human_task_acceptance"] is None
    assert receipt["natural_user_deadline"] is None
    with pytest.raises(FileExistsError):
        acceptance.run_case(case,str(out),repo=PROJECT)


def test_junit_tampering_is_detected(tmp_path):
    root=tmp_path/"evidence"
    receipt=acceptance.run_case("override-contract",str(root),repo=PROJECT)
    path=root/"results.xml"
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(ValueError,match="modified"):
        acceptance.verify(root/"receipt.json",path,receipt["research_commit_sha"])


def test_false_success_status_is_rejected(tmp_path):
    root=tmp_path/"evidence"
    receipt=acceptance.run_case("swf-byte-integrity",str(root),repo=PROJECT)
    path=root/"receipt.json"
    row=json.loads(path.read_text())
    row["exit_code"]=7
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError,match="inconsistent"):
        acceptance.verify(path,root/"results.xml",receipt["research_commit_sha"])


def test_unknown_case_refused_before_execution(tmp_path):
    with pytest.raises(ValueError,match="unknown acceptance case"):
        acceptance.run_case("any-other-case",str(tmp_path/"will-not-create"),repo=PROJECT)
    assert not (tmp_path/"will-not-create").exists()


def test_contract_cannot_promote_human_acceptance(monkeypatch,tmp_path):
    original=json.loads(acceptance.SPEC.read_text())
    original["independent_human_acceptance"]=True
    f=tmp_path/"altered.json"
    f.write_text(json.dumps(original))
    monkeypatch.setattr(acceptance,"SPEC",f)
    with pytest.raises(ValueError,match="unsupported acceptance claim"):
        acceptance.load_contract()


def test_contract_cannot_add_arbitrary_execution_target(monkeypatch,tmp_path):
    original=json.loads(acceptance.SPEC.read_text())
    original["cases"]["override-contract"]["nodeids"].append(
        "tests/test_core.py::test_explicit_immediate_is_hard_override")
    f=tmp_path/"altered.json"
    f.write_text(json.dumps(original))
    monkeypatch.setattr(acceptance,"SPEC",f)
    with pytest.raises(ValueError,match="unapproved test selector"):
        acceptance.load_contract()


def test_wrong_commit_and_unsupported_label_rejected(tmp_path):
    root=tmp_path/"evidence"
    receipt=acceptance.run_case("override-contract",str(root),repo=PROJECT)
    with pytest.raises(ValueError,match="source commit"):
        acceptance.verify(root/"receipt.json",root/"results.xml","b"*40)
    row=json.loads((root/"receipt.json").read_text())
    row["independent_human_task_acceptance"]=True
    (root/"receipt.json").write_text(json.dumps(row))
    with pytest.raises(ValueError,match="unsupported evidence"):
        acceptance.verify(root/"receipt.json",root/"results.xml",receipt["research_commit_sha"])



def test_contract_semantic_digest_matches_lf_and_crlf(monkeypatch,tmp_path):
    original=acceptance.SPEC.read_bytes()
    lf=original.replace(b"\r\n",b"\n")
    crlf=lf.replace(b"\n",b"\r\n")
    first=tmp_path/"lf.json"
    second=tmp_path/"crlf.json"
    first.write_bytes(lf)
    second.write_bytes(crlf)
    monkeypatch.setattr(acceptance,"SPEC",first)
    data_a,digest_a=acceptance.load_contract()
    monkeypatch.setattr(acceptance,"SPEC",second)
    data_b,digest_b=acceptance.load_contract()
    assert data_a==data_b
    assert digest_a==digest_b
    assert acceptance.digest(lf)!=acceptance.digest(crlf)


def test_old_noncanonical_receipt_schema_is_rejected(tmp_path):
    out=tmp_path/"evidence"
    receipt=acceptance.run_case("override-contract",str(out),repo=PROJECT)
    row=json.loads((out/"receipt.json").read_text())
    row["schema"]="affectcontrol-named-task-machine-check-v1"
    (out/"receipt.json").write_text(json.dumps(row))
    with pytest.raises(ValueError,match="schema"):
        acceptance.verify(out/"receipt.json",out/"results.xml",receipt["research_commit_sha"])
