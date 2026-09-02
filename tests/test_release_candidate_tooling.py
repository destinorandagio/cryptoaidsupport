from __future__ import annotations

import importlib.util
from pathlib import Path


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


def test_forbidden_db_and_dev_artifacts_fail_closed(tmp_path):
    for required in mod.REQUIRED_PWA:
        (tmp_path / required).write_text("x", encoding="utf-8")
    (tmp_path / "cryptoaid.sqlite").write_bytes(b"not-a-real-db")
    (tmp_path / "LEGGIMI.txt").write_text("dev", encoding="utf-8")
    errors = mod.validate_tree(tmp_path)
    assert any("cryptoaid.sqlite" in error for error in errors)
    assert any("LEGGIMI.txt" in error for error in errors)
