"""Read-only native S1 ↔ Sage provider mapping census, privacy-reduced.

Native S1 task IDs and Sage provider task IDs are already joined in the
production S1 SQLite schema. This is NOT a verified Bus message join,
independent task success or natural/user-origin deadline attestation.
No task inputs, titles, IDs, provider tokens or message metadata values
leave the source DB; only aggregate counts and schema fingerprint.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from benchmarks.capture_execution import _write_exclusive

EXPECTED = {
    "tasks": {"id", "created_at", "due_at", "status"},
    "agent_executions": {"s1_task_id", "provider", "provider_task_id", "status"},
    "events": {"task_id", "meta"},
}
BUS_FIELDS = ("request_id", "message_id", "thread_id", "reply_message_id")
SCHEMA = "affectcontrol-native-s1-sage-mapping-census-v1"


def audit(db_path):
    db_path = Path(db_path)
    if not db_path.is_file() or db_path.is_symlink():
        raise ValueError("existing regular native S1 database required")
    uri = "file:" + quote(str(db_path.resolve()), safe="/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        fields = {}
        for table, required in EXPECTED.items():
            available = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
            if not required.issubset(available):
                raise ValueError(f"{table}: unrecognized source schema")
            fields[table] = sorted(available)
        rows = conn.execute(
            "SELECT a.s1_task_id,a.provider,a.provider_task_id,a.status,"
            "t.id,t.due_at,t.created_at,t.status "
            "FROM agent_executions a LEFT JOIN tasks t ON a.s1_task_id=t.id"
        ).fetchall()
        if len(rows) > 10000:
            raise ValueError("unexpected native mapping volume")
        mapping_task_ids = set()
        provider_task_ids = set()
        provider_statuses = {}
        missing_task_refs = 0
        invalid_mapping_ids = 0
        mapped_due_at_filled = 0
        for s1_id, provider, provider_id, status, matched, due, created, task_status in rows:
            if not isinstance(s1_id, str) or not s1_id or not isinstance(provider_id, str) or not provider_id:
                invalid_mapping_ids += 1
                continue
            mapping_task_ids.add(s1_id)
            provider_task_ids.add((provider, provider_id))
            if matched is None:
                missing_task_refs += 1
            if isinstance(due, str) and due.strip():
                mapped_due_at_filled += 1
            provider_statuses[status or "missing"] = provider_statuses.get(status or "missing", 0) + 1
        total_tasks, with_due = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN due_at IS NOT NULL AND TRIM(CAST(due_at AS TEXT))<>'' "
            "THEN 1 ELSE 0 END) FROM tasks"
        ).fetchone()
        event_key_counts = {k: 0 for k in BUS_FIELDS}
        mapped_bus_meta = {k: 0 for k in BUS_FIELDS}
        for event_task, raw in conn.execute("SELECT task_id,meta FROM events"):
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(obj, dict):
                continue
            for key in BUS_FIELDS:
                if obj.get(key):
                    event_key_counts[key] += 1
                    if event_task in mapping_task_ids:
                        mapped_bus_meta[key] += 1
        schema_hash = hashlib.sha256(json.dumps(
            fields, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        return {
            "schema": SCHEMA,
            "source": "native_S1_SQLite_uri_read_only",
            "source_schema_sha256": schema_hash,
            "native_task_count": total_tasks,
            "native_task_due_at_nonempty": int(with_due or 0),
            "native_s1_sage_provider_mapping_rows": len(rows),
            "unique_s1_mapped_task_ids": len(mapping_task_ids),
            "unique_provider_task_refs": len(provider_task_ids),
            "missing_native_task_foreign_refs": missing_task_refs,
            "invalid_native_provider_mapping_ids": invalid_mapping_ids,
            "mapped_task_due_at_nonempty": mapped_due_at_filled,
            "native_provider_reported_status_counts": dict(sorted(provider_statuses.items())),
            "unattributed_native_event_bus_meta_key_counts": event_key_counts,
            "mapped_task_event_bus_meta_key_counts": mapped_bus_meta,
            "verified_native_s1_to_real_bus_message_joins": 0,
            "independent_agent_business_acceptance": None,
            "original_deadline_source_attested": None,
            "affectcontrol_policy_trial": None,
            "evidence_level": "E1-native-S1-to-Sage-provider-metadata-only",
            "warning": (
                "Native S1↔Sage provider IDs reflect the app's own mapping "
                "table, not verified WebClip message links. Recorded status "
                "COMPLETED is not independent success. S1 due_at is an "
                "unattested field. Bus metadata elsewhere cannot be joined "
                "without authenticated origin-bound provenance."
            ),
        }
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    result = audit(a.db)
    target = Path(a.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(target, (json.dumps(result, sort_keys=True, indent=2)+"\n").encode())
    print(json.dumps({
        "native_s1_sage_provider_mapping_rows": result["native_s1_sage_provider_mapping_rows"],
        "native_task_due_at_nonempty": result["native_task_due_at_nonempty"],
        "mapped_task_bus_metadata": result["mapped_task_event_bus_meta_key_counts"],
        "verified_native_s1_to_real_bus_message_joins": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
