"""Fixed GitHub Actions automated-check contract; no human acceptance claim."""
from __future__ import annotations

from copy import deepcopy

import pytest

from benchmarks.github_ci_evidence import audit, MATRIX, fetch_and_audit

EXPECTED = "a" * 40
RUN_ID = 42450509244


def fixture(*, finish=True):
    run = {
        "id": RUN_ID,
        "run_attempt": 1,
        "head_sha": EXPECTED,
        "head_branch": "research/bitemporal-label-audit-20261108",
        "event": "pull_request",
        "status": "completed" if finish else "in_progress",
        "conclusion": "success" if finish else None,
        "html_url": f"https://github.com/chanokfortyzz/AffectControl/actions/runs/{RUN_ID}",
        "created_at": "2026-11-08T05:22:13Z",
        "updated_at": "2026-11-08T05:24:13Z",
        "repository": {"full_name": "chanokfortyzz/AffectControl"},
    }
    rows = []
    for idx, (platform, python) in enumerate(sorted(MATRIX), 1):
        rows.append({
            "id": idx,
            "head_sha": EXPECTED,
            "name": f"test ({platform}, {python})",
            "status": "completed" if finish else "in_progress",
            "conclusion": "success" if finish else None,
            "html_url": f"{run['html_url']}/job/{idx}",
            "started_at": "2026-11-08T05:22:17Z",
            "completed_at": "2026-11-08T05:23:08Z" if finish else None,
        })
    return run, {"total_count": len(rows), "jobs": rows}


def test_complete_six_job_external_ci_pass_is_only_automated_check():
    r, jobs = fixture()
    result = audit(r, jobs, expected_sha=EXPECTED)
    assert result["n_expected_ci_jobs"] == 6
    assert result["n_completed_jobs"] == result["n_successful_jobs"] == 6
    assert result["automated_ci_outcome"] == "pass"
    assert result["independent_human_task_acceptance"] is None
    assert result["natural_user_deadlines"] is None
    assert result["causal_agent_scheduler_effect"] is None
    assert result["evidence_level"].startswith("E1")


def test_one_windows_failure_fails_entire_run_even_if_run_claims_success():
    r, jobs = fixture()
    jobs["jobs"][-1]["conclusion"] = "failure"
    result = audit(r, jobs, expected_sha=EXPECTED)
    assert result["n_successful_jobs"] == 5
    assert result["n_failed_jobs"] == 1
    assert result["automated_ci_outcome"] == "failed_or_nonpassing"


def test_pending_is_not_silently_treated_as_failure_or_success():
    r, jobs = fixture(finish=False)
    report = audit(r, jobs, expected_sha=EXPECTED)
    assert report["automated_ci_outcome"] == "pending"
    assert report["n_completed_jobs"] == 0


@pytest.mark.parametrize("change,phrase", [
    (lambda r,j: r.update(head_sha="b"*40), "SHA"),
    (lambda r,j: r.update(head_branch="main"), "branch"),
    (lambda r,j: r.update(repository={"full_name": "attacker/fork"}), "repository"),
    (lambda r,j: r.pop("repository"), "repository"),
    (lambda r,j: r.update(html_url="https://evil.example.com/job"), "URL"),
    (lambda r,j: r.update(run_attempt=0), "attempt"),
    (lambda r,j: r.update(event="workflow_dispatch"), "event"),
    (lambda r,j: r.update(status="completed", conclusion=None), "conclusion"),
    (lambda r,j: j["jobs"][0].update(head_sha="c"*40), "SHA"),
    (lambda r,j: j["jobs"][0].update(html_url="https://evil.example.com/log"), "URL"),
    (lambda r,j: j["jobs"][1].update(name=j["jobs"][0]["name"]), "duplicate"),
    (lambda r,j: j["jobs"].pop(), "incomplete"),
    (lambda r,j: j.update(total_count=30), "incomplete"),
    (lambda r,j: j["jobs"][0].update(conclusion="undetermined"), "conclusion"),
])
def test_malformed_ci_source_is_rejected(change, phrase):
    r, j = fixture()
    change(r, j)
    with pytest.raises(ValueError, match=phrase):
        audit(r, j, expected_sha=EXPECTED)


def test_fetched_api_outputs_are_pinned_but_not_attested(monkeypatch):
    r, j = fixture()
    requested = []
    def fake_api(path):
        requested.append(path)
        return deepcopy(r) if path.endswith(str(RUN_ID)) else deepcopy(j)
    monkeypatch.setattr("benchmarks.github_ci_evidence._api", fake_api)
    out = fetch_and_audit(RUN_ID, EXPECTED)
    assert out["capture_method"] == "authenticated-gh-api-live-read"
    assert len(out["run_api_response_sha256"]) == 64
    assert len(out["jobs_api_response_sha256"]) == 64
    assert requested == [
        f"repos/chanokfortyzz/AffectControl/actions/runs/{RUN_ID}",
        f"repos/chanokfortyzz/AffectControl/actions/runs/{RUN_ID}/jobs?per_page=100",
    ]
    assert out["independent_human_task_acceptance"] is None


def test_reject_invalid_identifiers_before_network(monkeypatch):
    def fail(_):
        raise AssertionError("must not attempt network")
    monkeypatch.setattr("benchmarks.github_ci_evidence._api", fail)
    with pytest.raises(ValueError, match="invalid run ID"):
        fetch_and_audit(-1, EXPECTED)
    with pytest.raises(ValueError, match="SHA"):
        fetch_and_audit(RUN_ID, "short")
