"""Audit locally cached Sage queue history vs real native S1 provider IDs.

A cached card is not an authenticated remote acceptance or Bus message.
Only aggregate counts and source SHA256 digests leave private source files.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from benchmarks.capture_execution import _write_exclusive
from benchmarks.native_sage_continuity_audit import get_mappings, read_outbox

SCHEMA = "affectcontrol-sage-queue-history-v1"
CARD = re.compile(r"(?m)^### \[(TASK-[^\]\r\n]+)\]")
FIELD = re.compile(r"^- \*\*(.+?)\*\*[:：]\s*(.*)$")
PATTERNS = ("02-MAC_TASK_QUEUE.md.bak*", "02-MAC_TASK_QUEUE-ARCHIVE*")


def parse_snapshot(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 20_000_000:
        raise ValueError("unsafe historical queue snapshot")
    raw = path.read_bytes()
    sections = CARD.split(raw.decode("utf-8"))
    cards = {}
    for idx in range(1, len(sections)-1, 2):
        ident = sections[idx]
        if ident in cards:
            raise ValueError("duplicate source card")
        fields = {}
        for line in sections[idx+1].splitlines():
            match = FIELD.match(line.strip())
            if match:
                fields.setdefault(match.group(1), match.group(2))
        cards[ident] = (
            fields.get("s1_ref"),
            (fields.get("状态") or fields.get("status") or "").strip().lower(),
        )
    return cards, hashlib.sha256(raw).hexdigest()


def audit(s1_db, bridge_root, outbox=None):
    mappings = get_mappings(s1_db)
    provider_to_native = {}
    for native, provider, _, _ in mappings:
        if not isinstance(native, str) or not native or not isinstance(provider, str) or not re.fullmatch(r"TASK-[A-Za-z0-9_-]+", provider):
            raise ValueError("invalid native/provider mapping")
        if provider in provider_to_native:
            raise ValueError("ambiguous provider ID")
        provider_to_native[provider] = native
    bridge = Path(bridge_root)
    if not bridge.is_dir() or bridge.is_symlink():
        raise ValueError("unsafe Sage Bridge directory")
    snapshots = {}
    for pattern in PATTERNS:
        for file in bridge.glob(pattern):
            if file.is_file():
                snapshots[file.name] = file
    if not snapshots or len(snapshots) > 1000:
        raise ValueError("invalid historical snapshot coverage")

    hits = {provider: [] for provider in provider_to_native}
    source_hashes = []
    count = Counter()
    for filename, path in sorted(snapshots.items()):
        try:
            cards, digest = parse_snapshot(path)
        except ValueError as exc:
            if str(exc) != "duplicate source card":
                raise
            # A merged/duplicated archived card violates the source grain.
            # Preserve source fingerprint but EXCLUDE that snapshot entirely.
            # Never select whichever duplicate has a favorable state.
            count["duplicate_card_snapshots_excluded"] += 1
            source_hashes.append((filename, hashlib.sha256(path.read_bytes()).hexdigest()))
            continue
        source_hashes.append((filename, digest))
        count["eligible_historical_queue_snapshots"] += 1
        for provider, native in provider_to_native.items():
            if provider not in cards:
                continue
            ref, status = cards[provider]
            relation = ("matching_s1_ref" if ref == native
                        else "no_s1_ref" if not ref else "conflicting_s1_ref")
            hits[provider].append((relation, status))
    count["mapped_native_s1_tasks"] = len(provider_to_native)
    for provider, records in hits.items():
        if not records:
            count["mapped_tasks_without_any_historical_queue_card"] += 1
            continue
        count["mapped_tasks_with_historical_provider_id_card"] += 1
        if any(x == "matching_s1_ref" for x, _ in records):
            count["mapped_tasks_with_explicit_matching_s1_ref_card"] += 1
        if any(x == "no_s1_ref" for x, _ in records):
            count["mapped_tasks_with_provider_id_only_card"] += 1
        if any(x == "conflicting_s1_ref" for x, _ in records):
            count["mapped_tasks_with_conflicting_s1_ref_card"] += 1
        if any(s in ("queued", "pending") for _, s in records):
            count["mapped_tasks_with_historical_queued_card"] += 1
        if any(s in ("done", "completed", "closed") for _, s in records):
            count["mapped_tasks_with_historical_done_card"] += 1
        count["provider_card_snapshot_occurrences"] += len(records)

    outbox_evidence = None
    if outbox is not None:
        pairs, digest = read_outbox(outbox)
        if len(pairs) != len(set(pairs)):
            raise ValueError("duplicate native/provider outbox request")
        outbox_evidence = {
            "source_sha256": digest,
            "exact_local_submission_matches": sum(
                (native, provider) in set(pairs)
                for provider, native in provider_to_native.items()
            ),
            "remote_delivery_confirmed": None,
        }
    manifest_digest = hashlib.sha256(json.dumps(
        source_hashes, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "schema": SCHEMA,
        "historical_queue_snapshots_examined": len(snapshots),
        "snapshot_manifest_sha256": manifest_digest,
        "coverage": dict(sorted(count.items())),
        "outbox_evidence": outbox_evidence,
        "independently_authenticated_remote_sage_ack": None,
        "verified_native_s1_webclip_message_join": None,
        "independent_business_task_acceptance": None,
        "evidence_level": "E1-local-archived-card-evidence-only",
        "warning": (
            "Queue snapshots are local and unsigned; provider-ID-only "
            "matches are weaker than a card with matching s1_ref. "
            "The word done is a historic source status, not independently "
            "accepted completion; Outbox proves only local submission intent."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--bridge", required=True)
    parser.add_argument("--outbox")
    parser.add_argument("--out", required=True)
    a = parser.parse_args()
    result = audit(a.db, a.bridge, a.outbox)
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(path, (json.dumps(result, sort_keys=True, indent=2) + "\n").encode())
    print(json.dumps(result["coverage"], sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
