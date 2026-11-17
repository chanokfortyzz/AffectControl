import hashlib
import json
from pathlib import Path

import pytest

from affectcontrol.receipt_audit import audit, main, MAX_ARTIFACT_BYTES


def _snapshot(path, tasks):
    path.write_text(json.dumps({"generated_epoch": 1770000000, "tasks": tasks}), encoding="utf-8")
    return path


def _entry(path, *, sha=None, scope="utf8-file-bytes-v1", exists=True, size=None):
    data = {
        "result_path": str(path),
        "result_content_sha256": sha,
        "result_hash_scope": scope,
        "result_exists": exists,
        "result_bytes": size,
    }
    return data


def test_valid_receipt_is_integrity_only(tmp_path):
    root = tmp_path / "authorized"
    root.mkdir()
    file = root / "report.txt"
    file.write_bytes(b"verified bytes only")
    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    snapshot = _snapshot(tmp_path / "state.json", {"secret-id": _entry(
        "report.txt", sha=sha, size=file.stat().st_size)})
    old = snapshot.read_bytes()
    result = audit(snapshot, root)
    assert snapshot.read_bytes() == old
    assert result["counts"]["sha256_matched_bytes"] == 1
    assert result["independently_verified_task_successes"] == 0
    assert result["dispatch_allowed"] is False
    assert "secret-id" not in json.dumps(result)
    assert str(root) not in json.dumps(result)


def test_mismatch_and_size_discrepancy(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    file = root / "out"; file.write_bytes(b"original")
    result = audit(_snapshot(tmp_path / "s.json", {
        "one": _entry(file, sha="0"*64, size=2),
    }), root)
    assert result["counts"]["sha256_mismatch"] == 1
    assert result["counts"]["source_size_mismatch"] == 1


def test_does_not_read_outside_or_symlink(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    outside = tmp_path / "outside.txt"; outside.write_text("secret")
    sha = hashlib.sha256(outside.read_bytes()).hexdigest()
    (root / "linked").symlink_to(outside)
    result = audit(_snapshot(tmp_path / "s.json", {
        "a": _entry(outside, sha=sha),
        "b": _entry(root / "linked", sha=sha),
    }), root)
    # Both are denied by resolved-scope boundary. No secret content is emitted.
    assert result["counts"]["out_of_scope_path"] == 2
    assert result["counts"].get("sha256_matched_bytes", 0) == 0


def test_bad_scope_or_missing_root_means_no_verification(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    f = root / "f"; f.write_text("data")
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    source = _snapshot(tmp_path / "s.json", {
        "a": _entry(f, sha=sha),
        "b": _entry(f, sha=sha, scope="nonstandard"),
        "c": _entry(f, sha=None),
    })
    r = audit(source)
    assert r["counts"]["no_artifact_root_provided"] == 1
    assert r["counts"]["unsupported_hash_scope"] == 1
    assert r["counts"]["no_valid_sha256"] == 1
    assert r["counts"].get("sha256_matched_bytes", 0) == 0


def test_invalid_and_oversized_snapshot(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"tasks":[]}')
    with pytest.raises(ValueError, match="tasks object"):
        audit(p)
    p.write_text("not-json")
    with pytest.raises(ValueError, match="JSON"):
        audit(p)


def test_cli_never_exposes_paths(tmp_path, capsys):
    snapshot = _snapshot(tmp_path / "source.json", {"secret": _entry(
        tmp_path / "private", sha="0"*64)})
    assert main(["--input", str(snapshot)]) == 0
    result = capsys.readouterr().out
    assert "private" not in result
    assert "secret" not in result
    assert json.loads(result)["counts"]["valid_sha256_claims"] == 1
