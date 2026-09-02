from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import posixpath
import re
from typing import Any, Iterable, Iterator, Mapping
import xml.etree.ElementTree as ET
import zipfile

from .engine import TwinRecord, TwinStatus, normalize_address, normalize_name
from .mirror_adapter import adapt_mirror_row

MIRROR_REGISTRY_INDEX_VERSION = "1.0.0"
DEFAULT_SHEET_NAME = "Registro dApp"
_DATE_HEADERS = {"Data acquisizione", "Ultimo aggiornamento fonte", "Prima indicizzazione"}
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _column_index(reference: str) -> int:
    match = re.match(r"([A-Z]+)", reference.upper())
    if not match:
        raise ValueError(f"invalid cell reference: {reference!r}")
    value = 0
    for char in match.group(1):
        value = value * 26 + ord(char) - 64
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(name))
    return ["".join(node.text or "" for node in item.iter(f"{{{_MAIN_NS}}}t")) for item in root]


def _workbook_date1904(archive: zipfile.ZipFile) -> bool:
    root = ET.fromstring(archive.read("xl/workbook.xml"))
    props = root.find(f"{{{_MAIN_NS}}}workbookPr")
    return bool(props is not None and props.attrib.get("date1904") in {"1", "true", "TRUE"})


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relation_id = None
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            relation_id = sheet.attrib.get(f"{{{_REL_NS}}}id")
            break
    if not relation_id:
        raise ValueError(f"missing XLSX sheet: {sheet_name}")
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target = None
    for rel in rels.findall(f"{{{_PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Id") == relation_id:
            target = rel.attrib.get("Target")
            break
    if not target:
        raise ValueError(f"missing XLSX relationship for sheet: {sheet_name}")
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("xl", target))


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{_MAIN_NS}}}t"))
    value_node = cell.find(f"{{{_MAIN_NS}}}v")
    raw = "" if value_node is None or value_node.text is None else value_node.text
    if cell_type == "s" and raw:
        index = int(raw)
        if index < 0 or index >= len(shared):
            raise ValueError("invalid shared string index")
        return shared[index]
    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def _excel_date(value: str, *, date1904: bool) -> str:
    try:
        serial = float(value)
    except (TypeError, ValueError):
        return value
    base = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
    rendered = base + timedelta(days=serial)
    return rendered.strftime("%Y-%m-%d %H:%M:%S")


def iter_mirror_rows(path: str | Path, *, sheet_name: str = DEFAULT_SHEET_NAME) -> Iterator[dict[str, str]]:
    """Stream the canonical MIRROR XLSX without adding a spreadsheet runtime dependency.

    The workbook remains the authority. This reader creates no database or copied registry.
    """
    with zipfile.ZipFile(Path(path), "r") as archive:
        shared = _shared_strings(archive)
        date1904 = _workbook_date1904(archive)
        sheet_path = _sheet_path(archive, sheet_name)
        headers: list[str] | None = None
        with archive.open(sheet_path) as stream:
            for event, element in ET.iterparse(stream, events=("end",)):
                if element.tag != f"{{{_MAIN_NS}}}row":
                    continue
                values: dict[int, str] = {}
                for cell in element.findall(f"{{{_MAIN_NS}}}c"):
                    reference = cell.attrib.get("r", "")
                    if not reference:
                        continue
                    values[_column_index(reference)] = _cell_value(cell, shared).strip()
                if headers is None:
                    width = max(values, default=-1) + 1
                    headers = [values.get(index, "").strip() for index in range(width)]
                    required = {"ID MIRROR81+", "Nome canonico"}
                    if not required.issubset(headers):
                        raise ValueError("MIRROR sheet missing canonical ID/name columns")
                else:
                    row: dict[str, str] = {}
                    for index, header in enumerate(headers):
                        if not header:
                            continue
                        value = values.get(index, "")
                        if header in _DATE_HEADERS and value:
                            value = _excel_date(value, date1904=date1904)
                        row[header] = value
                    if row.get("ID MIRROR81+") or row.get("Nome canonico"):
                        yield row
                element.clear()


def _status_order(status: TwinStatus) -> int:
    return {
        TwinStatus.VERIFIED: 0,
        TwinStatus.SUPPORTED: 1,
        TwinStatus.KNOWN: 2,
        TwinStatus.TO_VERIFY: 3,
        TwinStatus.UNKNOWN: 4,
    }[status]


