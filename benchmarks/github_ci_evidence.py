"""Independently executed GitHub Actions *test checks* as read-only evidence.

Fetch via authenticated GitHub CLI; validate source run/commit/job matrix.
These externally executed automated checks are not independent real-task
acceptance, nor a real scheduling-policy study. No raw logs or secrets saved.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from benchmarks.capture_execution import _write_exclusive

REPOSITORY = "chanokfortyzz/AffectControl"
BRANCH = "research/bitemporal-label-audit-20261108"
SHA = re.compile(r"^[0-9a-f]{40}$")
JOB = re.compile(r"^test \((macos-latest|ubuntu-latest|windows-latest), (3\.10|3\.12)\)$")
PLATFORMS = ("macos-latest", "ubuntu-latest", "windows-latest")
PYTHONS = ("3.10", "3.12")
MATRIX = {(o, p) for o in PLATFORMS for p in PYTHONS}
VALID_CONCLUSIONS = {"success", "failure", "cancelled", "timed_out", "action_required",
                     "neutral", "skipped", "stale", "startup_failure"}


def _time(s):
    if not isinstance(s, str):
        raise ValueError("missing GitHub timestamp")
    try:
        v = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid GitHub timestamp") from exc
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("GitHub timestamp has no timezone")
    return v.astimezone(timezone.utc)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(run, jobs, *, expected_sha):
    """Fail closed on wrong revision, missing jobs, or dubious run metadata."""
    if not isinstance(run, dict) or not isinstance(jobs, dict):
        raise ValueError("GitHub API outputs must be objects")
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise ValueError("expected_sha must be full 40-character Git commit SHA")
    if run.get("head_sha") != expected_sha:
        raise ValueError("run commit SHA does not match requested revision")
    if run.get("head_branch") != BRANCH:
        raise ValueError("wrong branch")
    if run.get("event") not in ("push", "pull_request"):
        raise ValueError("unexpected event")
    if type(run.get("id")) is not int or run["id"] <= 0:
        raise ValueError("invalid Actions run id")
    if type(run.get("run_attempt")) is not int or run["run_attempt"] < 1:
        raise ValueError("invalid run attempt")
    status = run.get("status")
    if status not in ("queued", "in_progress", "completed", "waiting", "requested", "pending"):
        raise ValueError("unknown run status")
    conclusion = run.get("conclusion")
    if status == "completed" and conclusion not in VALID_CONCLUSIONS:
        raise ValueError("completed run missing valid conclusion")
    if status != "completed" and conclusion is not None:
        raise ValueError("unfinished run already has a conclusion")
    expected_url = f"https://github.com/{REPOSITORY}/actions/runs/{run['id']}"
    if run.get("html_url") != expected_url:
        raise ValueError("unexpected GitHub Actions run URL")
    _time(run.get("created_at"))
    _time(run.get("updated_at"))
    repo = run.get("repository")
    if not isinstance(repo, dict) or repo.get("full_name") != REPOSITORY:
        raise ValueError("missing or wrong repository")
    rows = jobs.get("jobs")
    if not isinstance(rows, list) or type(jobs.get("total_count")) is not int:
        raise ValueError("GitHub job result is not a complete list")
    if len(rows) != jobs["total_count"]:
        raise ValueError("paginated or incomplete CI jobs response")
    if len(rows) != len(MATRIX):
        raise ValueError("required six-platform CI job matrix is incomplete")
    expected_names = set()
    sanitized = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("job row is not an object")
        m = JOB.fullmatch(str(row.get("name", "")))
        if not m:
            raise ValueError("unexpected CI job name")
        platform, py = m.groups()
        key = (platform, py)
        if key in expected_names:
            raise ValueError("duplicate platform/Python CI job")
        expected_names.add(key)
        if row.get("head_sha") != expected_sha:
            raise ValueError("CI job SHA mismatch")
        if type(row.get("id")) is not int or row["id"] <= 0:
            raise ValueError("invalid CI job id")
        if row.get("html_url") != expected_url + f"/job/{row['id']}":
            raise ValueError("CI job URL mismatch")
        jstatus = row.get("status")
        if jstatus not in ("queued", "in_progress", "completed", "waiting", "pending"):
            raise ValueError("invalid CI job status")
        jconclusion = row.get("conclusion")
        if jstatus == "completed" and jconclusion not in VALID_CONCLUSIONS:
            raise ValueError("completed job missing conclusion")
        if jstatus != "completed" and jconclusion is not None:
            raise ValueError("unfinished job has conclusion")
        started, ended = row.get("started_at"), row.get("completed_at")
        if started is not None:
            _time(started)
        if ended is not None:
            _time(ended)
        if started is not None and ended is not None and _time(ended) < _time(started):
            raise ValueError("job completed before start")
        sanitized.append({
            "job_id": row["id"], "platform": platform, "python": py,
            "status": jstatus, "conclusion": jconclusion,
            "job_url": row["html_url"],
        })
    if expected_names != MATRIX:
        raise ValueError("missing expected CI platform/Python pair")
    all_complete = status == "completed" and all(x["status"] == "completed" for x in sanitized)
    success = all_complete and conclusion == "success" and all(x["conclusion"] == "success" for x in sanitized)
    failed = status == "completed" and not success
    # Never force inconclusive runs into pass/fail status.
    outcome = "pass" if success else "failed_or_nonpassing" if failed else "pending"
    return {
        "protocol": "external-automated-ci-outcome-v1",
        "revision_sha": expected_sha,
        "run_id": run["id"],
        "run_attempt": run["run_attempt"],
        "event_type": run["event"],
        "run_url": expected_url,
        "n_expected_ci_jobs": len(MATRIX),
        "n_completed_jobs": sum(x["status"] == "completed" for x in sanitized),
        "n_successful_jobs": sum(x["status"] == "completed" and x["conclusion"] == "success" for x in sanitized),
        "n_failed_jobs": sum(x["status"] == "completed" and x["conclusion"] != "success" for x in sanitized),
        "automated_ci_outcome": outcome,
        "jobs": sorted(sanitized, key=lambda x: (x["platform"], x["python"])),
        "third_party_execution": "GitHub Actions (API reported)",
        "independent_human_task_acceptance": None,
        "natural_user_deadlines": None,
        "causal_agent_scheduler_effect": None,
        "evidence_level": "E1-external-automated-test-only",
        "warning": (
            "Executed GitHub Actions checks are independent CI infrastructure, "
            "not human adjudication of a real Agent task or experiment. "
            "The API response is not a cryptographic attestation; historical "
            "snapshots must remain traceable to GitHub. No deadlines are inferred."
        ),
    }


def _api(path):
    # Restrict REST endpoints, no URLs, no arbitrary shell command strings.
    res = subprocess.run(
        ["gh", "api", path, "--method", "GET"], check=True,
        text=True, capture_output=True, timeout=45,
    )
    return json.loads(res.stdout)


def fetch_and_audit(run_id: int, expected_sha: str):
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("invalid run ID")
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise ValueError("expected_sha must be full 40-character Git commit SHA")
    base = f"repos/{REPOSITORY}/actions/runs/{run_id}"
    run = _api(base)
    # Explicit per_page=100 makes the full six-job matrix visible
    jobs = _api(f"{base}/jobs?per_page=100")
    result = audit(run, jobs, expected_sha=expected_sha)
    result["capture_method"] = "authenticated-gh-api-live-read"
    # Raw API snapshots are not retained, only SHA256 digests. This
    # prevents raw account metadata from entering public outputs.
    result["run_api_response_sha256"] = _sha(json.dumps(run, sort_keys=True).encode())
    result["jobs_api_response_sha256"] = _sha(json.dumps(jobs, sort_keys=True).encode())
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--out", required=True, help="create-only JSON evidence path")
    args = p.parse_args()
    report = fetch_and_audit(args.run_id, args.expected_sha)
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    dest = Path(args.out)
    if dest.exists():
        raise FileExistsError("refuse to rewrite external CI evidence")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(dest, raw)
    print(json.dumps({
        "run_id": report["run_id"],
        "revision_sha": report["revision_sha"],
        "automated_ci_outcome": report["automated_ci_outcome"],
        "n_completed_jobs": report["n_completed_jobs"],
        "n_successful_jobs": report["n_successful_jobs"],
        "n_failed_jobs": report["n_failed_jobs"],
        "independent_human_task_acceptance": None,
    }, indent=2))


if __name__ == "__main__":
    main()
