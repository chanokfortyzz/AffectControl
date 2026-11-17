"""Bounded, read-only verification of Sage result receipts against local bytes.

The supplied snapshot is NOT an independent oracle; successful hash comparison
means the file matches the snapshot claim, not that its task succeeded.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")
SUPPORTED_SCOPE = "utf8-file-bytes-v1"


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(snapshot_path, artifact_root=None):
    source = Path(snapshot_path)
    if not source.is_file() or source.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot missing or exceeds 16 MiB")
    source_bytes = source.read_bytes()
    try:
        snapshot = json.loads(source_bytes)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("snapshot is not UTF-8 JSON") from error
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("tasks"), dict):
        raise ValueError("snapshot requires tasks object")
    root = Path(artifact_root).resolve(strict=True) if artifact_root else None
    if root is not None and not root.is_dir():
        raise ValueError("artifact root must be directory")

    counts = Counter()
    tasks = snapshot["tasks"]
    for task in tasks.values():
        if not isinstance(task, dict):
            counts["invalid_task_records"] += 1
            continue
        counts["tasks"] += 1
        if task.get("process_alive") is True:
            counts["source_process_alive_true"] += 1
        claimed_exists = task.get("result_exists")
        if claimed_exists is True:
            counts["source_result_exists_true"] += 1
        sha = task.get("result_content_sha256")
        if not isinstance(sha, str) or not HASH_RE.fullmatch(sha):
            counts["no_valid_sha256"] += 1
            continue
        counts["valid_sha256_claims"] += 1
        if task.get("result_hash_scope") != SUPPORTED_SCOPE:
            counts["unsupported_hash_scope"] += 1
            continue
        counts["supported_hash_scope"] += 1
        raw_path = task.get("result_path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            counts["missing_result_path"] += 1
            continue
        if root is None:
            counts["no_artifact_root_provided"] += 1
            continue
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        normalized = candidate.resolve(strict=False)
        if not _within(normalized, root):
            counts["out_of_scope_path"] += 1
            continue
        # Deny symlinks at the leaf, even if their target happens to be inside root.
        if candidate.is_symlink():
            counts["symlink_disallowed"] += 1
            continue
        if not normalized.is_file():
            counts["artifact_unavailable"] += 1
            continue
        size = normalized.stat().st_size
        if size > MAX_ARTIFACT_BYTES:
            counts["artifact_too_large"] += 1
            continue
        claimed_size = task.get("result_bytes")
        if type(claimed_size) is int and claimed_size >= 0 and claimed_size != size:
            counts["source_size_mismatch"] += 1
        try:
            actual = _hash_file(normalized)
        except OSError:
            counts["artifact_read_failure"] += 1
            continue
        if actual == sha.lower():
            counts["sha256_matched_bytes"] += 1
        else:
            counts["sha256_mismatch"] += 1

    return {
        "mode": "read_only_receipt_integrity_audit",
        "dispatch_allowed": False,
        "production_decision": "NOT_APPROVED",
        "source_snapshot_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_generated_epoch": snapshot.get("generated_epoch")
            if type(snapshot.get("generated_epoch")) in (int, float) else None,
        "artifact_root_supplied": root is not None,
        "counts": dict(sorted(counts.items())),
        "independently_verified_task_successes": 0,
        "limitations": [
            "hash match proves only file bytes match source snapshot claim",
            "the source snapshot is not independently authenticated",
            "snapshot freshness, task identity and authority are not established",
            "no human or external acceptance test performed",
            "a source result_exists flag alone is not verified file existence",
            "paths outside explicit artifact root and symlink leaf files are never read",
        ],
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description="Read-only Sage receipt byte-integrity audit")
    cli.add_argument("--input", required=True, help="07-MAC_TASK_STATE.json")
    cli.add_argument("--artifact-root", help="explicit root for permitted local artifacts")
    args = cli.parse_args(argv)
    try:
        print(json.dumps(audit(args.input, args.artifact_root), ensure_ascii=False,
                         sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
