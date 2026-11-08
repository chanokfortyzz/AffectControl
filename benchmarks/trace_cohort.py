"""Strict preflight and lineage-held-out split for external scheduler traces.

This is a *data admission* gate, not experimental proof. No model scores,
private event text, or test labels are read when creating the split.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import re

from affectcontrol.trace_validation import validate_trace, _required_string, _SHA256


def _inside_root(root: Path, relative: str) -> Path:
    _required_string(relative, "trace_file")
    rel = Path(relative)
    if rel.is_absolute():
        raise ValueError("trace_file must be relative to dataset root")
    root = root.resolve()
    candidate = (root / rel).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        raise ValueError("trace_file escapes dataset root")
    if not candidate.is_file():
        raise ValueError("trace_file not found")
    if candidate.suffix.lower() != ".jsonl":
        raise ValueError("trace_file must end in .jsonl")
    return candidate


def build_cohort(root: str | Path, manifest: str | Path, *,
                 seed=17, train_fraction=0.6, validation_fraction=0.2):
    root = Path(root).resolve()
    manifest = Path(manifest)
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("invalid training/validation fractions")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("no fraction reserved for held-out test")
    content = manifest.read_bytes()
    cases = []
    ids = set()
    paths = set()
    digests = set()
    lineages = set()
    sources = Counter()
    for n, line in enumerate(content.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifest line {n}: invalid JSON") from exc
        if not isinstance(entry, dict):
            raise ValueError(f"manifest line {n}: not a JSON object")
        sid = _required_string(entry.get("session_id"), "session_id")
        lineage = _required_string(entry.get("lineage_id"), "lineage_id")
        provenance = _required_string(entry.get("source"), "source")
        duration_basis = entry.get("duration_basis")
        if duration_basis not in ("measured", "wallclock_proxy", "synthetic"):
            raise ValueError("duration_basis must declare measured/proxy/synthetic")
        deadline_basis = entry.get("deadline_basis")
        if deadline_basis not in ("observed", "inferred", "synthetic", "none"):
            raise ValueError("deadline_basis must declare observed/inferred/synthetic/none")
        if sid in ids:
            raise ValueError("duplicate session_id")
        ids.add(sid)
        path = _inside_root(root, entry.get("trace_file"))
        if path in paths:
            raise ValueError("duplicate trace_file")
        paths.add(path)
        declared = entry.get("sha256")
        if not isinstance(declared, str) or not _SHA256.fullmatch(declared):
            raise ValueError("sha256 must be lowercase hex digest")
        original = path.read_bytes()
        actual = hashlib.sha256(original).hexdigest()
        if actual != declared:
            raise ValueError(f"checksum mismatch for session {sid}")
        if actual in digests:
            raise ValueError("duplicate trace content across sessions")
        digests.add(actual)
        report = validate_trace(original)
        if deadline_basis == "none" and report["n_deadline_events"] != 0:
            raise ValueError("declared no deadlines but trace contains deadlines")
        if deadline_basis != "none" and report["n_deadline_events"] == 0:
            raise ValueError("declared deadline basis but trace has no deadlines")
        sources[provenance] += 1
        lineages.add(lineage)
        cases.append({
            "session_id": sid, "lineage_id": lineage,
            "source": provenance, "duration_basis": duration_basis,
            "deadline_basis": deadline_basis,
            "trace_sha256": actual, **report,
        })
    if len(lineages) < 3:
        raise ValueError("at least three independent lineages required for train/validation/test")
    shuffled = sorted(lineages)
    random.Random(seed).shuffle(shuffled)
    size = len(shuffled)
    n_train = max(1, min(size - 2, int(size * train_fraction)))
    n_val = max(1, min(size - n_train - 1, int(size * validation_fraction)))
    assignment = {
        lineage: ("train" if i < n_train else
                  "validation" if i < n_train + n_val else "test")
        for i, lineage in enumerate(shuffled)
    }
    partitioned = sorted([
        {**case, "partition": assignment[case["lineage_id"]]}
        for case in cases
    ], key=lambda x: x["session_id"])
    counts = Counter(case["partition"] for case in partitioned)
    # The checksum makes the split auditable but not immutable on its own.
    split_spec = {
        "manifest_sha256": hashlib.sha256(content).hexdigest(),
        "seed": seed, "train_fraction": train_fraction,
        "validation_fraction": validation_fraction,
        "assignments": sorted(assignment.items()),
    }
    split_digest = hashlib.sha256(json.dumps(
        split_spec, ensure_ascii=False, sort_keys=True
    ).encode()).hexdigest()
    return {
        "protocol": "lineage-held-out-preflight-v1",
        "inference_status": "data-admission-only",
        "manifest_sha256": split_spec["manifest_sha256"],
        "split_sha256": split_digest,
        "n_sessions": len(cases), "n_lineages": size,
        "partition_session_counts": dict(sorted(counts.items())),
        "source_session_counts": dict(sorted(sources.items())),
        "contains_synthetic_duration": any(c["duration_basis"] == "synthetic" for c in cases),
        "contains_inferred_deadline": any(c["deadline_basis"] == "inferred" for c in cases),
        "sessions": partitioned,
        "warning": (
            "This audit establishes no scheduler benefit. Do not tune on test data. "
            "Lineage IDs, provenance, compute time, deadlines, and completion "
            "oracles must be independently verified."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--out", help="optional JSON audit output")
    args = parser.parse_args()
    result = build_cohort(args.root, args.manifest, seed=args.seed,
                          train_fraction=args.train_fraction,
                          validation_fraction=args.validation_fraction)
    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
