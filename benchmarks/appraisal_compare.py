from __future__ import annotations
import argparse, json, math, random
from pathlib import Path
from affectcontrol import brier_score, expected_calibration_error, roc_auc_score, threshold_metrics


def percentile(xs, q):
    if not xs: return None
    ys = sorted(float(x) for x in xs)
    i = min(len(ys) - 1, max(0, round((len(ys) - 1) * q)))
    return ys[i]


def provider_report(rows, provider, threshold):
    usable = [r for r in rows if provider in (r.get("predictions") or {})]
    scores = [float(r["predictions"][provider]) for r in usable]
    labels = [int(r["label"]) for r in usable]
    lat = [float((r.get("latency_ms") or {}).get(provider)) for r in usable
           if (r.get("latency_ms") or {}).get(provider) is not None]
    cost = [float((r.get("cost_usd") or {}).get(provider)) for r in usable
            if (r.get("cost_usd") or {}).get(provider) is not None]
    return {
        "n": len(usable), "coverage": len(usable) / len(rows) if rows else 0.0,
        "brier": brier_score(scores, labels) if usable else None,
        "ece": expected_calibration_error(scores, labels) if usable else None,
        "auroc": roc_auc_score(scores, labels) if usable else None,
        "threshold_metrics": threshold_metrics(scores, labels, threshold) if usable else None,
        "mean_latency_ms": sum(lat) / len(lat) if lat else None,
        "p95_latency_ms": percentile(lat, .95),
        "mean_cost_usd": sum(cost) / len(cost) if cost else None,
    }


def _cluster_id(row):
    # Keep the original session/trajectory as the independent statistical unit.
    cid = row.get("cluster_id", row.get("session_id"))
    if cid is None:
        return None
    if not isinstance(cid, str) or not cid.strip():
        raise ValueError("cluster_id/session_id must be a nonempty string")
    return cid


def paired_brier_bootstrap(rows, a, b, samples=2000, seed=17):
    """Compare paired rows, treating each trajectory as an independent unit.

    Missing cluster identifiers are allowed for a descriptive diagnostic only;
    no confidence interval is calculated in that case.
    """
    if samples < 1:
        raise ValueError("samples must be positive")
    common = [r for r in rows if a in (r.get("predictions") or {})
              and b in (r.get("predictions") or {})]
    if not common:
        return {"n": 0, "n_clusters": 0, "delta_brier_a_minus_b": None,
                "ci95": [None, None], "resampling_unit": "none"}
    diffs = [
        (float(r["predictions"][a]) - float(r["label"])) ** 2 -
        (float(r["predictions"][b]) - float(r["label"])) ** 2
        for r in common
    ]
    ids = [_cluster_id(r) for r in common]
    if all(cid is None for cid in ids):
        return {"n": len(common), "n_clusters": None,
                "delta_brier_a_minus_b": sum(diffs) / len(diffs),
                "ci95": [None, None], "resampling_unit": "descriptive_rows",
                "warning": "No session/cluster IDs; uncertainty cannot be cluster-corrected."}
    if any(cid is None for cid in ids):
        raise ValueError("partial cluster identifiers among paired rows")
    groups = {}
    for cid, diff in zip(ids, diffs):
        groups.setdefault(cid, []).append(diff)
    # A long session must not overwhelm the analysis merely by emitting
    # many more scheduler ticks than another session.
    cluster_means = [sum(x) / len(x) for x in groups.values()]
    point = sum(cluster_means) / len(cluster_means)
    if len(cluster_means) < 2:
        return {"n": len(common), "n_clusters": len(groups),
                "delta_brier_a_minus_b": point,
                "ci95": [None, None], "resampling_unit": "session",
                "warning": "Fewer than two independent sessions; no CI."}
    rng = random.Random(seed)
    boots = [
        sum(rng.choice(cluster_means) for _ in cluster_means) / len(cluster_means)
        for _ in range(samples)
    ]
    boots.sort()
    return {
        "n": len(common), "n_clusters": len(groups),
        "delta_brier_a_minus_b": point,
        "ci95": [boots[int(.025 * (len(boots) - 1))],
                 boots[int(.975 * (len(boots) - 1))]],
        "resampling_unit": "session",
        "estimand": "unweighted_mean_of_session_mean_paired_brier_differences",
    }


def load_rows(path):
    rows = []
    seen = set()
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        row = json.loads(line)
        if type(row.get("label")) is not int or row["label"] not in (0, 1):
            raise ValueError(f"line {n}: label must be integer 0/1")
        if "id" not in row or not isinstance(row["id"], str) or not row["id"].strip():
            raise ValueError(f"line {n}: a nonempty id is required")
        if row["id"] in seen:
            raise ValueError(f"line {n}: duplicate case id")
        seen.add(row["id"])
        _cluster_id(row)  # Fail closed on invalid cluster values.
        preds = row.get("predictions") or {}
        if not isinstance(preds, dict):
            raise ValueError(f"line {n}: predictions must be an object")
        for name, v in preds.items():
            try:
                x = float(v)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {n}: prediction {name} is not numeric") from exc
            if not math.isfinite(x) or not 0 <= x <= 1:
                raise ValueError(f"line {n}: prediction {name} outside [0,1]")
        rows.append(row)
    if not rows: raise ValueError("empty dataset")
    return rows


def compare(path, threshold=.5):
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be within [0,1]")
    rows = load_rows(path)
    providers = sorted({p for r in rows for p in (r.get("predictions") or {})})
    reports = {p: provider_report(rows, p, threshold) for p in providers}
    pairs = {}
    for i, a in enumerate(providers):
        for b in providers[i + 1:]:
            pairs[f"{a}__vs__{b}"] = paired_brier_bootstrap(rows, a, b)
    return {
        "n_rows": len(rows), "threshold": threshold, "providers": reports,
        "paired_brier": pairs,
        "warning": ("Research diagnostics; only session-clustered intervals support "
                    "independent-session inference. Select the primary pair before "
                    "inspecting final labels, and address provider non-coverage."),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--threshold", type=float, default=.5)
    args = ap.parse_args()
    print(json.dumps(compare(args.dataset, args.threshold), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
