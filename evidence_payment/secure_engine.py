"""CHAT02 private Evidence storage containment for the 48H MVP.

Case identifiers are logical identifiers, never filesystem paths.  Storage
rejects traversal, symlink/junction roots, and symlinked path components before
Evidence bytes or rows can escape the configured private root.  On POSIX the
write path is anchored with directory file descriptors plus O_NOFOLLOW so a
path-swap race cannot redirect quarantine/final bytes outside the root.
"""
from __future__ import annotations

import errno
import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any, Iterable

from .engine import EvidencePaymentError, _id, _now
from .mvp_engine import EvidencePaymentEngine as _MvpEvidencePaymentEngine

EVIDENCE_STORAGE_GUARD_VERSION = "1.2"
_CASE_STORAGE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_case_storage_key(case_id: Any) -> str:
    if not isinstance(case_id, str) or not _CASE_STORAGE_KEY.fullmatch(case_id):
        raise EvidencePaymentError(
            "INVALID_CASE_STORAGE_KEY",
            "Case identifier is not a valid private Evidence storage key",
        )
    if case_id in {".", ".."}:
        raise EvidencePaymentError(
            "INVALID_CASE_STORAGE_KEY",
            "Case identifier cannot be a filesystem traversal segment",
        )
    return case_id


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        st = os.lstat(path)
        return stat.S_ISLNK(st.st_mode)
    except FileNotFoundError:
        return False


