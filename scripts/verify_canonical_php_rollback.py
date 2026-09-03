#!/usr/bin/env python3
"""Prove canonical PHP backup -> candidate restore -> rollback in a disposable tree.

This verifier never deploys and never mutates either caller-supplied source tree.
It creates an exact raw backup of the current canonical snapshot, simulates a
candidate cutover in a new local work directory, validates the candidate with
the canonical-php release profile, then restores the raw backup and proves that
the rollback is byte-for-byte identical to the original snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

from mvp_release_candidate import ZIP_EPOCH, build_manifest, sha256_file, validate_tree


class RollbackError(RuntimeError):
    pass


def _is_reparse_point(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def _entries(root: Path) -> list[Path]:
    return sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())


def _validate_read_only_tree(root: Path, label: str) -> None:
    if not root.is_dir():
        raise RollbackError(f"{label} is not a directory: {root}")
    if root.is_symlink() or _is_reparse_point(root):
        raise RollbackError(f"{label} root is symlink/reparse point")
    for path in _entries(root):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise RollbackError(f"{label} contains symlink: {rel}")
        if _is_reparse_point(path):
            raise RollbackError(f"{label} contains reparse point: {rel}")
        if not path.is_dir() and not path.is_file():
            raise RollbackError(f"{label} contains non-regular entry: {rel}")


def _normalize_hashes(values: list[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_path, raw_digest in values:
        rel = PurePosixPath(raw_path)
        if rel.is_absolute() or ".." in rel.parts or rel.as_posix() in {"", "."}:
            raise RollbackError(f"invalid required hash path: {raw_path}")
        digest = raw_digest.lower().strip()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise RollbackError(f"invalid SHA-256 for {raw_path}")
        result[rel.as_posix()] = digest
    return result


def _verify_hashes(root: Path, required: dict[str, str], label: str) -> None:
    for rel, expected in required.items():
        target = root / Path(*PurePosixPath(rel).parts)
        if not target.is_file() or target.is_symlink() or _is_reparse_point(target):
            raise RollbackError(f"{label} required hash target missing/non-regular: {rel}")
        actual = sha256_file(target)
        if actual != expected:
            raise RollbackError(
                f"{label} required SHA-256 mismatch: {rel} expected={expected} actual={actual}"
            )


def _raw_manifest(root: Path) -> dict:
    files: list[dict[str, object]] = []
    for path in _entries(root):
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    payload = {"schema_version": "1.0", "profile": "raw-rollback", "files": files}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def _write_raw_backup(root: Path, package: Path) -> str:
    package.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in _entries(root):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(rel, ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return sha256_file(package)


def _safe_extract(package: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    root_real = destination.resolve()
    with zipfile.ZipFile(package, "r") as zf:
        for info in zf.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or member.as_posix() in {"", "."}:
                raise RollbackError(f"unsafe backup member: {info.filename}")
            target = (destination / Path(*member.parts)).resolve()
            if target != root_real and root_real not in target.parents:
                raise RollbackError(f"unsafe backup member: {info.filename}")
        zf.extractall(destination)


def _copy_regular_tree(source: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    for path in _entries(source):
        rel = path.relative_to(source)
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target, follow_symlinks=False)


def verify_transaction(
    current_snapshot: Path,
    candidate: Path,
    workdir: Path,
    *,
    current_required_sha256: dict[str, str],
    candidate_required_sha256: dict[str, str],
) -> dict:
    current_snapshot = current_snapshot.expanduser().absolute()
    candidate = candidate.expanduser().absolute()
    workdir = workdir.expanduser().absolute()

    _validate_read_only_tree(current_snapshot, "current snapshot")
    _validate_read_only_tree(candidate, "candidate")
    if workdir.exists():
        raise RollbackError(f"workdir already exists: {workdir}")
    for source in (current_snapshot.resolve(), candidate.resolve()):
        try:
            workdir.relative_to(source)
        except ValueError:
            pass
        else:
            raise RollbackError("workdir must not be inside a source tree")
    if not workdir.parent.is_dir() or workdir.parent.is_symlink() or _is_reparse_point(workdir.parent):
        raise RollbackError("workdir parent must be an existing regular directory")

    _verify_hashes(current_snapshot, current_required_sha256, "current snapshot")
    _verify_hashes(candidate, candidate_required_sha256, "candidate")
    candidate_errors = validate_tree(
        candidate,
        profile="canonical-php",
        required_sha256=candidate_required_sha256,
    )
    if candidate_errors:
        raise RollbackError("candidate invalid: " + "; ".join(candidate_errors))

    current_before = _raw_manifest(current_snapshot)
    candidate_manifest = build_manifest(candidate, profile="canonical-php")
    backup = workdir / "backup-current.zip"
    active = workdir / "active-public-html"

    try:
        workdir.mkdir(mode=0o700)
        backup_sha = _write_raw_backup(current_snapshot, backup)

        # Simulated candidate cutover, confined to the disposable workdir.
        _copy_regular_tree(candidate, active)
        active_errors = validate_tree(
            active,
            profile="canonical-php",
            required_sha256=candidate_required_sha256,
        )
        if active_errors:
            raise RollbackError("candidate restore invalid: " + "; ".join(active_errors))
        active_manifest = build_manifest(active, profile="canonical-php")
        if active_manifest["manifest_sha256"] != candidate_manifest["manifest_sha256"]:
            raise RollbackError("candidate restore manifest mismatch")

        # Simulated rollback from the exact raw pre-cutover backup.
        shutil.rmtree(active)
        _safe_extract(backup, active)
        _validate_read_only_tree(active, "restored rollback")
        _verify_hashes(active, current_required_sha256, "restored rollback")
        restored = _raw_manifest(active)
        if restored["manifest_sha256"] != current_before["manifest_sha256"]:
            raise RollbackError("rollback manifest mismatch")

        # Prove caller-owned sources were not modified by the simulation.
        current_after = _raw_manifest(current_snapshot)
        candidate_after = build_manifest(candidate, profile="canonical-php")
        if current_after["manifest_sha256"] != current_before["manifest_sha256"]:
            raise RollbackError("current snapshot changed during verification")
        if candidate_after["manifest_sha256"] != candidate_manifest["manifest_sha256"]:
            raise RollbackError("candidate changed during verification")

        return {
            "status": "PASS",
            "source_read_only": True,
            "backup_sha256": backup_sha,
            "current_manifest_sha256": current_before["manifest_sha256"],
            "candidate_manifest_sha256": candidate_manifest["manifest_sha256"],
            "candidate_restore_ok": True,
            "rollback_manifest_sha256": restored["manifest_sha256"],
            "rollback_ok": True,
            "current_required_sha256": dict(sorted(current_required_sha256.items())),
            "candidate_required_sha256": dict(sorted(candidate_required_sha256.items())),
        }
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
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
    parser.add_argument("current_snapshot", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("--require-current-sha256", action="append", default=[], type=parse_required_hash)
    parser.add_argument("--require-candidate-sha256", action="append", default=[], type=parse_required_hash)
    args = parser.parse_args()

    try:
        result = verify_transaction(
            args.current_snapshot,
            args.candidate,
            args.workdir,
            current_required_sha256=_normalize_hashes(args.require_current_sha256),
            candidate_required_sha256=_normalize_hashes(args.require_candidate_sha256),
        )
    except RollbackError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, indent=2, sort_keys=True))
        return 3

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
