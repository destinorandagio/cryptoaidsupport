#!/usr/bin/env python3
"""Deterministic, staging-only release-candidate packaging for CryptoAID MVP.

This tool never deploys. It validates a candidate tree, rejects release-forbidden
artifacts, writes a deterministic manifest, creates a reproducible ZIP, and can
restore/verify that ZIP into a disposable directory.

Two explicit release profiles are supported:
- pwa-shell: repository frontend shell used by CI smoke tests.
- canonical-php: disposable staging copy of the canonical PHP public_html tree.

The canonical profile can require exact SHA-256 preservation for critical files
(for example .htaccess) without ever mutating the canonical Drive tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
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
    "wallet-placeholder.png",
}
FORBIDDEN_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx"}
FORBIDDEN_DEV_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}
PROFILE_REQUIRED = {
    "pwa-shell": {"index.html", "manifest.webmanifest", "sw.js", "offline.html"},
    "canonical-php": {".htaccess", "index.php", "manifest.php", "sw.js"},
}
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def candidate_entries(root: Path) -> list[Path]:
    return sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())


def candidate_files(root: Path) -> list[Path]:
    return [p for p in candidate_entries(root) if p.is_file() and not p.is_symlink()]


def _is_reparse_point(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def _forbidden_secret_name(name: str) -> bool:
    lowered = name.lower()
    return lowered == ".env" or lowered.startswith(".env.")


def _normalize_required_hashes(required_sha256: dict[str, str] | None) -> tuple[dict[str, str], list[str]]:
    normalized: dict[str, str] = {}
    errors: list[str] = []
    for raw_path, raw_hash in (required_sha256 or {}).items():
        rel = PurePosixPath(raw_path)
        if rel.is_absolute() or ".." in rel.parts or str(rel) in {"", "."}:
            errors.append(f"invalid required-hash path: {raw_path}")
            continue
        digest = raw_hash.lower().strip()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            errors.append(f"invalid required SHA-256 for {raw_path}")
            continue
        normalized[rel.as_posix()] = digest
    return normalized, errors


def validate_tree(
    root: Path,
    profile: str = "pwa-shell",
    required_sha256: dict[str, str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if profile not in PROFILE_REQUIRED:
        return [f"unknown release profile: {profile}"]
    if not root.is_dir():
        return [f"candidate root is not a directory: {root}"]
    if root.is_symlink() or _is_reparse_point(root):
        return [f"candidate root must not be a symlink/reparse point: {root}"]

    entries = candidate_entries(root)
    for path in entries:
        rel = path.relative_to(root)
        rel_text = rel.as_posix()
        if path.is_symlink():
            errors.append(f"forbidden symlink: {rel_text}")
            continue
        if _is_reparse_point(path):
            errors.append(f"forbidden reparse point: {rel_text}")
        if any(part in FORBIDDEN_DEV_DIRS for part in rel.parts):
            errors.append(f"forbidden dev directory content: {rel_text}")
        if path.is_file():
            if path.name in FORBIDDEN_NAMES:
                errors.append(f"forbidden release artifact: {rel_text}")
            if _forbidden_secret_name(path.name):
                errors.append(f"forbidden environment/secret artifact: {rel_text}")
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                errors.append(f"forbidden sensitive/database suffix: {rel_text}")

    rels = {p.relative_to(root).as_posix() for p in candidate_files(root)}
    missing = sorted(PROFILE_REQUIRED[profile] - rels)
    if missing:
        errors.append(f"missing required {profile} files: " + ", ".join(missing))

    normalized_hashes, hash_errors = _normalize_required_hashes(required_sha256)
    errors.extend(hash_errors)
    for rel, expected in normalized_hashes.items():
        path = root / Path(*PurePosixPath(rel).parts)
        if not path.is_file() or path.is_symlink():
            errors.append(f"required hash target missing or non-regular: {rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(f"required SHA-256 mismatch: {rel} expected={expected} actual={actual}")

    return sorted(set(errors))


def build_manifest(root: Path, profile: str = "pwa-shell") -> dict:
    files = []
    for path in candidate_files(root):
        rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    payload = {"schema_version": "1.1", "profile": profile, "files": files}
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


def restore_and_verify(
    package: Path,
    expected_manifest: dict,
    required_sha256: dict[str, str] | None = None,
) -> dict:
    profile = expected_manifest.get("profile", "pwa-shell")
    with tempfile.TemporaryDirectory(prefix="cryptoaid-restore-") as td:
        root = Path(td)
        with zipfile.ZipFile(package, "r") as zf:
            for name in zf.namelist():
                member = PurePosixPath(name)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError(f"unsafe ZIP member: {name}")
                dest = (root / Path(*member.parts)).resolve()
                if dest != root.resolve() and root.resolve() not in dest.parents:
                    raise ValueError(f"unsafe ZIP member: {name}")
            zf.extractall(root)
        errors = validate_tree(root, profile=profile, required_sha256=required_sha256)
        restored = build_manifest(root, profile=profile)
        return {
            "ok": not errors and restored["manifest_sha256"] == expected_manifest["manifest_sha256"],
            "errors": errors,
            "restored_manifest_sha256": restored["manifest_sha256"],
        }


def parse_required_hash(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected PATH=SHA256")
    path, digest = value.split("=", 1)
    if not path or not digest:
        raise argparse.ArgumentTypeError("expected PATH=SHA256")
    return path, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILE_REQUIRED), default="pwa-shell")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--restore-check", action="store_true")
    parser.add_argument(
        "--require-sha256",
        action="append",
        default=[],
        type=parse_required_hash,
        metavar="PATH=SHA256",
        help="Require an exact SHA-256 for a critical candidate file; repeatable.",
    )
    args = parser.parse_args()

    root = args.candidate.resolve()
    required_sha256 = dict(args.require_sha256)
    errors = validate_tree(root, profile=args.profile, required_sha256=required_sha256)
    if errors:
        print(json.dumps({"status": "FAIL", "profile": args.profile, "errors": errors}, indent=2))
        return 2

    manifest = build_manifest(root, profile=args.profile)
    result = {
        "status": "PASS",
        "profile": args.profile,
        "manifest_sha256": manifest["manifest_sha256"],
        "file_count": len(manifest["files"]),
    }
    if required_sha256:
        result["required_sha256"] = dict(sorted(required_sha256.items()))
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.package:
        package_sha = write_deterministic_zip(root, args.package)
        result["package_sha256"] = package_sha
        if args.restore_check:
            result["restore"] = restore_and_verify(
                args.package,
                manifest,
                required_sha256=required_sha256,
            )
            if not result["restore"]["ok"]:
                print(json.dumps(result, indent=2, sort_keys=True))
                return 3
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
