"""Read-only S1 -> Sage card/state/result continuity audit.

Compares native S1 provider mappings with the *current* Sage queue,
watchdog state and persisted result files. No provider status is
treated as independently adjudicated business-task acceptance.
No task content or private identifiers are emitted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

from benchmarks.capture_execution import _write_exclusive

SCHEMA = "affectcontrol-native-sage-source-continuity-v1"
CARD = re.compile(r"^### \[(TASK-[^\]]+)\]", re.M)
FIELD = re.compile(r"^- \*\*(.+?)\*\*[:：]\s*(.*)$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
MAX_STATE_BYTES = 20_000_000
MAX_CARD_BYTES = 20_000_000
MAX_RESULT_BYTES = 30_000_000


def hash_data(raw):
    return hashlib.sha256(raw).hexdigest()


def read_cards(path: Path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CARD_BYTES:
        raise ValueError("missing/unsafe queue card source")
    cards = {}
    sections = CARD.split(path.read_text(encoding="utf-8"))
    for i in range(1, len(sections)-1, 2):
        provider = sections[i]
        if provider in cards or not SAFE_ID.fullmatch(provider):
            raise ValueError("duplicate or malformed Sage task card")
        fields = {}
        for line in sections[i+1].splitlines():
            match = FIELD.match(line.strip())
            if match:
                fields.setdefault(match.group(1).strip(),match.group(2).strip())
        cards[provider] = {"s1_ref":fields.get("s1_ref"),"card_status":fields.get("状态") or fields.get("status")}
    return cards


def read_state(path: Path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_STATE_BYTES:
        raise ValueError("missing/unsafe Sage watchdog state")
    doc=json.loads(path.read_bytes())
    if not isinstance(doc,dict) or not isinstance(doc.get("tasks"),dict):
        raise ValueError("invalid Sage watchdog state")
    if len(doc["tasks"]) > 100000:
        raise ValueError("Sage watchdog state unexpectedly large")
    return doc["tasks"]


def get_mappings(db_path):
    db_path = Path(db_path)
    if db_path.is_symlink() or not db_path.is_file():
        raise ValueError("native S1 SQLite source unavailable")
    con = sqlite3.connect("file:"+quote(str(db_path.resolve()),safe="/")+"?mode=ro",uri=True)
    con.execute("PRAGMA query_only=ON")
    try:
        cols={r[1] for r in con.execute("PRAGMA table_info(agent_executions)")}
        if not {"s1_task_id","provider","provider_task_id","status"}.issubset(cols):
            raise ValueError("unrecognized native provider mapping schema")
        mappings = con.execute(
            "SELECT a.s1_task_id,a.provider_task_id,a.status,t.due_at "
            "FROM agent_executions a LEFT JOIN tasks t ON t.id=a.s1_task_id "
            "WHERE a.provider='sage'"
        ).fetchall()
    finally:
        con.close()
    if len(mappings) > 10000:
        raise ValueError("unbounded native provider mapping result")
    return mappings


def audit(db_path, queue_path, state_path, results_directory):
    cards = read_cards(queue_path)
    watchdog = read_state(state_path)
    mappings = get_mappings(db_path)
    result_root = Path(results_directory)
    if result_root.is_symlink() or not result_root.is_dir():
        raise ValueError("missing or unsafe result directory")
    counts=Counter()
    snapshots=[]
    seen=set()
    for native_id, provider_id, db_status, due_at in mappings:
        if not isinstance(native_id,str) or not native_id:
            raise ValueError("invalid native ID in mapping")
        if not isinstance(provider_id,str) or not SAFE_ID.fullmatch(provider_id):
            raise ValueError("unsafe Sage provider task identifier")
        if provider_id in seen:
            raise ValueError("same provider task ID ambiguously mapped")
        seen.add(provider_id)
        counts["native_s1_provider_mappings"]+=1
        db_status = db_status or "missing"
        counts["db_status_"+str(db_status)]+=1
        if isinstance(due_at,str) and due_at.strip():
            counts["mapped_nonempty_due_at"]+=1
        card=cards.get(provider_id)
        state=watchdog.get(provider_id)
        if card is not None:
            counts["mapped_provider_cards_present"]+=1
            if card["s1_ref"]==native_id:
                counts["mapped_card_explicit_s1_ref_matches"]+=1
            elif card["s1_ref"]:
                counts["mapped_card_s1_ref_conflict"]+=1
            else:
                counts["mapped_card_s1_ref_missing"]+=1
        else:
            counts["mapped_provider_cards_absent_from_current_snapshot"]+=1
        if isinstance(state,dict):
            counts["mapped_watchdog_entries_present"]+=1
        else:
            counts["mapped_watchdog_entries_absent_from_current_snapshot"]+=1
        result = result_root / (provider_id+".md")
        if result.is_symlink():
            raise ValueError("symlinked result file unsafe")
        if result.exists():
            if not result.is_file() or result.stat().st_size > MAX_RESULT_BYTES:
                raise ValueError("unexpected Sage result file type or size")
            blob=result.read_bytes()
            if blob:
                counts["mapped_nonempty_result_files"]+=1
                snapshots.append(hash_data(blob))
                if db_status=="COMPLETED":
                    counts["db_completed_with_nonempty_result"]+=1
            else:
                counts["mapped_empty_result_files"]+=1
        else:
            counts["mapped_result_files_missing"]+=1
        if db_status=="COMPLETED" and not result.is_file():
            counts["db_completed_without_result_file"]+=1
    return {
        "schema":SCHEMA,
        "source_type":"local_readonly_S1_Sage_queue_watchdog_and_result_files",
        "current_queue_card_count":len(cards),
        "current_watchdog_task_count":len(watchdog),
        "coverage":dict(sorted(counts.items())),
        "nonempty_result_multiset_sha256":hash_data(
            json.dumps(sorted(snapshots),separators=(",",":")).encode()),
        "native_to_sage_provider_mapping_count":len(mappings),
        "verified_native_s1_to_webclip_message_join_count":0,
        "independent_task_business_acceptance":None,
        "natural_deadline_source_authenticated":None,
        "affectcontrol_vs_urgency_policy_effect":None,
        "evidence_level":"E1-native-provider-continuity-only",
        "warning":(
            "A nonempty result file is a deliverable, not independent "
            "acceptance; an old missing queue/watchdog entry can reflect "
            "archiving/rotation and is not proof task submission failed. "
            "The Sage outbox/card transport and separate WebClip Bus API "
            "have different ID spaces; no Bus-message source join proved."
        ),
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db",required=True)
    p.add_argument("--queue",required=True)
    p.add_argument("--state",required=True)
    p.add_argument("--results",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    r=audit(args.db,args.queue,args.state,args.results)
    output=Path(args.out)
    output.parent.mkdir(parents=True,exist_ok=True)
    _write_exclusive(output,(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print(json.dumps({
        "native_s1_provider_mappings":r["native_to_sage_provider_mapping_count"],
        "current_queue_cards":r["current_queue_card_count"],
        "current_watchdog_tasks":r["current_watchdog_task_count"],
        "coverage":r["coverage"],
        "verified_bus_joins":0,
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