def _assert_no_existing_link_components(path: str | Path) -> Path:
    """Reject an existing symlink/junction anywhere in an unresolved path."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for part in parts:
        current = current / part
        if os.path.lexists(current) and _is_link_or_reparse(current):
            raise EvidencePaymentError(
                "EVIDENCE_SYMLINK_FORBIDDEN",
                "Private Evidence storage cannot traverse symlink/reparse components",
            )
    return absolute


class EvidencePaymentEngine(_MvpEvidencePaymentEngine):
    """Canonical CHAT02 engine with fail-closed private Evidence containment."""

    def __init__(self, db_path, private_root):
        # The base engine resolves the path, so inspect the caller-supplied path
        # first; otherwise a symlink root would be silently followed.
        raw_root = _assert_no_existing_link_components(private_root)
        super().__init__(db_path, raw_root)
        _assert_no_existing_link_components(self.private_root)
        if not self.private_root.is_dir():
            raise EvidencePaymentError(
                "EVIDENCE_ROOT_INVALID", "Private Evidence root must be a directory"
            )

    @staticmethod
    def _nofollow_flags(*, directory: bool = False) -> int:
        flags = os.O_RDONLY
        if directory:
            flags |= getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        return flags

    @staticmethod
    def _raise_storage_link(exc: OSError) -> None:
        if exc.errno in {
            errno.ELOOP,
            errno.ENOTDIR,
            getattr(errno, "EMLINK", -1),
        }:
            raise EvidencePaymentError(
                "EVIDENCE_SYMLINK_FORBIDDEN",
                "Private Evidence path contains a symlink/reparse component",
            ) from exc
        raise EvidencePaymentError(
            "EVIDENCE_STORAGE_ERROR", "Private Evidence storage operation failed"
        ) from exc

    def _open_child_dir(self, parent_fd: int, name: str) -> int:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError as exc:
            self._raise_storage_link(exc)
        try:
            fd = os.open(
                name,
                self._nofollow_flags(directory=True),
                dir_fd=parent_fd,
            )
        except OSError as exc:
            self._raise_storage_link(exc)
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            os.close(fd)
            raise EvidencePaymentError(
                "EVIDENCE_STORAGE_ERROR", "Private Evidence component is not a directory"
            )
        return fd

    def _safe_write_posix(
        self, *, case_id: str, evidence_id: str, version: int, content: bytes
    ) -> tuple[Path, int, str]:
        """Write quarantine/final bytes beneath root using no-follow dirfds.

        Returns (relative path, open evidence-directory fd, final filename).  The
        caller keeps the fd through DB commit so it can unlink the exact file on
        rollback without re-resolving an attacker-controlled pathname.
        """
        root_fd = case_fd = evidence_fd = None
        tmp_name = f"v{version}.quarantine"
        final_name = f"v{version}.bin"
        try:
            root_fd = os.open(
                self.private_root,
                self._nofollow_flags(directory=True),
            )
            if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
                raise EvidencePaymentError(
                    "EVIDENCE_ROOT_INVALID", "Private Evidence root must be a directory"
                )
            case_fd = self._open_child_dir(root_fd, case_id)
            evidence_fd = self._open_child_dir(case_fd, evidence_id)

            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_NOFOLLOW", 0)
            try:
                file_fd = os.open(tmp_name, flags, 0o600, dir_fd=evidence_fd)
            except OSError as exc:
                self._raise_storage_link(exc)
            try:
                view = memoryview(content)
                written = 0
                while written < len(view):
                    n = os.write(file_fd, view[written:])
                    if n <= 0:
                        raise EvidencePaymentError(
                            "EVIDENCE_STORAGE_ERROR", "Short private Evidence write"
                        )
                    written += n
                os.fsync(file_fd)
            finally:
                os.close(file_fd)

            try:
                os.replace(
                    tmp_name,
                    final_name,
                    src_dir_fd=evidence_fd,
                    dst_dir_fd=evidence_fd,
                )
            except OSError as exc:
                try:
                    os.unlink(tmp_name, dir_fd=evidence_fd)
                except OSError:
                    pass
                self._raise_storage_link(exc)

            rel = Path(case_id) / evidence_id / final_name
            return rel, evidence_fd, final_name
        except OSError as exc:
            self._raise_storage_link(exc)
        finally:
            if case_fd is not None:
                os.close(case_fd)
            if root_fd is not None:
                os.close(root_fd)
            # evidence_fd intentionally remains open only on successful return.

    def _safe_write_fallback(
        self, *, case_id: str, evidence_id: str, version: int, content: bytes
    ) -> tuple[Path, None, Path]:
        """Fail-closed fallback for platforms without POSIX dir_fd support.

        It rejects link/reparse components immediately before and after each
        directory creation and verifies resolved containment before an exclusive
        quarantine write.  Production should prefer the POSIX no-follow path.
        """
        case_dir = self.private_root / case_id
        evidence_dir = case_dir / evidence_id
        for component in (case_dir, evidence_dir):
            if os.path.lexists(component) and _is_link_or_reparse(component):
                raise EvidencePaymentError(
                    "EVIDENCE_SYMLINK_FORBIDDEN",
                    "Private Evidence path contains a symlink/reparse component",
                )
            component.mkdir(mode=0o700, exist_ok=True)
            if _is_link_or_reparse(component):
                raise EvidencePaymentError(
                    "EVIDENCE_SYMLINK_FORBIDDEN",
                    "Private Evidence path contains a symlink/reparse component",
                )
            try:
                component.resolve(strict=True).relative_to(self.private_root)
            except (OSError, ValueError) as exc:
                raise EvidencePaymentError(
                    "EVIDENCE_STORAGE_ESCAPE", "Private Evidence path escaped its root"
                ) from exc

        tmp = evidence_dir / f"v{version}.quarantine"
        final = evidence_dir / f"v{version}.bin"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(tmp, flags, 0o600)
        except OSError as exc:
            self._raise_storage_link(exc)
        try:
            view = memoryview(content)
            written = 0
            while written < len(view):
                n = os.write(fd, view[written:])
                if n <= 0:
                    raise EvidencePaymentError(
                        "EVIDENCE_STORAGE_ERROR", "Short private Evidence write"
                    )
                written += n
                # Re-check parent after each write on fallback platforms.
                if _is_link_or_reparse(evidence_dir):
                    raise EvidencePaymentError(
                        "EVIDENCE_SYMLINK_FORBIDDEN",
                        "Private Evidence path changed to a link during write",
                    )
            os.fsync(fd)
        finally:
            os.close(fd)
        if _is_link_or_reparse(evidence_dir):
            try:
                tmp.unlink(missing_ok=True)
            finally:
                raise EvidencePaymentError(
                    "EVIDENCE_SYMLINK_FORBIDDEN",
                    "Private Evidence path changed to a link during write",
                )
        os.replace(tmp, final)
        try:
            final.resolve(strict=True).relative_to(self.private_root)
        except (OSError, ValueError) as exc:
            final.unlink(missing_ok=True)
            raise EvidencePaymentError(
                "EVIDENCE_STORAGE_ESCAPE", "Private Evidence file escaped its root"
            ) from exc
        return Path(case_id) / evidence_id / final.name, None, final

    def _safe_write(
        self, *, case_id: str, evidence_id: str, version: int, content: bytes
    ):
        supports_dir_fd = (
            os.open in getattr(os, "supports_dir_fd", set())
            and os.mkdir in getattr(os, "supports_dir_fd", set())
            and os.unlink in getattr(os, "supports_dir_fd", set())
            and os.replace in getattr(os, "supports_dir_fd", set())
            and bool(getattr(os, "O_NOFOLLOW", 0))
        )
        if supports_dir_fd:
            return self._safe_write_posix(
                case_id=case_id, evidence_id=evidence_id, version=version, content=content
            )
        return self._safe_write_fallback(
            case_id=case_id, evidence_id=evidence_id, version=version, content=content
        )

    @staticmethod
    def _cleanup_written(handle, final_ref) -> None:
        try:
            if handle is not None:
                os.unlink(final_ref, dir_fd=handle)
            else:
                Path(final_ref).unlink(missing_ok=True)
        except OSError:
            # DB rollback remains authoritative; a cleanup failure is surfaced by
            # subsequent filesystem audit and never converted into AVAILABLE.
            pass

    def store_evidence(
        self,
        *,
        case_id: str,
        content: bytes,
        original_name: str,
        mime_declared: str,
        mime_detected: str,
        uploader: str,
        consent_id: str,
        authorization: str,
        max_bytes: int = 25_000_000,
        allowed_mimes: Iterable[str] = ("application/pdf", "image/png", "image/jpeg"),
        parent_evidence_id: str | None = None,
        reason: str = "UPLOAD",
    ):
        safe_case_id = validate_case_storage_key(case_id)
        if not authorization or authorization == "DENIED":
            raise EvidencePaymentError("UNAUTHORIZED", "Evidence authorization required")
        if not consent_id:
            raise EvidencePaymentError("CONSENT_REQUIRED", "Consent binding required")
        if len(content) > max_bytes:
            raise EvidencePaymentError("OVERSIZED", "Evidence exceeds size limit")
        allowed = set(allowed_mimes)
        if (
            mime_declared not in allowed
            or mime_detected not in allowed
            or mime_declared != mime_detected
        ):
            raise EvidencePaymentError("MIME_REJECTED", "MIME validation failed")

        # Revalidate the root immediately before opening it.  A root path that
        # was replaced by a symlink after construction is rejected.
        _assert_no_existing_link_components(self.private_root)
        digest = hashlib.sha256(content).hexdigest()
        evidence_id = _id("ev")
        write_handle = final_ref = None
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                version = 1
                if parent_evidence_id:
                    parent = c.execute(
                        "SELECT * FROM evidence_records WHERE evidence_id=?",
                        (parent_evidence_id,),
                    ).fetchone()
                    if not parent or parent["case_id"] != safe_case_id:
                        raise EvidencePaymentError("BAD_LINEAGE", "Invalid evidence parent")
                    version = int(parent["version"]) + 1

                rel, write_handle, final_ref = self._safe_write(
                    case_id=safe_case_id,
                    evidence_id=evidence_id,
                    version=version,
                    content=content,
                )
                c.execute(
                    "INSERT INTO evidence_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        evidence_id,
                        safe_case_id,
                        version,
                        parent_evidence_id,
                        "AVAILABLE",
                        original_name,
                        mime_declared,
                        mime_detected,
                        len(content),
                        digest,
                        str(rel),
                        uploader,
                        consent_id,
                        authorization,
                        reason,
                        _now(),
                        None,
                    ),
                )
                if parent_evidence_id:
                    c.execute(
                        "UPDATE evidence_records SET status='SUPERSEDED', superseded_at=? WHERE evidence_id=?",
                        (_now(), parent_evidence_id),
                    )
                c.execute("COMMIT")
            except Exception:
                if c.in_transaction:
                    c.execute("ROLLBACK")
                if final_ref is not None:
                    self._cleanup_written(write_handle, final_ref)
                raise
            finally:
                if write_handle is not None:
                    os.close(write_handle)

        return {
            "evidence_id": evidence_id,
            "case_id": safe_case_id,
            "version": version,
            "sha256": digest,
            "status": "AVAILABLE",
        }
