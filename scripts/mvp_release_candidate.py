#!/usr/bin/env python3
"""Deterministic, staging-only release-candidate packaging for CryptoAID MVP.

This tool never deploys. It validates a candidate tree, rejects release-forbidden
artifacts, writes a deterministic manifest, creates a reproducible ZIP, and can
restore/verify that ZIP into a disposable directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

FORBIDDEN_NAMES = {
    "BLOCKCHAINPLUS-MASTER.sqlite",
    "cryptoaid.sqlite",
    "DEMO-APERTA.flag",
    "LEGGIMI.txt",
    "LEGGIMI-LOGHI.txt",
    "schema.sql",
}
FORBIDDEN_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx"}
REQUIRED_PWA = {"index.html", "manifest.webmanifest", "sw.js", "offline.html"}
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def candidate_files(root: Path) -> list[Path]:
    return sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )


def validate_tree(root: Path) -> list[str]:
    errors: list[str] = []
    if not root.is_dir():
        return [f"candidate root is not a directory: {root}"]

    rels = {p.relative_to(root).as_posix() for p in candidate_files(root)}
    missing = sorted(REQUIRED_PWA - rels)
    if missing:
        errors.append("missing required PWA files: " + ", ".join(missing))

    for path in candidate_files(root):
        rel = path.relative_to(root)
        if path.name in FORBIDDEN_NAMES:
            errors.append(f"forbidden release artifact: {rel.as_posix()}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden sensitive/database suffix: {rel.as_posix()}")
        if any(part in {".git", "__pycache__", ".pytest_cache", "node_modules"} for part in rel.parts):
            errors.append(f"forbidden dev directory content: {rel.as_posix()}")
    return sorted(set(errors))


def build_manifest(root: Path) -> dict:
    files = []
    for path in candidate_files(root):
        rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    payload = {"schema_version": "1.0", "files": files}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["manifest_sha256"] = sha256_bytes(canonical)
    return payload


def write_deterministic_zip(root: Path, out: Path) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in candidate_files(root):
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(PurePosixPath(rel).as_posix(), ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return sha256_file(out)


def restore_and_verify(package: Path, expected_manifest: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="cryptoaid-restore-") as td:
        root = Path(td)
        with zipfile.ZipFile(package, "r") as zf:
            for name in zf.namelist():
                dest = (root / name).resolve()
                if root.resolve() not in dest.parents:
                    raise ValueError(f"unsafe ZIP member: {name}")
            zf.extractall(root)
        errors = validate_tree(root)
        restored = build_manifest(root)
        return {
            "ok": not errors and restored["manifest_sha256"] == expected_manifest["manifest_sha256"],
            "errors": errors,
            "restored_manifest_sha256": restored["manifest_sha256"],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--restore-check", action="store_true")
    args = parser.parse_args()

    root = args.candidate.resolve()
    errors = validate_tree(root)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        return 2

    manifest = build_manifest(root)
    result = {"status": "PASS", "manifest_sha256": manifest["manifest_sha256"], "file_count": len(manifest["files"])}
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.package:
        package_sha = write_deterministic_zip(root, args.package)
        result["package_sha256"] = package_sha
        if args.restore_check:
            result["restore"] = restore_and_verify(args.package, manifest)
            if not result["restore"]["ok"]:
                print(json.dumps(result, indent=2, sort_keys=True))
                return 3
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
