from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "assemble_canonical_php_staging.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_canonical_source(tmp_path: Path) -> Path:
    source = tmp_path / "canonical-public-html"
    source.mkdir()
    (source / ".htaccess").write_text("RewriteEngine On\n", encoding="utf-8")
    (source / "index.php").write_text("<?php echo 'ok';\n", encoding="utf-8")
    (source / "manifest.php").write_text("<?php return [];\n", encoding="utf-8")
    (source / "sw.js").write_text("self.addEventListener('fetch',()=>{});\n", encoding="utf-8")
    (source / "assets").mkdir()
    (source / "assets" / "app.js").write_text("console.log('ok');\n", encoding="utf-8")

    # Exact release-dirty paths already recorded by the canonical Drive audit.
    (source / "LEGGIMI.txt").write_text("operator note\n", encoding="utf-8")
    (source / "_lib").mkdir()
    (source / "_lib" / "schema.sql").write_text("create table forbidden(x);\n", encoding="utf-8")
    partners = source / "assets" / "partners"
    partners.mkdir()
    (partners / "LEGGIMI-LOGHI.txt").write_text("logo note\n", encoding="utf-8")
    (partners / "wallet-placeholder.png").write_bytes(b"placeholder")
    return source


def _run(source: Path, staging: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(source), str(staging), *extra],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_assembles_clean_disposable_tree_preserving_htaccess_and_restores(tmp_path: Path) -> None:
    source = _make_canonical_source(tmp_path)
    staging = tmp_path / "staging"
    manifest = tmp_path / "manifest.json"
    package = tmp_path / "candidate.zip"
    htaccess_sha = _sha256(source / ".htaccess")
    source_before = {
        p.relative_to(source).as_posix(): p.read_bytes()
        for p in source.rglob("*")
        if p.is_file()
    }

    result = _run(
        source,
        staging,
        "--exclude-known-drive-dirty",
        "--require-sha256",
        f".htaccess={htaccess_sha}",
        "--manifest",
        str(manifest),
        "--package",
        str(package),
        "--restore-check",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert payload["profile"] == "canonical-php"
    assert payload["source_read_only"] is True
    assert payload["restore"]["ok"] is True
    assert set(payload["excluded_known_dirty"]) == {
        "LEGGIMI.txt",
        "_lib/schema.sql",
        "assets/partners/LEGGIMI-LOGHI.txt",
        "assets/partners/wallet-placeholder.png",
    }
    assert _sha256(staging / ".htaccess") == htaccess_sha
    assert not (staging / "LEGGIMI.txt").exists()
    assert not (staging / "_lib" / "schema.sql").exists()
    assert not (staging / "assets" / "partners" / "LEGGIMI-LOGHI.txt").exists()
    assert not (staging / "assets" / "partners" / "wallet-placeholder.png").exists()
    assert package.is_file()
    assert manifest.is_file()

    # The assembler is explicitly non-mutating toward its source snapshot.
    source_after = {
        p.relative_to(source).as_posix(): p.read_bytes()
        for p in source.rglob("*")
        if p.is_file()
    }
    assert source_after == source_before


def test_unknown_secret_fails_closed_and_removes_partial_staging(tmp_path: Path) -> None:
    source = _make_canonical_source(tmp_path)
    (source / ".env.production").write_text("SECRET=must-not-package\n", encoding="utf-8")
    staging = tmp_path / "staging"
    htaccess_sha = _sha256(source / ".htaccess")

    result = _run(
        source,
        staging,
        "--exclude-known-drive-dirty",
        "--require-sha256",
        f".htaccess={htaccess_sha}",
    )

    assert result.returncode == 2
    assert "forbidden environment/secret artifact" in result.stdout
    assert not staging.exists()
    assert (source / ".env.production").is_file()


def test_required_htaccess_hash_mismatch_fails_before_staging_creation(tmp_path: Path) -> None:
    source = _make_canonical_source(tmp_path)
    staging = tmp_path / "staging"

    result = _run(
        source,
        staging,
        "--exclude-known-drive-dirty",
        "--require-sha256",
        f".htaccess={'0' * 64}",
    )

    assert result.returncode == 2
    assert "required source SHA-256 mismatch" in result.stdout
    assert not staging.exists()


def test_destination_inside_source_is_rejected(tmp_path: Path) -> None:
    source = _make_canonical_source(tmp_path)
    staging = source / "staging"
    htaccess_sha = _sha256(source / ".htaccess")

    result = _run(
        source,
        staging,
        "--exclude-known-drive-dirty",
        "--require-sha256",
        f".htaccess={htaccess_sha}",
    )

    assert result.returncode == 2
    assert "must not be inside source tree" in result.stdout
    assert not staging.exists()


def test_source_symlink_is_rejected_without_copying_target(tmp_path: Path) -> None:
    source = _make_canonical_source(tmp_path)
    target = tmp_path / "outside.txt"
    target.write_text("outside\n", encoding="utf-8")
    link = source / "assets" / "outside-link.txt"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    staging = tmp_path / "staging"
    htaccess_sha = _sha256(source / ".htaccess")

    result = _run(
        source,
        staging,
        "--exclude-known-drive-dirty",
        "--require-sha256",
        f".htaccess={htaccess_sha}",
    )

    assert result.returncode == 2
    assert "source contains symlink" in result.stdout
    assert not staging.exists()
    assert target.read_text(encoding="utf-8") == "outside\n"
