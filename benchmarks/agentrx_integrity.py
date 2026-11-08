"""Audit a pinned external failure-trajectory sample without fitting a policy.

The failure-only AgentRx tau retail subset can check provenance and label
alignment, but it cannot evaluate AffectControl interruption efficacy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

SOURCE = "https://github.com/microsoft/AgentRx"
SOURCE_COMMIT = "7a18c79708e7671be15124460f4f7296107c2a55"
TRACE_SHA256 = "17f8b3356d1124274cc7ed0215b5ff696970073dbed57394c60e775d5f85d717"
LABEL_SHA256 = "58067689b2ec42f9cbfec2a84ec08d39cea4d8270617b55d0185862753642d16"


def _load(path, digest):
    raw = Path(path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != digest:
        raise ValueError(f"checksum mismatch for {Path(path).name}: {actual}")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")
    return data


def audit(traces, labels):
    if not traces or not labels:
        raise ValueError("empty trajectory or annotation dataset")
    by_id = {}
    for trace in traces:
        identifier = str(trace["task_id"])
        if identifier in by_id:
            raise ValueError(f"duplicate trajectory ID: {identifier}")
        messages = trace.get("traj")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"missing message timeline for {identifier}")
        by_id[identifier] = trace

    labeled = set()
    categories = Counter()
    n_failures = 0
    n_root_steps = 0
    for item in labels:
        identifier = str(item["trajectory_id"])
        if identifier in labeled:
            raise ValueError(f"duplicate ground-truth trajectory ID: {identifier}")
        labeled.add(identifier)
        if identifier not in by_id:
            raise ValueError(f"annotation without trajectory: {identifier}")
        failures = item.get("failures")
        if not isinstance(failures, list) or not failures:
            raise ValueError(f"missing failure annotations for {identifier}")
        root = item.get("root_cause")
        if not isinstance(root, dict):
            raise ValueError(f"missing root_cause for {identifier}")
        root_id = root.get("failure_id")
        root_rows = [x for x in failures if x.get("failure_id") == root_id]
        if len(root_rows) != 1:
            raise ValueError(f"root failure_id is not uniquely present for {identifier}")
        indexes = {m.get("index") for m in by_id[identifier]["traj"]}
        for failure in failures:
            step = failure.get("step_number")
            if type(step) is not int or step < 1:
                raise ValueError(f"invalid failure step for {identifier}")
            if step not in indexes:
                raise ValueError(f"failure step not found in original message index for {identifier}: {step}")
            category = failure.get("failure_category")
            if not isinstance(category, str) or not category:
                raise ValueError(f"missing failure category for {identifier}")
            categories[category] += 1
            n_failures += 1
        n_root_steps += 1

    unmatched = sorted(set(by_id) - labeled)
    rewards = [by_id[x].get("reward") for x in labeled]
    if any(not isinstance(x, (int, float)) for x in rewards):
        raise ValueError("missing or invalid reward")
    return {
        "source": SOURCE, "source_commit": SOURCE_COMMIT,
        "n_trajectories": len(by_id),
        "n_labeled_trajectories": len(labeled),
        "n_unlabeled_trajectories": len(unmatched),
        "n_failure_annotations": n_failures,
        "n_valid_root_refs": n_root_steps,
        "n_failed_rewards": sum(float(x) == 0.0 for x in rewards),
        "n_success_rewards": sum(float(x) > 0.0 for x in rewards),
        "categories": dict(sorted(categories.items())),
        "trace_sha256": TRACE_SHA256,
        "label_sha256": LABEL_SHA256,
        "inference_status": "source-integrity-only",
        "limitation": (
            "Failure-enriched and nonrandom: neither failure-rate reduction nor "
            "policy treatment effect is estimable; annotations mark error steps, "
            "not human-approved interruption decisions."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", required=True)
    parser.add_argument("--labels", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(_load(args.traces, TRACE_SHA256),
                           _load(args.labels, LABEL_SHA256)),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
