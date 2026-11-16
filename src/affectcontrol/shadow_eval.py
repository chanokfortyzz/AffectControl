"""Read-only paired evaluation of AffectControl Pilot interruption advice.

This analyses externally supplied labels, never generates labels from predictions or
runs tasks. Artifact hashes validate byte integrity, not label correctness.
"""
from __future__ import annotations
import argparse
import json
import math
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

from .pilot import file_hash

HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def _read_labels(path):
    labels = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"bad JSONL line {number}") from e
        if not isinstance(row, dict):
            raise ValueError(f"line {number} must be object")
        event_id = row.get("event_id")
        if not isinstance(event_id, str) or not event_id or len(event_id) > 128:
            raise ValueError(f"line {number} missing event_id")
        if event_id in labels:
            raise ValueError(f"duplicate oracle label event_id: {event_id}")
        if type(row.get("should_interrupt")) is not bool:
            raise ValueError(f"line {number} needs boolean should_interrupt")
        reviewer = row.get("reviewer_id")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError(f"line {number} missing reviewer_id")
        if row.get("split") != "holdout":
            raise ValueError(f"line {number} must specify split=holdout")
        if row.get("label_origin") not in {"independent_human", "external_test"}:
            raise ValueError(f"line {number} needs external label_origin")
        if "evidence_file" in row or "evidence_sha256" in row:
            name, sha = row.get("evidence_file"), row.get("evidence_sha256")
            if not isinstance(name, str) or not isinstance(sha, str) or not HEX64.fullmatch(sha):
                raise ValueError(f"line {number} needs evidence_file and valid sha256")
            actual = file_hash(name)
            if actual != sha.lower():
                raise ValueError(f"line {number} evidence hash mismatch")
            row["integrity_checked"] = True
        else:
            row["integrity_checked"] = False
        labels[event_id] = row
    if not labels:
        raise ValueError("empty oracle labels")
    return labels


def _stats(pairs, strategy):
    tp = sum(p[strategy] and p["truth"] for p in pairs)
    fp = sum(p[strategy] and not p["truth"] for p in pairs)
    tn = sum(not p[strategy] and not p["truth"] for p in pairs)
    fn = sum(not p[strategy] and p["truth"] for p in pairs)
    n = len(pairs)
    return {
        "n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": (tp + tn) / n if n else None,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
        "false_negative_rate": fn / (fn + tp) if fn + tp else None,
    }


def _cluster_bootstrap(pairs, samples=2000, seed=17):
    """Paired bootstrap resamples TASK groups, preserving within-task correlation."""
    groups = defaultdict(list)
    for p in pairs:
        groups[p["task_id"]].append(p)
    keys = sorted(groups)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    deltas = []
    for _ in range(samples):
        selected = [p for _ in keys for p in groups[rng.choice(keys)]]
        if not selected:
            continue
        a = _stats(selected, "affective")["accuracy"]
        b = _stats(selected, "baseline")["accuracy"]
        deltas.append(a - b)
    deltas.sort()
    if not deltas:
        return None
    return [deltas[int(.025 * (len(deltas) - 1))], deltas[int(.975 * (len(deltas) - 1))]]


def evaluate(db, labels_path, *, minimum=20):
    if minimum < 1:
        raise ValueError("minimum must be positive")
    path = Path(db).resolve()
    if not path.is_file():
        raise ValueError("pilot DB not found")
    labels = _read_labels(labels_path)
    uri = "file:" + quote(str(path), safe="/") + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        rows = conn.execute(
            "SELECT event_id,task_id,response FROM pilot_decisions ORDER BY event_id").fetchall()
    decisions = {}
    for event_id, task_id, raw in rows:
        response = json.loads(raw)
        decisions[event_id] = (task_id, response)
    unknown = set(labels).difference(decisions)
    if unknown:
        raise ValueError(f"oracle labels refer to unknown decisions: {len(unknown)}")

    paired = []
    explicit = []
    verified = 0
    for event_id, label in labels.items():
        task_id, prediction = decisions[event_id]
        checked = bool(label["integrity_checked"])
        verified += checked
        pair = {
            "task_id": task_id,
            "truth": label["should_interrupt"],
            "affective": bool(prediction["recommendation"]["should_interrupt"]),
            "baseline": bool(prediction["baseline"]["should_interrupt"]),
        }
        if prediction["explicit_user_override"]:
            explicit.append(pair)
        else:
            paired.append(pair)
    def performance(rows):
        a, b = _stats(rows, "affective"), _stats(rows, "baseline")
        return {
            "affective": a, "urgency_only": b,
            "accuracy_delta_affective_minus_urgency": (
                a["accuracy"] - b["accuracy"] if rows else None),
            "paired_discordances": {
                "affective_only_correct": sum(
                    (p["affective"] == p["truth"]) and
                    (p["baseline"] != p["truth"]) for p in rows),
                "urgency_only_correct": sum(
                    (p["baseline"] == p["truth"]) and
                    (p["affective"] != p["truth"]) for p in rows),
            },
            "cluster_bootstrap_95ci_delta": _cluster_bootstrap(rows),
        }
    n = len(paired)
    return {
        "analysis": "paired interruption classification, NOT scheduler-performance validation",
        "label_trust": "self-declared provenance, external independence not authenticated",
        "evidence_integrity": "SHA256 validates bytes only, not task correctness",
        "dispatch_allowed": False,
        "pilot_decisions": len(decisions),
        "oracle_labels": len(labels),
        "label_coverage": len(labels) / len(decisions) if decisions else 0.0,
        "artifact_hash_checked_labels": verified,
        "non_override": performance(paired),
        "explicit_user_override": {
            "n": len(explicit),
            "affective_compliance": sum(p["affective"] for p in explicit) / len(explicit)
                if explicit else None,
            "baseline_compliance": sum(p["baseline"] for p in explicit) / len(explicit)
                if explicit else None,
        },
        "distinct_tasks_with_labels": len(set(p["task_id"] for p in paired + explicit)),
        "minimum_non_override_samples": minimum,
        "sample_gate_met": n >= minimum and len(set(p["task_id"] for p in paired)) >= 2,
        "production_decision": "NOT_APPROVED",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only evaluation of shadow decisions")
    ap.add_argument("--db", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--minimum", type=int, default=20)
    args = ap.parse_args(argv)
    try:
        print(json.dumps(evaluate(args.db, args.labels, minimum=args.minimum),
                         ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
