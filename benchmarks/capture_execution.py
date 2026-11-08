"""Opt-in local-process observation: evidence receipts without task content.

A captured single command is a real wall-clock observation, *not* an
independent Agent scheduling experiment or an active-compute-time measure.
Use an explicitly authorized, non-destructive command. No shell or logging
of stdin, argv, environment, stdout, stderr, or task content.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from affectcontrol.trace_validation import validate_trace

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,75}$")
_MAX_SECONDS = 1800.0


def _safe_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{name} must match {_SAFE_ID.pattern}")
    return value


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_exclusive(path: Path, data: bytes) -> None:
    """Create-only, no overwrite; no following a pre-existing symlink."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _hash_stream(stream) -> tuple[str, int]:
    stream.seek(0)
    digest = hashlib.sha256()
    count = 0
    while chunk := stream.read(65536):
        digest.update(chunk)
        count += len(chunk)
    return digest.hexdigest(), count


def _time_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def capture(
    root: str | Path,
    session_id: str,
    lineage_id: str,
    argv: list[str],
    *,
    cwd: str | Path,
    timeout_s: float = 120.0,
) -> dict:
    """Run a command exactly once and persist privacy-reduced observations.

    Output files stay local to root/. A failure/timeout is *observed*, never
    converted into a negative human appraisal label. Does not assert a
    deadline or that lineages are statistically independent.
    """
    session_id = _safe_id(session_id, "session_id")
    lineage_id = _safe_id(lineage_id, "lineage_id")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
        raise ValueError("argv must be a nonempty list of nonempty strings")
    if not isinstance(timeout_s, (int, float)) or not math.isfinite(timeout_s) or not 0 < timeout_s <= _MAX_SECONDS:
        raise ValueError(f"timeout_s must be between 0 and {_MAX_SECONDS}")
    root = Path(root).expanduser().resolve()
    cwd = Path(cwd).expanduser().resolve()
    if not cwd.is_dir():
        raise ValueError("cwd must be an existing directory")
    root.mkdir(parents=True, exist_ok=True)
    # Reject symlink redirection of the two evidence stores before any
    # subprocess executes. Do not silently write outside the chosen root.
    for subdir in ("sessions", "receipts"):
        child = root / subdir
        if child.is_symlink():
            raise ValueError("evidence directory must not be a symlink")
        child.mkdir(exist_ok=True)
        if not child.is_dir() or child.resolve().parent != root:
            raise ValueError("invalid evidence directory")
    session_path = root / "sessions" / f"{session_id}.jsonl"
    receipt_path = root / "receipts" / f"{session_id}.json"
    # Fail before any side effects if session ID was already used.
    if session_path.exists() or receipt_path.exists() or session_path.is_symlink() or receipt_path.is_symlink():
        raise FileExistsError("session_id already exists; never overwrite an observation")
    # Reserve before starting the process: two concurrent writers must not
    # execute the same session_id twice.
    reserve = root / "receipts" / f"{session_id}.reserved"
    reserve_fd = os.open(reserve, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(reserve_fd)
    process_started = False
    try:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            started_utc = _time_iso()
            started = time.perf_counter_ns()
            process_started = True
            try:
                proc = subprocess.run(
                    argv, shell=False, cwd=str(cwd), stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr, timeout=float(timeout_s),
                    check=False,
                )
                exit_code = proc.returncode
                result = "exited"
            except subprocess.TimeoutExpired:
                exit_code = None
                result = "timed_out"
            except OSError as exc:
                exit_code = None
                result = "launch_error"
                # Error type, not untrusted error message containing paths.
                launch_error_type = type(exc).__name__
            ended = time.perf_counter_ns()
            ended_utc = _time_iso()
            observed_s = (ended - started) / 1e9
            stdout_digest, stdout_bytes = _hash_stream(stdout)
            stderr_digest, stderr_bytes = _hash_stream(stderr)

        # The only task input is an opaque identifier. The measured wall
        # duration is a proxy, not independently measured active work.
        event = {
            "at_s": 0.0,
            "kind": "arrive",
            "task_id": session_id,
            "payload": {
                "text": session_id,
                "duration_s": max(observed_s, 1e-9),
                "priority": "P2",
                "preemptible": False,
                "metadata": {
                    "duration_source": "observed_wallclock_proxy",
                    "source_type": "local_process",
                    "session_id": session_id,
                },
            },
        }
        trace = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
        validate_trace(trace)
        command_digest = _sha(json.dumps(argv, ensure_ascii=False).encode())
        receipt = {
            "schema": "affectcontrol-local-observation-v1",
            "session_id": session_id,
            "lineage_id": lineage_id,
            "source": "local-process:opt-in",
            "start_utc": started_utc,
            "end_utc": ended_utc,
            "duration_wallclock_s": observed_s,
            "duration_basis": "wallclock_proxy",
            "deadline_basis": "none",
            "preemptible_observed": False,
            "result": result,
            "exit_code": exit_code,
            "oracle_status": "exit-code-only-not-independent-adjudication",
            "argv_sha256": command_digest,
            "command_name": Path(argv[0]).name,
            "stdout_sha256": stdout_digest,
            "stderr_sha256": stderr_digest,
            "stdout_bytes": stdout_bytes,
            "stderr_bytes": stderr_bytes,
            "trace_sha256": _sha(trace),
            "warning": (
                "This is one real wall-clock process observation, not a causal "
                "scheduler trial, human interruption label, or verified "
                "active-compute duration."
            ),
        }
        if result == "launch_error":
            receipt["launch_error_type"] = launch_error_type
        receipt_bytes = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
        _write_exclusive(session_path, trace)
        try:
            _write_exclusive(receipt_path, receipt_bytes)
        except BaseException:
            session_path.unlink(missing_ok=True)
            raise
        return receipt
    finally:
        # Retain reservation on crash/uncertain process outcome; never risk
        # accidentally rerunning side effects under the same session ID.
        if not process_started:
            reserve.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--lineage-id", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--timeout-s", type=float, default=120)
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="command arguments after --; shell syntax is not interpreted")
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ["--"] else args.command
    result = capture(args.root, args.session_id, args.lineage_id,
                     argv, cwd=args.cwd, timeout_s=args.timeout_s)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
