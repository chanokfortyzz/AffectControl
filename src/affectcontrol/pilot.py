"""Isolated AffectControl pilot. Records scoped advice and feedback, never dispatches tasks."""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from .config import ControlPolicyConfig, MemoryPolicyConfig, RuleProviderConfig, StateConfig
from .control import ControlPolicy
from .harness import AffectControlHarness
from .memory import MemoryControl
from .providers import KeywordRuleBaseline
from .state import StateEngine
from .types import AffectiveState, Event

SCHEMA_VERSION = 1
PRIORITIES = {"P0", "P1", "P2", "P3"}
STATUSES = {"success", "partial", "failure"}

def digest(data):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def file_hash(path):
    p = Path(path)
    if not p.is_file():
        raise ValueError("evidence file missing or not a regular file")
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def valid_id(value, field):
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or any(ord(c) < 32 for c in value):
        raise ValueError(f"{field} must be 1..128 printable characters")
    return value

class TxStateStore:
    """Same transaction for persistent affective state and audit decision."""
    def __init__(self, conn):
        self.conn = conn

    def load(self, key):
        row = self.conn.execute("SELECT payload FROM pilot_states WHERE scope=?", (key,)).fetchone()
        return AffectiveState(**json.loads(row[0])) if row else None

    def update(self, key, updater):
        state = updater(self.load(key) or AffectiveState())
        if not isinstance(state, AffectiveState):
            raise TypeError("state updater must return AffectiveState")
        self.conn.execute(
            "INSERT INTO pilot_states(scope,payload) VALUES (?,?) "
            "ON CONFLICT(scope) DO UPDATE SET payload=excluded.payload",
            (key, json.dumps(state.asdict(), ensure_ascii=False, sort_keys=True)))
        return state

