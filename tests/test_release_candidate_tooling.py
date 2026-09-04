from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mvp_release_candidate.py"
spec = importlib.util.spec_from_file_location("mvp_release_candidate", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_frontend_candidate_is_release_hygiene_clean():
    candidate = ROOT / "frontend" / "public_html"
    assert mod.validate_tree(candidate) == []
    manifest = mod.build_manifest(candidate)
    assert manifest["files"]
    assert manifest["profile"] == "pwa-shell"
    assert len(manifest["manifest_sha256"]) == 64


def test_deterministic_package_and_restore(tmp_path):
    candidate = ROOT / "frontend" / "public_html"
    first = tmp_path / "candidate-a.zip"
    second = tmp_path / "candidate-b.zip"
    manifest = mod.build_manifest(candidate)
    sha_a = mod.write_deterministic_zip(candidate, first)
    sha_b = mod.write_deterministic_zip(candidate, second)
    assert sha_a == sha_b
    restored = mod.restore_and_verify(first, manifest)
    assert restored["ok"] is True
    assert restored["errors"] == []
    assert restored["restored_manifest_sha256"] == manifest["manifest_sha256"]


def test_forbidden_db_dev_and_secret_artifacts_fail_closed(tmp_path):
    for required in mod.PROFILE_REQUIRED["pwa-shell"]:
        (tmp_path / required).write_text("x", encoding="utf-8")
    (tmp_path / "cryptoaid.sqlite").write_bytes(b"not-a-real-db")
    (tmp_path / "LEGGIMI.txt").write_text("dev", encoding="utf-8")
    (tmp_path / ".env.production").write_text("SECRET=x", encoding="utf-8")
    errors = mod.validate_tree(tmp_path)
    assert any("cryptoaid.sqlite" in error for error in errors)
    assert any("LEGGIMI.txt" in error for error in errors)
    assert any(".env.production" in error for error in errors)


def _write_canonical_php_fixture(root: Path) -> str:
    (root / ".htaccess").write_text("DirectoryIndex index.php\n", encoding="utf-8")
    (root / "index.php").write_text("<?php echo 'ok';\n", encoding="utf-8")
    (root / "manifest.php").write_text("<?php echo '{}';\n", encoding="utf-8")
    (root / "sw.js").write_text("self.addEventListener('fetch',()=>{});\n", encoding="utf-8")
    return mod.sha256_file(root / ".htaccess")


def test_canonical_php_profile_requires_htaccess_and_preserves_exact_hash(tmp_path):
    expected_htaccess = _write_canonical_php_fixture(tmp_path)
    required = {".htaccess": expected_htaccess}
    assert mod.validate_tree(tmp_path, profile="canonical-php", required_sha256=required) == []

    (tmp_path / ".htaccess").write_text("DirectoryIndex index.html\n", encoding="utf-8")
    errors = mod.validate_tree(tmp_path, profile="canonical-php", required_sha256=required)
    assert any("required SHA-256 mismatch: .htaccess" in error for error in errors)


def test_canonical_php_package_restore_keeps_profile_and_critical_hash(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    expected_htaccess = _write_canonical_php_fixture(candidate)
    package = tmp_path / "canonical.zip"
    required = {".htaccess": expected_htaccess}

    assert mod.validate_tree(candidate, profile="canonical-php", required_sha256=required) == []
    manifest = mod.build_manifest(candidate, profile="canonical-php")
    assert manifest["profile"] == "canonical-php"
    mod.write_deterministic_zip(candidate, package)
    restored = mod.restore_and_verify(package, manifest, required_sha256=required)
    assert restored["ok"] is True
    assert restored["errors"] == []


def test_symlink_is_rejected_before_packaging(tmp_path):
    for required in mod.PROFILE_REQUIRED["pwa-shell"]:
        (tmp_path / required).write_text("x", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.write_text("private", encoding="utf-8")
    link = tmp_path / "linked-private.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this runner")
    errors = mod.validate_tree(tmp_path)
    assert any("forbidden symlink: linked-private.txt" in error for error in errors)


def test_cli_rejects_symlink_candidate_root(tmp_path):
    target = tmp_path / "real-candidate"
    target.mkdir()
    for required in mod.PROFILE_REQUIRED["pwa-shell"]:
        (target / required).write_text("x", encoding="utf-8")
    linked_root = tmp_path / "candidate-link"
    try:
        linked_root.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlink creation unavailable on this runner")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(linked_root)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "candidate root must not be a symlink/reparse point" in proc.stdout


def test_canonical_php_profile_rejects_known_drive_dirty_artifacts(tmp_path):
    _write_canonical_php_fixture(tmp_path)
    (tmp_path / "LEGGIMI.txt").write_text("remove me", encoding="utf-8")
    lib = tmp_path / "_lib"
    lib.mkdir()
    (lib / "schema.sql").write_text("create table x(id integer);", encoding="utf-8")
    partners = tmp_path / "assets" / "partners"
    partners.mkdir(parents=True)
    (partners / "LEGGIMI-LOGHI.txt").write_text("dev note", encoding="utf-8")
    (partners / "wallet-placeholder.png").write_bytes(b"placeholder")
    errors = mod.validate_tree(tmp_path, profile="canonical-php")
    assert any("LEGGIMI.txt" in error for error in errors)
    assert any("schema.sql" in error for error in errors)
    assert any("LEGGIMI-LOGHI.txt" in error for error in errors)
    assert any("wallet-placeholder.png" in error for error in errors)
