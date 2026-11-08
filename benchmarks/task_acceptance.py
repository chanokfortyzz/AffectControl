"""Frozen named-task CI checks with SHA256/JUnit receipt.

This is repository *machine verification*, not independent human acceptance,
real user deadlines, or evidence of Agent scheduling treatment effects.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from benchmarks.capture_execution import _write_exclusive

SPEC = Path(__file__).with_name("task_acceptance_spec.json")
SCHEMA = "affectcontrol-named-task-machine-check-v2"
CASES = frozenset({"override-contract", "swf-byte-integrity"})


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_contract():
    raw = SPEC.read_bytes()
    spec = json.loads(raw)
    if set(spec) != {"schema", "evidence_scope", "deadline_basis", "independent_human_acceptance", "cases"}:
        raise ValueError("invalid contract schema")
    if spec["schema"] != "affectcontrol-task-acceptance-contract-v1" or spec["deadline_basis"] != "none" or spec["independent_human_acceptance"] is not None:
        raise ValueError("unsupported acceptance claim")
    if set(spec["cases"]) != CASES:
        raise ValueError("unapproved contract cases")
    for case, item in spec["cases"].items():
        if set(item) != {"purpose", "nodeids"} or not item["purpose"]:
            raise ValueError("invalid case")
        nodes = item["nodeids"]
        if not isinstance(nodes, list) or not nodes or len(nodes) > 10 or len(set(nodes)) != len(nodes):
            raise ValueError("invalid test list")
        prefix = "tests/test_explicit_override_priority.py::" if case == "override-contract" else "tests/test_pwa_arrival_audit.py::"
        if any(not isinstance(n, str) or not n.startswith(prefix) or not re.fullmatch(r"tests/test_[a-z_]+\.py::test_[a-z_]+", n) for n in nodes):
            raise ValueError("unapproved test selector")
    # The contract is a JSON object, not a byte-for-byte line-ending artifact.
    # Git may check out CRLF on Windows. Hash canonical semantic content so
    # the same frozen contract produces an identical digest on all platforms.
    canonical = json.dumps(spec, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
    return spec, digest(canonical)


def junit_summary(raw: bytes, selectors: list[str]) -> dict:
    root = ET.fromstring(raw)
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    rows = [case for suite in suites for case in suite.findall("testcase")]
    expected = {(Path(n.split("::")[0]).stem, n.split("::")[1]) for n in selectors}
    actual = {(r.get("classname", "").split(".")[-1], r.get("name")) for r in rows}
    if len(rows) != len(expected) or actual != expected:
        raise ValueError("JUnit report does not match frozen named tests")
    fails = sum(r.find("failure") is not None for r in rows)
    errors = sum(r.find("error") is not None for r in rows)
    skipped = sum(r.find("skipped") is not None for r in rows)
    return {"n_tests": len(rows), "n_passed": len(rows) - fails - errors - skipped,
            "n_failed": fails, "n_errors": errors, "n_skipped": skipped}


def run_case(case: str, output_dir: str, repo="."):
    spec, spec_sha = load_contract()
    if case not in CASES:
        raise ValueError("unknown acceptance case")
    repo = Path(repo).resolve()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True, timeout=10).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("unverifiable commit")
    nodes = spec["cases"][case]["nodeids"]
    if any(not (repo / n.split("::")[0]).is_file() for n in nodes):
        raise ValueError("required test missing")
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=False)
    junit = folder / "results.xml"
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *nodes, f"--junitxml={junit.resolve()}"],
            cwd=repo, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL,
            shell=False, timeout=120, check=False,
        )
        stdout.seek(0)
        stderr.seek(0)
        stdout_hash, stderr_hash = digest(stdout.read()), digest(stderr.read())
    raw = junit.read_bytes() if junit.exists() else b""
    try:
        results = junit_summary(raw, nodes) if raw else None
    except (ValueError, ET.ParseError):
        results = None
    success = (proc.returncode == 0 and results is not None and
               results["n_passed"] == len(nodes))
    receipt = {
        "schema": SCHEMA, "contract_sha256": spec_sha,
        "task_case": case, "research_commit_sha": commit,
        "test_selectors": nodes,
        "exit_code": proc.returncode,
        "junit_sha256": digest(raw) if raw else None,
        "junit_results": results,
        "stdout_sha256": stdout_hash, "stderr_sha256": stderr_hash,
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "automated_task_test_outcome": "pass" if success else "fail_or_incomplete",
        "independent_human_task_acceptance": None,
        "natural_user_deadline": None, "causal_scheduler_effect": None,
        "evidence_level": "E1-named-automated-check-only",
    }
    _write_exclusive(folder / "receipt.json",
                     (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    return receipt


def verify(receipt_file: str, junit_file: str, expected_sha: str):
    spec, spec_sha = load_contract()
    if not re.fullmatch(r"[a-f0-9]{40}", expected_sha):
        raise ValueError("expected commit SHA invalid")
    receipt = json.loads(Path(receipt_file).read_bytes())
    if receipt.get("schema") != SCHEMA or receipt.get("research_commit_sha") != expected_sha:
        raise ValueError("wrong receipt schema or source commit")
    if receipt.get("contract_sha256") != spec_sha:
        raise ValueError("contract hash mismatch")
    case = receipt.get("task_case")
    if case not in CASES or receipt.get("test_selectors") != spec["cases"][case]["nodeids"]:
        raise ValueError("task acceptance criterion mismatch")
    raw = Path(junit_file).read_bytes()
    if receipt.get("junit_sha256") != digest(raw):
        raise ValueError("JUnit evidence modified")
    results = junit_summary(raw, spec["cases"][case]["nodeids"])
    if receipt.get("junit_results") != results:
        raise ValueError("result summary modified")
    success = (type(receipt.get("exit_code")) is int and receipt["exit_code"] == 0
               and results["n_passed"] == len(spec["cases"][case]["nodeids"]))
    if receipt.get("automated_task_test_outcome") != ("pass" if success else "fail_or_incomplete"):
        raise ValueError("claimed outcome inconsistent with JUnit")
    if any(receipt.get(k) is not None for k in ("independent_human_task_acceptance", "natural_user_deadline", "causal_scheduler_effect")):
        raise ValueError("unsupported evidence claim")
    return {"task_case": case, "commit": expected_sha, "n_passed": results["n_passed"],
            "n_expected": results["n_tests"], "automated_task_test_outcome": receipt["automated_task_test_outcome"],
            "independent_human_task_acceptance": None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run")
    run.add_argument("--case", required=True, choices=sorted(CASES))
    run.add_argument("--out", required=True)
    check = sub.add_parser("verify")
    check.add_argument("--receipt", required=True)
    check.add_argument("--junit", required=True)
    check.add_argument("--expected-sha", required=True)
    a = p.parse_args()
    if a.action == "run":
        result = run_case(a.case, a.out)
        print(json.dumps({"case": a.case, "outcome": result["automated_task_test_outcome"],
                          "commit": result["research_commit_sha"]}))
        if result["automated_task_test_outcome"] != "pass":
            raise SystemExit(1)
    else:
        print(json.dumps(verify(a.receipt, a.junit, a.expected_sha), indent=2))


if __name__ == "__main__":
    main()