class MirrorRegistryIndex:
    """Exact-key read index over canonical MIRROR rows.

    Colliding aliases/tickers/contracts intentionally remain ambiguous. The index never
    chooses a first record, never changes SIC-ID/Twin authority, and never promotes a
    MIRROR prudential state to VERIFIED.
    """

    def __init__(self, records: Iterable[TwinRecord], *, source_version: str, source_sha256: str | None = None) -> None:
        if not source_version.strip():
            raise ValueError("source_version is required")
        self.source_version = source_version
        self.source_sha256 = source_sha256
        self._records: dict[str, TwinRecord] = {}
        self._terms: dict[str, set[str]] = defaultdict(set)
        self._contracts: dict[str, set[str]] = defaultdict(set)
        for record in records:
            self.add(record)

    def add(self, record: TwinRecord) -> None:
        if record.twin_id in self._records:
            raise ValueError(f"duplicate MIRROR/Twin id: {record.twin_id}")
        self._records[record.twin_id] = record
        for key in record.searchable_names():
            if key:
                self._terms[key].add(record.twin_id)
        for contract in record.contracts:
            self._contracts[normalize_address(contract)].add(record.twin_id)

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping[str, Any]], *, source_version: str) -> "MirrorRegistryIndex":
        return cls((adapt_mirror_row(row, source_version=source_version) for row in rows), source_version=source_version)

    @classmethod
    def from_xlsx(
        cls,
        path: str | Path,
        *,
        source_version: str,
        expected_sha256: str | None = None,
        sheet_name: str = DEFAULT_SHEET_NAME,
    ) -> "MirrorRegistryIndex":
        actual_sha = file_sha256(path)
        if expected_sha256 and actual_sha.lower() != expected_sha256.lower():
            raise ValueError("MIRROR source SHA256 mismatch")
        records = (adapt_mirror_row(row, source_version=source_version) for row in iter_mirror_rows(path, sheet_name=sheet_name))
        return cls(records, source_version=source_version, source_sha256=actual_sha)

    def get(self, twin_id: str) -> TwinRecord | None:
        return self._records.get(twin_id)

    def resolve(self, query: str, *, chain_id: int | None = None) -> list[TwinRecord]:
        raw = query.strip()
        ids: set[str]
        try:
            address = normalize_address(raw)
        except ValueError:
            ids = set(self._terms.get(normalize_name(raw), ()))
        else:
            ids = set(self._contracts.get(address, ()))
        records = [self._records[twin_id] for twin_id in ids]
        if chain_id is not None:
            records = [record for record in records if record.chain_id in (None, chain_id)]
        return sorted(records, key=lambda record: (_status_order(record.status), record.name.casefold(), record.twin_id))

    def resolve_one(self, query: str, *, chain_id: int | None = None) -> TwinRecord | None:
        matches = self.resolve(query, chain_id=chain_id)
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError("ambiguous MIRROR entity; chain/contract disambiguation required")
        return matches[0]

    def search_or_candidate(self, query: str, *, chain_id: int | None = None) -> dict[str, Any]:
        matches = self.resolve(query, chain_id=chain_id)
        if matches:
            return {"state": "MATCH", "results": matches}
        return {
            "state": TwinStatus.TO_VERIFY.value,
            "candidate_status": "USER_SUBMITTED_TO_VERIFY",
            "query": query,
            "chain_id": chain_id,
            "case_available": True,
            "promoted": False,
            "truth_label": "TO_VERIFY",
        }

    def stats(self) -> dict[str, int | str | None]:
        return {
            "index_version": MIRROR_REGISTRY_INDEX_VERSION,
            "source_version": self.source_version,
            "source_sha256": self.source_sha256,
            "records": len(self._records),
            "term_keys": len(self._terms),
            "ambiguous_term_keys": sum(1 for ids in self._terms.values() if len(ids) > 1),
            "contract_keys": len(self._contracts),
            "ambiguous_contract_keys": sum(1 for ids in self._contracts.values() if len(ids) > 1),
        }


__all__ = [
    "DEFAULT_SHEET_NAME",
    "MIRROR_REGISTRY_INDEX_VERSION",
    "MirrorRegistryIndex",
    "file_sha256",
    "iter_mirror_rows",
]
