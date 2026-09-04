from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_canonical_php_rollback.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_current(tmp_path: Path) -> Path:
    root = tmp_path / "current-public-html"
    root.mkdir()
    (root / ".htaccess").write_text("RewriteEngine On\n", encoding="utf-8")
    (root / "index.php").write_text("<?php echo 'current';\n", encoding="utf-8")
    (root / "manifest.php").write_text("<?php return ['current'=>true];\n", encoding="utf-8")
    (root / "sw.js").write_text("// current\n", encoding="utf-8")
    (root / "LEGGIMI.txt").write_text("must survive rollback backup\n", encoding="utf-8")
    (root / "_lib").mkdir()
    (root / "_lib" / "schema.sql").write_text("legacy current bytes\n", encoding="utf-8")
    return root


def _make_candidate(tmp_path: Path) -> Path:
    root = tmp_path / "candidate-public-html"
    root.mkdir()
    (root / ".htaccess").write_text("RewriteEngine On\n", encoding="utf-8")
    (root / "index.php").write_text("<?php echo 'candidate';\n", encoding="utf-8")
    (root / "manifest.php").write_text("<?php return ['candidate'=>true];\n", encoding="utf-8")
    (root / "sw.js").write_text("// candidate\n", encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets" / "app.js").write_text("console.log('candidate');\n", encoding="utf-8")
    return root


def _bytes(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and not p.is_symlink()
    }


def _run(current: Path, candidate: Path, workdir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(current), str(candidate), str(workdir), *extra],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_backup_candidate_restore_and_rollback_are_exact_and_sources_read_only(tmp_path: Path) -> None:
    current = _make_current(tmp_path)
    candidate = _make_candidate(tmp_path)
    workdir = tmp_path / "release-transaction"
    current_before = _bytes(current)
    candidate_before = _bytes(candidate)
    current_ht = _sha256(current / ".htaccess")
    candidate_ht = _sha256(candidate / ".htaccess")

    result = _run(
        current,
        candidate,
        workdir,
        "--require-current-sha256",
        f".htaccess={current_ht}",
        "--require-candidate-sha256",
        f".htaccess={candidate_ht}",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["source_read_only"] is True
    assert payload["candidate_restore_ok"] is True
    assert payload["rollback_ok"] is True
    assert payload["rollback_manifest_sha256"] == payload["current_manifest_sha256"]
    assert len(payload["backup_sha256"]) == 64
    assert (workdir / "backup-current.zip").is_file()
    assert (workdir / "active-public-html" / "LEGGIMI.txt").read_text(encoding="utf-8") == "must survive rollback backup\n"
    assert (workdir / "active-public-html" / "_lib" / "schema.sql").read_text(encoding="utf-8") == "legacy current bytes\n"
    assert _bytes(current) == current_before
    assert _bytes(candidate) == candidate_before


def test_candidate_hash_mismatch_fails_before_workdir_creation(tmp_path: Path) -> None:
    current = _make_current(tmp_path)
    candidate = _make_candidate(tmp_path)
    workdir = tmp_path / "release-transaction"

    result = _run(
        current,
        candidate,
        workdir,
        "--require-candidate-sha256",
        f".htaccess={'0' * 64}",
    )

    assert result.returncode == 2
    assert "candidate required SHA-256 mismatch" in result.stdout
    assert not workdir.exists()


def test_current_snapshot_symlink_fails_closed_without_touching_target(tmp_path: Path) -> None:
    current = _make_current(tmp_path)
    candidate = _make_candidate(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = current / "outside-link.txt"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    workdir = tmp_path / "release-transaction"

    result = _run(current, candidate, workdir)

    assert result.returncode == 2
    assert "current snapshot contains symlink" in result.stdout
    assert not workdir.exists()
    assert outside.read_text(encoding="utf-8") == "outside\n"


def test_dirty_candidate_is_rejected_even_if_current_backup_contains_same_legacy_names(tmp_path: Path) -> None:
    current = _make_current(tmp_path)
    candidate = _make_candidate(tmp_path)
    (candidate / "LEGGIMI.txt").write_text("not release clean\n", encoding="utf-8")
    workdir = tmp_path / "release-transaction"

    result = _run(current, candidate, workdir)

    assert result.returncode == 2
    assert "candidate invalid" in result.stdout
    assert "forbidden release artifact" in result.stdout
    assert not workdir.exists()


def test_workdir_inside_source_is_rejected(tmp_path: Path) -> None:
    current = _make_current(tmp_path)
    candidate = _make_candidate(tmp_path)
    workdir = current / "release-transaction"

    result = _run(current, candidate, workdir)

    assert result.returncode == 2
    assert "workdir must not be inside a source tree" in result.stdout
    assert not workdir.exists()
