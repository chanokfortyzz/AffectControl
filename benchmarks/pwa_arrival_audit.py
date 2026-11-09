"""Public historical HPC workload arrival audit; not Agent-policy evaluation.

Input is pinned SWF 2.2 from a third-party GitHub mirror of PWA. SWF
submit timestamps and run times are observed historical job metadata.
Requested runtime is a walltime/resource limit, never a user deadline.
No scheduler outcomes, human interruption labels, or E2 claims.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

PINNED = {
    "KTH-SP2.swf": {
        "sha256": "fba36494c4e4257f72182e8b629ebb0bcb054b3b82851ef957445bd627adcc87",
        "institution": "KTH Royal Institute of Technology",
    },
    "CTC-SP2.swf": {
        "sha256": "d078f9517bafcf37602482abe99e0b2e1c1867e3ce7748df8acc50364847bccf",
        "institution": "Cornell Theory Center",
    },
}
REPO_COMMIT = "b9362a40bf5c0f86788a7b1411ec1c3dea9a92d9"
SOURCE = "https://github.com/ihfaz297/cpu-scheduling-fairness-survey"
HORIZONS = (1, 5, 10, 30, 60, 300)


def percentile(values, q):
    if not values:
        return None
    sorted_values = sorted(values)
    return sorted_values[int((len(sorted_values) - 1) * q)]


def parse_swf(path, *, expected_hash=None):
    path = Path(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_hash is not None and digest != expected_hash:
        raise ValueError("source SHA256 checksum does not match pinned contents")
    headers = {}
    header_comments = []
    submits = []
    runtimes = []
    positive_requests = 0
    statuses = Counter()
    invalid_times = 0
    rows = 0
    observed_ids = set()
    for lineno, raw_line in enumerate(raw.decode("utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(";"):
            header_comments.append(line)
            if ":" in line:
                key, value = line[1:].split(":", 1)
                headers[key.strip()] = value.strip()
            continue
        pieces = line.split()
        if len(pieces) != 18:
            raise ValueError(f"line {lineno}: expected 18 SWF columns")
        try:
            numbers = [float(s) for s in pieces]
        except ValueError as exc:
            raise ValueError(f"line {lineno}: nonnumeric SWF field") from exc
        if not all(math.isfinite(v) for v in numbers):
            raise ValueError(f"line {lineno}: nonfinite SWF field")
        # SWF column 6 (CPU time) legitimately contains decimal fractions;
        # only identifier/timestamps/runtime/status must be exact integers.
        if any(not numbers[i].is_integer() for i in (0, 1, 2, 3, 10)):
            raise ValueError(f"line {lineno}: fractional integral field")
        identifier, submit, wait, runtime = [int(x) for x in numbers[:4]]
        if identifier in observed_ids:
            raise ValueError(f"line {lineno}: duplicate job number")
        observed_ids.add(identifier)
        rows += 1
        statuses[numbers[10]] += 1
        if submit < 0 or runtime <= 0:
            invalid_times += 1
            continue
        submits.append(submit)
        runtimes.append(runtime)
        positive_requests += numbers[8] > 0
    if headers.get("Version") != "2.2":
        raise ValueError("expected documented SWF format version 2.2")
    if rows < 2 or len(submits) < 2:
        raise ValueError("insufficient observed valid jobs")
    submits.sort()
    return {
        "source_sha256": digest,
        "headers": headers,
        "is_cleaned_log": any("cleaned version" in s.lower() for s in header_comments),
        "n_swf_jobs": rows,
        "n_valid_arrival_and_runtime_jobs": len(submits),
        "n_missing_or_invalid_runtime_jobs": invalid_times,
        "n_positive_requested_runtime": positive_requests,
        "status_counts": dict(sorted(statuses.items())),
        "submit_times": submits,
        "runtime_seconds": runtimes,
    }


def summarize(records):
    submits = records["submit_times"]
    runtimes = records["runtime_seconds"]
    if submits[-1] == submits[0]:
        raise ValueError("zero observed time window")
    horizon_stats = {}
    # Inter-arrival gaps are observational; no reordering or synthetic new tasks.
    gaps = [b - a for a,b in zip(submits, submits[1:])]
    for horizon in HORIZONS:
        next_at_event = sum(gap <= horizon for gap in gaps) / len(gaps)
        # At an arbitrary time, the next arrival is <= horizon when
        # it falls within the final min(horizon,gap) of each gap.
        time_coverage = sum(min(horizon, gap) for gap in gaps) / (submits[-1] - submits[0])
        horizon_stats[str(horizon)] = {
            "next_arrival_within_horizon_at_job_submit_fraction": next_at_event,
            "next_arrival_within_horizon_at_uniform_time_fraction": time_coverage,
        }
    output = {
        "protocol": "pwa-historical-real-arrival-check-v1",
        "source_sha256": records["source_sha256"],
        "institution": records["headers"].get("Installation", "not_stated"),
        "is_cleaned_log": records["is_cleaned_log"],
        "n_raw_jobs": records["n_swf_jobs"],
        "n_valid_jobs": records["n_valid_arrival_and_runtime_jobs"],
        "n_excluded_for_invalid_time": records["n_missing_or_invalid_runtime_jobs"],
        "n_positive_requested_runtime": records["n_positive_requested_runtime"],
        "n_zero_interarrival_gaps": sum(gap == 0 for gap in gaps),
        "span_seconds": submits[-1] - submits[0],
        "recorded_runtime_seconds": {
            "median": percentile(runtimes, .5),
            "p90": percentile(runtimes, .9),
            "p95": percentile(runtimes, .95),
        },
        "observed_arrival_interval_seconds": {
            "median": percentile(gaps, .5),
            "p90": percentile(gaps, .9),
            "p95": percentile(gaps, .95),
        },
        "arrival_within_seconds": horizon_stats,
        "inference_status": "historical-HPC-arrivals-only",
        "deadline_status": "not_available_requested_runtime_is_resource_limit",
        "independent_agent_acceptance": None,
        "warning": (
            "Historical HPC submissions across multiple processors, not agent "
            "task arrival/deadline/interrupt preferences. Estimates are empirical "
            "for the archived log only. Requested runtime is not a user task "
            "completion deadline. Source is a pinned third-party mirror, not "
            "independently byte-checked against the original archive."
        ),
    }
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True, help="create-only JSON result path")
    args = p.parse_args()
    reports = {}
    for name, meta in PINNED.items():
        parsed = parse_swf(Path(args.root) / name, expected_hash=meta["sha256"])
        reports[name] = summarize(parsed)
    result = {
        "protocol": "pwa-historical-real-arrival-check-v1",
        "source": SOURCE,
        "pinned_mirror_commit": REPO_COMMIT,
        "datasets": reports,
        "evidence_level": "E1-real-exogenous-arrival-metadata-only",
        "warning": "No natural Agent deadlines or counterfactual action effects.",
    }
    dest = Path(args.out)
    if dest.exists():
        raise FileExistsError("refuse to overwrite audit summary")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
