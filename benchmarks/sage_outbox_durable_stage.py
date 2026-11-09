"""Crash-recoverable, idempotent Sage Outbox receiver in a PRIVATE staging root.

Research protocol only. NO production Sage queue, native S1 DB, WebClip
message, credential or automatic task dispatch. A local receipt records
durable staging state, NOT independently authenticated Sage intake.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re

from benchmarks.sage_outbox_staged_intake import (
    SCHEMA as SOURCE_SCHEMA, _write_exclusive, digest, parse_append, read,
)

SCHEMA = "affectcontrol-sage-outbox-durable-stage-v1"
FILE_LIMIT = 20_000_000
PROVIDER_IDS = re.compile(r"(?m)^### \[(TASK-[^\]\r\n]+)\]")
FATAL_PHASES = frozenset(("after_prepare", "after_queue", "after_state"))


class InjectedCrash(RuntimeError):
    """Test-only interruption immediately after a durable phase."""


def _encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False)+"\n").encode("utf-8")


def _sync_directory(root):
    if os.name != "nt":
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


@contextmanager
def _exclusive_lock(root):
    # OS-managed lock releases when the process dies. Unlike an O_EXCL lock
    # file, it cannot permanently block startup after a hard crash.
    file = root / ".receiver.lock"
    if file.is_symlink():
        raise ValueError("unsafe staging lock")
    with file.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError("staging receiver already locked") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError("staging receiver already locked") from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _private_root(path):
    root = Path(path)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("missing or linked private staging root")
    for name in ("queue.md", "state.json", "pending.json", "queue.next", "state.next"):
        if (root / name).is_symlink():
            raise ValueError("unsafe staging file symlink")
    return root


def _read_state(root):
    blob = read(root / "state.json")
    state = json.loads(blob)
    if state.get("schema") != SCHEMA:
        raise ValueError("invalid receiver state")
    if type(state.get("cursor_bytes")) is not int or state["cursor_bytes"] < 1:
        raise ValueError("invalid receiver cursor")
    for k in ("source_prefix_sha256", "queue_sha256"):
        if not re.fullmatch("[a-f0-9]{64}", str(state.get(k, ""))):
            raise ValueError("invalid receiver digest")
    if not isinstance(state.get("accepted"), dict):
        raise ValueError("invalid staged acceptance ledger")
    return state, blob


def initialize(source, initial_queue, root):
    """Pin all existing requests as prior history; never replay them."""
    original = read(source)
    original.decode("utf-8")
    if not original.endswith(b"\n"):
        raise ValueError("incomplete Outbox initial snapshot")
    template = read(initial_queue)
    template.decode("utf-8")
    root = Path(root)
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    state = {
        "schema": SCHEMA,
        "cursor_bytes": len(original),
        "source_prefix_sha256": digest(original),
        "queue_sha256": digest(template),
        "accepted": {},
        "committed_steps": 0,
        "historical_requests_replayed": 0,
        "real_sage_receiver_acknowledgement": None,
        "actual_webclip_message_id": None,
        "auto_dispatch_allowed": False,
    }
    _write_exclusive(root / "queue.md", template)
    _write_exclusive(root / "state.json", _encode(state))
    _sync_directory(root)
    return public_status(root)


def _render_cards(tasks):
    out = ""
    for x in tasks:
        out += (
            "\n\n### [" + x["card"] + "]\n"
            "- **状态**：queued\n"
            "- **来源**：S1-staged-only-not-production\n"
            "- **s1_ref**：" + x["native"] + "\n"
            "- **描述**：" + x["goal"] + "\n"
            "- **risk**：" + x["risk"] + "\n"
            "- **auto_run**：no\n"
            "- **requires_user_confirm**：yes\n"
            "- **router_decision**：STAGING_NOT_DISPATCHABLE\n"
        )
    return out.encode("utf-8")


def _recover_locked(root, *, crash_at=None):
    pending_file = root / "pending.json"
    if not pending_file.exists():
        if (root / "queue.next").exists() or (root / "state.next").exists():
            raise ValueError("orphan staging temporary file without pending journal")
        return False
    p = json.loads(read(pending_file))
    if p.get("schema") != SCHEMA or not isinstance(p.get("new_state"), dict):
        raise ValueError("invalid pending journal")
    new_state_bytes = _encode(p["new_state"])
    new_queue_bytes = base64.b64decode(p["new_queue_b64"], validate=True)
    if len(new_queue_bytes) > FILE_LIMIT:
        raise ValueError("oversized staged queue")
    if digest(new_queue_bytes) != p.get("new_queue_sha256"):
        raise ValueError("pending queue hash mismatch")
    old_state_sha = p.get("old_state_sha256")
    old_queue_sha = p.get("old_queue_sha256")
    current_state = read(root / "state.json")
    current_queue = read(root / "queue.md")
    state_sha = digest(current_state)
    queue_sha = digest(current_queue)
    new_state_sha = digest(new_state_bytes)
    if state_sha not in (old_state_sha, new_state_sha):
        raise ValueError("staging state changed during pending transaction")
    if queue_sha not in (old_queue_sha, p["new_queue_sha256"]):
        raise ValueError("staging queue changed during pending transaction")
    if state_sha == new_state_sha and queue_sha == old_queue_sha and queue_sha != p["new_queue_sha256"]:
        raise ValueError("state committed before required queue bytes")
    if queue_sha == old_queue_sha and queue_sha != p["new_queue_sha256"]:
        target = root / "queue.next"
        if target.exists():
            # The process may have died midway through writing queue.next.
            # Rebuild ONLY this private temporary file from the already
            # durable journal; never reconstruct or overwrite live sources.
            if digest(target.read_bytes()) != p["new_queue_sha256"]:
                target.unlink()
                _write_exclusive(target, new_queue_bytes)
        else:
            _write_exclusive(target, new_queue_bytes)
        os.replace(target, root / "queue.md")
        _sync_directory(root)
    if crash_at == "after_queue":
        raise InjectedCrash("after_queue")
    if state_sha == old_state_sha and state_sha != new_state_sha:
        target = root / "state.next"
        if target.exists():
            if digest(target.read_bytes()) != new_state_sha:
                target.unlink()
                _write_exclusive(target, new_state_bytes)
        else:
            _write_exclusive(target, new_state_bytes)
        os.replace(target, root / "state.json")
        _sync_directory(root)
    if crash_at == "after_state":
        raise InjectedCrash("after_state")
    if digest(read(root / "queue.md")) != p["new_queue_sha256"] or digest(read(root / "state.json")) != new_state_sha:
        raise ValueError("transaction recovery postcondition failed")
    pending_file.unlink()
    _sync_directory(root)
    return True


def recover(root):
    root = _private_root(root)
    with _exclusive_lock(root):
        _recover_locked(root)
    return public_status(root)


def tick(source, root, *, crash_at=None):
    """Durably convert only new requests into PRIVATE non-executable cards."""
    if crash_at not in FATAL_PHASES | {None}:
        raise ValueError("invalid test crash phase")
    root = _private_root(root)
    with _exclusive_lock(root):
        _recover_locked(root)
        state, original_state_bytes = _read_state(root)
        queue_bytes = read(root / "queue.md")
        if digest(queue_bytes) != state["queue_sha256"]:
            raise ValueError("staged queue changed outside receiver transaction")
        incoming = read(source)
        cursor = state["cursor_bytes"]
        if len(incoming) < cursor or digest(incoming[:cursor]) != state["source_prefix_sha256"]:
            raise ValueError("Outbox has rotated, truncated or changed original bytes")
        if len(incoming) == cursor:
            return {"new_candidate_count": 0, "noop": True, "production_dispatch_changed": False}
        if not incoming.endswith(b"\n"):
            raise ValueError("incomplete appended Outbox write")
        suffix = incoming[cursor:]
        tasks = parse_append(suffix.decode("utf-8"))
        accepted = dict(state["accepted"])
        current_ids = set(PROVIDER_IDS.findall(queue_bytes.decode("utf-8")))
        native_ids = {record["native_ref_sha256"] for record in accepted.values()}
        for item in tasks:
            card_hash = digest(item["card"].encode("utf-8"))
            native_hash = digest(item["native"].encode("utf-8"))
            if item["card"] in current_ids or card_hash in accepted or native_hash in native_ids:
                raise ValueError("previously accepted or existing S1 request collision")
            accepted[card_hash] = {
                "native_ref_sha256": native_hash,
                "source_entry_sha256": item["source_entry_sha256"],
            }
        new_queue = queue_bytes + _render_cards(tasks)
        next_state = {
            **state, "cursor_bytes": len(incoming),
            "source_prefix_sha256": digest(incoming),
            "queue_sha256": digest(new_queue),
            "accepted": accepted,
            "committed_steps": state["committed_steps"] + 1,
        }
        pending = {
            "schema": SCHEMA,
            "old_state_sha256": digest(original_state_bytes),
            "old_queue_sha256": digest(queue_bytes),
            "new_queue_sha256": digest(new_queue),
            "new_queue_b64": base64.b64encode(new_queue).decode("ascii"),
            "new_state": next_state,
        }
        _write_exclusive(root / "pending.json", _encode(pending))
        _sync_directory(root)
        if crash_at == "after_prepare":
            raise InjectedCrash("after_prepare")
        _recover_locked(root, crash_at=crash_at)
        return {
            "new_candidate_count": len(tasks),
            "noop": False,
            "production_dispatch_changed": False,
            "real_sage_receiver_acknowledgement": None,
        }


def public_status(root):
    root = _private_root(root)
    state, _ = _read_state(root)
    return {
        "schema": SCHEMA, "historical_requests_replayed": 0,
        "staged_candidate_count": len(state["accepted"]),
        "committed_steps": state["committed_steps"],
        "pending_transaction_exists": (root / "pending.json").exists(),
        "auto_dispatch_allowed": False,
        "real_sage_receiver_acknowledgement": None,
        "real_webclip_bus_message_id": None,
        "evidence_level": "E1-isolated-durable-receiver-not-Sage-production",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("init")
    a.add_argument("--source", required=True)
    a.add_argument("--queue", required=True)
    a.add_argument("--root", required=True)
    a = sub.add_parser("tick")
    a.add_argument("--source", required=True)
    a.add_argument("--root", required=True)
    a = sub.add_parser("recover")
    a.add_argument("--root", required=True)
    a = p.parse_args()
    if a.mode == "init":
        result = initialize(a.source, a.queue, a.root)
    elif a.mode == "tick":
        result = tick(a.source, a.root)
    else:
        result = recover(a.root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
