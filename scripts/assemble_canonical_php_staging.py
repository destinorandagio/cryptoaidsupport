#!/usr/bin/env python3
"""Assemble a disposable, release-clean canonical PHP staging tree.

This command is deliberately non-deploying. It copies a caller-supplied local
snapshot/export of the canonical ``public_html`` tree into a new disposable
staging directory, removes only the explicitly known release-dirty paths when
requested, validates the result with ``mvp_release_candidate``'s
``canonical-php`` profile, and can emit the deterministic manifest/package and
restore proof.

The source tree is always read-only. Production/canonical Drive content is never
modified by this script.
"""
from __future__ import annotations

import argparse
import json
import shutil
import stat
from pathlib import Path, PurePosixPath

from mvp_release_candidate import (
    build_manifest,
    restore_and_verify,
    sha256_file,
    validate_tree,
    write_deterministic_zip,
)

KNOWN_DRIVE_DIRTY_PATHS = {
    "LEGGIMI.txt",
    "_lib/schema.sql",
    "assets/icons/make-icons.py",
    "assets/partners/LEGGIMI-LOGHI.txt",
    "assets/partners/wallet-placeholder.png",
}


class AssemblyError(RuntimeError):
    pass


def _is_reparse_point(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def _source_entries(root: Path) -> list[Path]:
    return sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())


def _validate_source_identity(source: Path, staging: Path) -> None:
    if not source.is_dir():
        raise AssemblyError(f"source is not a directory: {source}")
    if source.is_symlink() or _is_reparse_point(source):
        raise AssemblyError(f"source root is symlink/reparse point: {source}")
    if staging.exists():
        raise AssemblyError(f"staging destination already exists: {staging}")

    source_real = source.resolve()
    staging_abs = staging.absolute()
    try:
        staging_abs.relative_to(source_real)
    except ValueError:
        pass
    else:
        raise AssemblyError("staging destination must not be inside source tree")

    parent = staging.parent
    if not parent.exists() or not parent.is_dir():
        raise AssemblyError(f"staging parent is not an existing directory: {parent}")
    if parent.is_symlink() or _is_reparse_point(parent):
        raise AssemblyError(f"staging parent is symlink/reparse point: {parent}")

    for path in _source_entries(source):
        rel = path.relative_to(source).as_posix()
        if path.is_symlink():
            raise AssemblyError(f"source contains symlink: {rel}")
        if _is_reparse_point(path):
            raise AssemblyError(f"source contains reparse point: {rel}")
        if not path.is_dir() and not path.is_file():
            raise AssemblyError(f"source contains non-regular entry: {rel}")


def _normalize_required_hashes(values: list[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_path, raw_digest in values:
        rel = PurePosixPath(raw_path)
        if rel.is_absolute() or ".." in rel.parts or rel.as_posix() in {"", "."}:
            raise AssemblyError(f"invalid required hash path: {raw_path}")
        digest = raw_digest.lower().strip()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise AssemblyError(f"invalid SHA-256 for {raw_path}")
        result[rel.as_posix()] = digest
    return result


def _verify_source_hashes(source: Path, required_sha256: dict[str, str]) -> None:
    for rel, expected in required_sha256.items():
        target = source / Path(*PurePosixPath(rel).parts)
        if not target.is_file() or target.is_symlink() or _is_reparse_point(target):
            raise AssemblyError(f"required source hash target missing/non-regular: {rel}")
        actual = sha256_file(target)
        if actual != expected:
            raise AssemblyError(
                f"required source SHA-256 mismatch: {rel} expected={expected} actual={actual}"
            )


def _copy_tree(
    source: Path,
    staging: Path,
    *,
    exclude_known_dirty: bool,
) -> tuple[list[str], int]:
    staging.mkdir(mode=0o700)
    excluded: list[str] = []
    copied_files = 0
    for path in _source_entries(source):
        rel = path.relative_to(source)
        rel_text = rel.as_posix()
        if exclude_known_dirty and rel_text in KNOWN_DRIVE_DIRTY_PATHS:
            excluded.append(rel_text)
            continue
        destination = staging / rel
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination, follow_symlinks=False)
        copied_files += 1
    return sorted(excluded), copied_files


def assemble(
    source: Path,
    staging: Path,
    *,
    required_sha256: dict[str, str],
    exclude_known_dirty: bool,
    manifest_path: Path | None = None,
    package_path: Path | None = None,
    restore_check: bool = False,
) -> dict:
    source = source.expanduser().absolute()
    staging = staging.expanduser().absolute()
    _validate_source_identity(source, staging)
    _verify_source_hashes(source, required_sha256)

    try:
        excluded, copied_files = _copy_tree(
            source,
            staging,
            exclude_known_dirty=exclude_known_dirty,
        )
        errors = validate_tree(
            staging,
            profile="canonical-php",
            required_sha256=required_sha256,
        )
        if errors:
            raise AssemblyError("; ".join(errors))

        manifest = build_manifest(staging, profile="canonical-php")
        result: dict = {
            "status": "PASS",
            "profile": "canonical-php",
            "source": str(source),
            "staging": str(staging),
            "source_read_only": True,
            "excluded_known_dirty": excluded,
            "copied_file_count": copied_files,
            "manifest_sha256": manifest["manifest_sha256"],
            "required_sha256": dict(sorted(required_sha256.items())),
        }
        if manifest_path is not None:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if package_path is not None:
            result["package_sha256"] = write_deterministic_zip(staging, package_path)
            if restore_check:
                result["restore"] = restore_and_verify(
                    package_path,
                    manifest,
                    required_sha256=required_sha256,
                )
                if not result["restore"]["ok"]:
                    raise AssemblyError("deterministic package restore verification failed")
        elif restore_check:
            raise AssemblyError("--restore-check requires --package")
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_required_hash(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected PATH=SHA256")
    path, digest = value.split("=", 1)
    if not path or not digest:
        raise argparse.ArgumentTypeError("expected PATH=SHA256")
    return path, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="read-only local snapshot/export of canonical public_html")
    parser.add_argument("staging", type=Path, help="new disposable staging directory")
    parser.add_argument(
        "--exclude-known-drive-dirty",
        action="store_true",
        help="exclude only the exact release-dirty paths recorded in the latest canonical Drive audit",
    )
    parser.add_argument(
        "--require-sha256",
        action="append",
        default=[],
        type=parse_required_hash,
        metavar="PATH=SHA256",
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--restore-check", action="store_true")
    args = parser.parse_args()

    try:
        required_sha256 = _normalize_required_hashes(args.require_sha256)
        result = assemble(
            args.source,
            args.staging,
            required_sha256=required_sha256,
            exclude_known_dirty=args.exclude_known_drive_dirty,
            manifest_path=args.manifest,
            package_path=args.package,
            restore_check=args.restore_check,
        )
    except AssemblyError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    except Exception as exc:  # fail closed, but keep the CLI diagnostic concise
        print(json.dumps({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, indent=2, sort_keys=True))
        return 3

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
