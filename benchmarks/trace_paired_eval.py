"""Read-only matched-trace scheduler diagnostic; not a causal effect estimate.

Uses only SHA-verified sessions with observed deadlines and independently
measured work durations. The same environment events are replayed against
urgency-only and affective schedulers. Resample at the lineage level.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random

from affectcontrol import (
    AffectControlHarness, AffectiveScheduler, ControlPolicy,
    KeywordRuleBaseline, MemoryControl, StateEngine, TraceRunner,
    load_jsonl_trace, reference_policy,
)
from benchmarks.trace_cohort import _inside_root, build_cohort


METRICS = ("deadline_miss_rate", "completion_rate", "wall_clock_s")


def _run(path, strategy):
    policy = reference_policy(warn=False)
    harness = AffectControlHarness(
        KeywordRuleBaseline(policy.rule),
        state_engine=StateEngine(policy.state),
        control=ControlPolicy(policy.control),
        memory=MemoryControl(policy.memory),
    )
    trace = load_jsonl_trace(path, max_runtime_s=21600.0)
    scheduler = AffectiveScheduler(policy.scheduler, strategy=strategy)
    return TraceRunner(harness, scheduler).run(trace)


def lineage_paired_interval(rows, *, metric, seed=17, samples=2000):
    """Equal weight for each independent lineage, not every event/session."""
    lineage_values = defaultdict(list)
    for row in rows:
        lineage_values[row["lineage_id"]].append(
            float(row["affective"][metric]) - float(row["urgency"][metric])
        )
    means = [sum(xs) / len(xs) for _, xs in sorted(lineage_values.items())]
    if not means:
        return {"n_lineages": 0, "delta": None, "ci95": [None, None]}
    point = sum(means) / len(means)
    if len(means) < 2:
        return {"n_lineages": len(means), "delta": point,
                "ci95": [None, None],
                "warning": "Only one independent lineage; CI withheld."}
    rng = random.Random(seed)
    boot = sorted(
        sum(rng.choice(means) for _ in means) / len(means)
        for _ in range(samples)
    )
    return {
        "n_lineages": len(means),
        "delta": point,
        "ci95": [boot[int(.025 * (len(boot) - 1))],
                 boot[int(.975 * (len(boot) - 1))]],
        "estimand": "equal_lineage_mean_of_paired_affective_minus_urgency",
    }


def paired_replay(root, manifest, *, partition="validation",
                  unlock_test=False, seed=17):
    if partition not in ("train", "validation", "test"):
        raise ValueError("unknown partition")
    if partition == "test" and not unlock_test:
        raise ValueError("held-out test is locked; freeze the analysis first")
    cohort = build_cohort(root, manifest, seed=seed)
    source_rows = [json.loads(line) for line in
                   Path(manifest).read_text(encoding="utf-8").splitlines() if line.strip()]
    source_by_id = {row["session_id"]: row for row in source_rows}
    selected = [s for s in cohort["sessions"] if s["partition"] == partition]
    eligible = [s for s in selected
                if s["duration_basis"] == "measured"
                and s["deadline_basis"] == "observed"]
    excluded = len(selected) - len(eligible)
    results = []
    for case in eligible:
        original = source_by_id[case["session_id"]]
        file = _inside_root(Path(root), original["trace_file"])
        if hashlib.sha256(file.read_bytes()).hexdigest() != case["trace_sha256"]:
            raise ValueError("trace changed after cohort preflight")
        baseline = _run(file, "urgency")
        affective = _run(file, "affective")
        results.append({
            "session_id": case["session_id"],
            "lineage_id": case["lineage_id"],
            "urgency": {metric: baseline[metric] for metric in METRICS},
            "affective": {metric: affective[metric] for metric in METRICS},
        })
    summary = {
        metric: lineage_paired_interval(results, metric=metric, seed=seed)
        for metric in METRICS
    }
    return {
        "protocol": "matched-trace-diagnostic-v1",
        "partition": partition,
        "split_sha256": cohort["split_sha256"],
        "manifest_sha256": cohort["manifest_sha256"],
        "n_selected_sessions": len(selected),
        "n_eligible_sessions": len(results),
        "n_excluded_unverified_sessions": excluded,
        "n_eligible_lineages": len({r["lineage_id"] for r in results}),
        "primary_metric": "deadline_miss_rate",
        "difference_direction": "affective_minus_urgency; negative improves deadline misses",
        "paired_results": summary,
        "inferential_status": "offline-exogenous-replay-only",
        "warning": (
            "Event timing and durations are frozen across strategies; "
            "this is NOT an observed causal intervention or external efficacy proof. "
            "Provenance is asserted by manifest authors and must be independently audited. "
            "No labels or thresholds are fitted in this script."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--partition", choices=("train", "validation", "test"),
                        default="validation")
    parser.add_argument("--unlock-test", action="store_true",
                        help="explicitly acknowledge inspecting the held-out test")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--out", help="optional JSON output")
    args = parser.parse_args()
    result = paired_replay(args.root, args.manifest,
                           partition=args.partition,
                           unlock_test=args.unlock_test,
                           seed=args.seed)
    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
