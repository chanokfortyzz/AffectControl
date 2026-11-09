"""Executor-separated coding task oracle: isolated, read-only re-execution.

Six archived coding-agent worktrees are copied as two allowlisted Python
modules into private temporary directories. Run previously frozen hidden
unittest suites outside the original worktrees. Compare with archived local
evaluator outputs and their sha256 hashes. This is *not* natural Agent task
acceptance, external human adjudication, or an AffectControl treatment test.

Only run against explicitly authorized own-machine source trees: hidden test
scripts are arbitrary Python, albeit pinned here to files inspected in advance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

from benchmarks.capture_execution import _write_exclusive

PROTOCOL = "agent-eval-hidden-oracle-actual-rerun-v1"
TASK_SPECS = (
    ("experiment-p1", "DEDUP-001", "test_hidden.py",
     "8d879c3a8b431cca5c1796c623de41f5587af908bea43b03057008d2348da516", 2),
    ("experiment-p1", "UNKNOWN-002", "test_hidden.py",
     "8d879c3a8b431cca5c1796c623de41f5587af908bea43b03057008d2348da516", 2),
    ("experiment-p2", "PIPELINE-003", "test_pipeline.py",
     "645d9718658b6df72088de99050d3b631a421d89dba4367d1220a0bd8ed79af9", 3),
)
ARMS = ("B2", "B3")
MODULES = ("backend.py", "easylap.py")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
RUN_COUNT = re.compile(rb"Ran (\d+) tests? in")
SUCCESS = re.compile(rb"(?m)^OK\s*$")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_unittest(stderr: bytes, exit_code: int, *, expected_count: int) -> dict:
    match = RUN_COUNT.search(stderr)
    count = int(match.group(1)) if match else None
    ok = bool(SUCCESS.search(stderr)) and exit_code == 0 and count == expected_count
    return {
        "exit_code": exit_code,
        "n_executed_tests": count,
        "n_expected_tests": expected_count,
        "oracle_pass": ok,
    }


def _git_head(tree: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tree,
        capture_output=True, text=True, timeout=10, check=True,
    )
    actual = result.stdout.strip()
    if not SHA40.fullmatch(actual):
        raise ValueError("invalid source fixture commit SHA")
    return actual


def _read_archived(archive: Path, expected_hidden: int) -> tuple[dict, dict]:
    stored = json.loads(archive.read_bytes())
    if not isinstance(stored, dict) or not isinstance(stored.get("public"), dict) or not isinstance(stored.get("hidden"), dict):
        raise ValueError("invalid archived evaluator acceptance structure")
    comparison = {}
    for field in ("public", "hidden"):
        expected_hash = stored[field].get("log_sha256")
        if not isinstance(expected_hash, str) or not SHA64.fullmatch(expected_hash):
            raise ValueError("archived test log hash not valid")
        file = archive.parent / f"{field}.log"
        if not file.is_file() or file.is_symlink() or sha(file.read_bytes()) != expected_hash:
            raise ValueError("archived log diverges from pinned acceptance")
        comparison[field + "_log_sha256_verified"] = True
    if stored["hidden"].get("tests_run") != expected_hidden:
        raise ValueError("hidden test count differs from archived result")
    if type(stored.get("passed")) is not bool or type(stored.get("workflow_complete")) is not bool:
        raise ValueError("invalid archived outcome flags")
    if type(stored["hidden"].get("passed")) is not bool:
        raise ValueError("invalid archived hidden outcome")
    return stored, comparison


def _run_one(root: Path, exp: str, task_id: str, test_file: str, test_sha: str,
             expected_tests: int, arm: str, python: Path) -> dict:
    suite = root / exp / "hidden" / test_file
    if suite.is_symlink() or not suite.is_file() or sha(suite.read_bytes()) != test_sha:
        raise ValueError("hidden evaluator suite does not match frozen sha256")
    fixture = root / exp / task_id
    source = json.loads((fixture / "task.json").read_bytes())
    if source.get("task_id") != task_id:
        raise ValueError("task identifier does not match source task file")
    expected_commit = source.get("fixture_commit")
    if not isinstance(expected_commit, str) or not SHA40.fullmatch(expected_commit):
        raise ValueError("invalid starting fixture commit")
    tree = fixture / arm
    if not tree.is_dir() or tree.is_symlink() or _git_head(tree) != expected_commit:
        raise ValueError("agent worktree no longer matches source fixture commit")
    archived, integrity = _read_archived(
        fixture / "runs" / arm / "evaluator" / "acceptance.json", expected_tests
    )
    if archived.get("task_id") != task_id or archived.get("arm") != arm:
        raise ValueError("archived acceptance task/arm identity mismatch")
    files = {}
    with tempfile.TemporaryDirectory(prefix="affectcontrol-isolated-oracle-") as name:
        stage = Path(name)
        for module in MODULES:
            entry = tree / module
            if entry.is_symlink() or not entry.is_file():
                raise ValueError("source code module missing or symlinked")
            raw = entry.read_bytes()
            files[module] = sha(raw)
            (stage / module).write_bytes(raw)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": str(stage),
            "HOME": str(stage),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        result = subprocess.run(
            [str(python), "-B", "-m", "unittest", "discover",
             "-s", str(suite.parent.resolve()), "-v"],
            cwd=stage, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=60, check=False,
        )
        # Raw stdout/stderr are intentionally never retained or printed.
        observed = parse_unittest(
            result.stderr, result.returncode, expected_count=expected_tests
        )
        observed["stdout_sha256"] = sha(result.stdout)
        observed["stderr_sha256"] = sha(result.stderr)
    if observed["n_executed_tests"] != expected_tests:
        raise ValueError("hidden tests not executed completely")
    if observed["oracle_pass"] != archived["hidden"]["passed"]:
        raise ValueError("independent rerun disagrees with archived hidden-test outcome")
    if archived.get("passed") and not observed["oracle_pass"]:
        raise ValueError("archived overall success conflicts with actual hidden tests")
    return {
        "task_id": task_id,
        "arm": arm,
        "experiment": exp,
        "fixture_commit_sha": expected_commit,
        "task_definition_sha256": sha((fixture / "task.json").read_bytes()),
        "source_module_sha256": files,
        "hidden_test_suite_sha256": test_sha,
        "archived_logs_verified": integrity,
        "archived_overall_pass": archived["passed"],
        "archived_workflow_complete": archived["workflow_complete"],
        "archived_hidden_oracle_pass": archived["hidden"]["passed"],
        "rerun": observed,
        "natural_user_deadline": None,
        "treatment": "B2_or_B3_code_workflow_not_affectcontrol",
        "oracle": "evaluator-authored-hidden-unit-tests",
    }


def audit(root: Path, python: Path) -> dict:
    root = Path(root).resolve()
    python = Path(python).resolve()
    if not python.is_file():
        raise ValueError("provided Python interpreter does not exist")
    entries = [
        _run_one(root, experiment, task, suite, digest, count, arm, python)
        for experiment, task, suite, digest, count in TASK_SPECS
        for arm in ARMS
    ]
    n_pass = sum(x["rerun"]["oracle_pass"] for x in entries)
    return {
        "protocol": PROTOCOL,
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_count": len(TASK_SPECS),
        "run_count": len(entries),
        "n_executor_separated_code_oracle_pass": n_pass,
        "n_executor_separated_code_oracle_fail": len(entries) - n_pass,
        "archived_evaluator_integrity_all_pass": True,
        "rerun_agrees_with_archived_hidden_tests_all": True,
        "results": entries,
        "externally_signed_oracle": None,
        "independent_human_business_acceptance": None,
        "naturally_observed_task_deadlines": None,
        "affectcontrol_vs_urgency_comparison": None,
        "evidence_level": "E1-executor-separated-code-oracle-only",
        "warning": (
            "Evaluator-only hidden coding tests were independently executed "
            "from agent worktrees in fresh local sandboxes, not independently "
            "authored by an external party and not a natural user task oracle. "
            "Both B2 and B3 are coding workflow conditions, not AffectControl "
            "scheduling policies. No natural deadlines, production preemption "
            "or cross-project causal claim. No original code or private logs "
            "are emitted."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--agent-eval-root", required=True)
    p.add_argument("--python", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = audit(Path(args.agent_eval_root), Path(args.python))
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(destination, (json.dumps(result, sort_keys=True, indent=2) + "\n").encode())
    print(json.dumps({
        "task_count": result["task_count"],
        "run_count": result["run_count"],
        "oracle_pass": result["n_executor_separated_code_oracle_pass"],
        "oracle_fail": result["n_executor_separated_code_oracle_fail"],
        "archived_logs_all_verified": result["archived_evaluator_integrity_all_pass"],
        "interpretation": result["evidence_level"],
    }, indent=2))


if __name__ == "__main__":
    main()