class ShadowPilot:
    """Single-host, SQLite-backed, uncalibrated reference policy pilot."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), isolation_level=None, timeout=30)
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS pilot_meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pilot_states(scope TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pilot_decisions(
                event_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                request_hash TEXT NOT NULL, response TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS pilot_outcomes(
                event_id TEXT PRIMARY KEY REFERENCES pilot_decisions(event_id),
                status TEXT NOT NULL, evidence_hash TEXT, hash_checked INTEGER NOT NULL,
                created REAL NOT NULL);
        """)
        version = self.db.execute("SELECT v FROM pilot_meta WHERE k='schema_version'").fetchone()
        if version is None:
            self.db.execute("INSERT INTO pilot_meta(k,v) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
        elif int(version[0]) != SCHEMA_VERSION:
            self.db.close()
            raise ValueError("unsupported pilot schema version")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def harness(self):
        # Explicit reference configs avoid hidden parameters, NOT scientific calibration.
        return AffectControlHarness(
            KeywordRuleBaseline(RuleProviderConfig()),
            state_engine=StateEngine(StateConfig()),
            control=ControlPolicy(ControlPolicyConfig()),
            memory=MemoryControl(MemoryPolicyConfig()),
            store=TxStateStore(self.db))

    def decide(self, *, event_id, task_id, text, priority="P2", immediate=False):
        valid_id(event_id, "event_id")
        valid_id(task_id, "task_id")
        if not isinstance(text, str) or not 1 <= len(text) <= 4000 or not text.strip():
            raise ValueError("text must be 1..4000 nonblank characters")
        if priority not in PRIORITIES:
            raise ValueError("priority must be P0..P3")
        if not isinstance(immediate, bool):
            raise ValueError("immediate must be boolean")
        request_hash = digest({"task_id": task_id, "text": text,
                               "priority": priority, "immediate": immediate})
        with self.transaction():
            prior = self.db.execute(
                "SELECT request_hash,response FROM pilot_decisions WHERE event_id=?", (event_id,)).fetchone()
            if prior:
                if prior[0] != request_hash:
                    raise ValueError("event_id collision: request differs")
                return json.loads(prior[1])
            value = self.harness().process(
                Event(text, task_id=task_id, explicit_user_immediate=immediate),
                base_priority=priority, now_s=time.time())
            urgency = float(value["appraisal"].urgency)
            response = {
                "event_id": event_id, "task_id": task_id, "scope": value["scope_key"],
                "mode": "shadow", "dispatch_allowed": False,
                "policy": "uncalibrated_reference",
                "recommendation": value["control"].asdict(),
                "baseline": {"name": "urgency_only_threshold_0.75",
                             "urgency_score": urgency,
                             "should_interrupt": immediate or urgency >= .75},
                "state_step": value["state"].step,
                "explicit_user_override": immediate,
            }
            self.db.execute(
                "INSERT INTO pilot_decisions(event_id,task_id,request_hash,response,created) "
                "VALUES(?,?,?,?,?)",
                (event_id, task_id, request_hash, json.dumps(response, ensure_ascii=False), time.time()))
            return response

    def feedback(self, *, event_id, status, evidence_file=None, expected_sha256=None):
        valid_id(event_id, "event_id")
        if status not in STATUSES:
            raise ValueError("invalid outcome status")
        if (evidence_file is None) != (expected_sha256 is None):
            raise ValueError("evidence_file and expected_sha256 must be supplied together")
        evidence_hash = None
        checked = False
        if evidence_file is not None:
            if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or any(
                x not in "0123456789abcdef" for x in expected_sha256.lower()
            ):
                raise ValueError("expected_sha256 must be hex SHA-256")
            evidence_hash = file_hash(evidence_file)
            if evidence_hash != expected_sha256.lower():
                raise ValueError("evidence SHA-256 mismatch")
            checked = True
        with self.transaction():
            previous = self.db.execute(
                "SELECT status,evidence_hash,hash_checked FROM pilot_outcomes WHERE event_id=?",
                (event_id,)).fetchone()
            if previous:
                if previous != (status, evidence_hash, int(checked)):
                    raise ValueError("immutable outcome: conflicting replay")
                return self._feedback_response(event_id, status, evidence_hash, checked, True)
            task = self.db.execute(
                "SELECT task_id FROM pilot_decisions WHERE event_id=?", (event_id,)).fetchone()
            if task is None:
                raise ValueError("unknown event_id")
            self.harness().outcome(task[0], success=status == "success",
                                   partial=status == "partial", now_s=time.time())
            self.db.execute(
                "INSERT INTO pilot_outcomes(event_id,status,evidence_hash,hash_checked,created) "
                "VALUES(?,?,?,?,?)",
                (event_id, status, evidence_hash, int(checked), time.time()))
            return self._feedback_response(event_id, status, evidence_hash, checked, False)

    @staticmethod
    def _feedback_response(event_id, status, evidence_hash, checked, replay):
        return {
            "event_id": event_id, "reported_outcome": status,
            "artifact_sha256": evidence_hash,
            "artifact_integrity_checked": checked,
            "outcome_independently_verified": False,
            "idempotent_replay": replay,
        }

    def report(self):
        decisions = [json.loads(r[0]) for r in self.db.execute("SELECT response FROM pilot_decisions")]
        outcomes = self.db.execute("SELECT status,hash_checked FROM pilot_outcomes").fetchall()
        return {
            "mode": "shadow", "dispatch_allowed": False,
            "evidence_level": "engineering only; effectiveness unvalidated",
            "decisions": len(decisions),
            "tasks": self.db.execute("SELECT COUNT(DISTINCT task_id) FROM pilot_decisions").fetchone()[0],
            "scopes": self.db.execute("SELECT COUNT(*) FROM pilot_states").fetchone()[0],
            "explicit_immediate": sum(d["explicit_user_override"] for d in decisions),
            "reference_baseline_interrupt_disagreements": sum(
                d["recommendation"]["should_interrupt"] != d["baseline"]["should_interrupt"]
                for d in decisions),
            "reported_outcomes": len(outcomes),
            "reported_statuses": {s: sum(x[0] == s for x in outcomes) for s in sorted(STATUSES)},
            "artifact_hash_checks": sum(x[1] for x in outcomes),
            "independently_verified_outcomes": 0,
        }

def main(argv=None):
    cli = argparse.ArgumentParser(description="AffectControl shadow pilot (no dispatch)")
    cli.add_argument("--db", default=".affectcontrol/pilot.sqlite3")
    sub = cli.add_subparsers(dest="command", required=True)
    d = sub.add_parser("decide")
    d.add_argument("--event-id", required=True)
    d.add_argument("--task-id", required=True)
    d.add_argument("--text", required=True)
    d.add_argument("--priority", choices=sorted(PRIORITIES), default="P2")
    d.add_argument("--immediate", action="store_true")
    f = sub.add_parser("feedback")
    f.add_argument("--event-id", required=True)
    f.add_argument("--status", choices=sorted(STATUSES), required=True)
    f.add_argument("--evidence-file")
    f.add_argument("--expected-sha256")
    sub.add_parser("report")
    args = cli.parse_args(argv)
    try:
        with ShadowPilot(args.db) as pilot:
            if args.command == "decide":
                result = pilot.decide(event_id=args.event_id, task_id=args.task_id,
                                      text=args.text, priority=args.priority, immediate=args.immediate)
            elif args.command == "feedback":
                result = pilot.feedback(event_id=args.event_id, status=args.status,
                                        evidence_file=args.evidence_file, expected_sha256=args.expected_sha256)
            else:
                result = pilot.report()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, KeyError, OSError, sqlite3.Error) as err:
        print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
