"""Read-only integrity and descriptive audit of external Agent run summaries.

This audit does not compare AffectControl policies. It purposefully avoids
any effect significance claim or independent-verification assertion.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

_ARMS = ("B2", "B3")
_NUMERIC = ("wall_seconds", "api_cost_usd", "total_tokens")
_BOOLEAN = ("passed", "workflow_complete")


def audit(files: list[str | Path]) -> dict:
    rows = {}
    sources = []
    for filename in files:
        path = Path(filename)
        content = path.read_bytes()
        sources.append({"filename": path.parent.name + "/" + path.name, "sha256": hashlib.sha256(content).hexdigest()})
        for lineno, line in enumerate(content.decode("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{lineno} invalid JSONL") from exc
            if not isinstance(r, dict):
                raise ValueError("non-object run summary")
            task_id, arm, model, seed = (r.get(x) for x in ("task_id", "arm", "model", "seed"))
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("missing task_id")
            if arm not in _ARMS:
                raise ValueError("unsupported arm")
            if not isinstance(model, str) or not model.strip() or type(seed) is not int:
                raise ValueError("model/seed missing")
            for field in _BOOLEAN:
                if type(r.get(field)) is not bool:
                    raise ValueError(f"{field} must be boolean")
            for field in _NUMERIC:
                val = r.get(field)
                if type(val) not in (int, float) or not math.isfinite(val) or val < 0:
                    raise ValueError(f"{field} must be nonnegative finite")
            verified_by = r.get("verified_by")
            if not isinstance(verified_by, str) or not verified_by.strip():
                raise ValueError("missing verified_by field")
            key = (task_id, model, seed, arm)
            if key in rows:
                raise ValueError("duplicate task-model-seed-arm")
            rows[key] = r
    if not rows:
        raise ValueError("no observations")
    grouped = defaultdict(dict)
    for (task_id, model, seed, arm), record in rows.items():
        grouped[(task_id, model, seed)][arm] = record
    complete = [v for v in grouped.values() if set(v) == set(_ARMS)]
    incomplete = [k for k, v in grouped.items() if set(v) != set(_ARMS)]
    per_arm = {}
    for arm in _ARMS:
        group = [r for key, r in rows.items() if key[3] == arm]
        per_arm[arm] = {
            "n": len(group),
            "passed": sum(r["passed"] for r in group),
            "workflow_complete": sum(r["workflow_complete"] for r in group),
            "mean_wall_seconds": sum(r["wall_seconds"] for r in group) / len(group) if group else None,
            "mean_cost_usd": sum(r["api_cost_usd"] for r in group) / len(group) if group else None,
        }
    deltas = {}
    for field in _NUMERIC:
        xs = [v["B3"][field] - v["B2"][field] for v in complete]
        deltas["paired_mean_B3_minus_B2_" + field] = sum(xs) / len(xs) if xs else None
    return {
        "status": "observational-agent-run-summary-only",
        "source_files": sources,
        "n_records": len(rows),
        "n_matched_tasks": len(complete),
        "n_unmatched_tasks": len(incomplete),
        "declared_verifiers": dict(sorted(Counter(r["verified_by"] for r in rows.values()).items())),
        "per_arm": per_arm,
        "descriptive_paired_differences": deltas,
        "warning": (
            "B2/B3 are Agent evaluation workflow variants, NOT AffectControl scheduler "
            "treatments. Claimed independent_tests are self-reported metadata. "
            "Only a tiny convenience sample; no CI, no population inference, "
            "no causal or external-validity claim. A passed test is not "
            "the same as complete workflow delivery."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = audit(args.files)
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
