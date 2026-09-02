from pathlib import Path
import zipfile

import pytest

from twin.engine import TwinStatus
from twin.mirror_registry import MirrorRegistryIndex, file_sha256, iter_mirror_rows


def _row(twin_id: str, name: str, *, aliases: str = "", token: str = "", contract: str = "") -> dict[str, str]:
    return {
        "ID MIRROR81+": twin_id,
        "Nome canonico": name,
        "Alias / versioni": aliases,
        "Stato prudenziale": "STATUS_UNVERIFIED",
        "Categoria": "Test",
        "Chain": "",
        "Chain primaria": "",
        "Token": token,
        "Contratti / indirizzi": contract,
        "Sito ufficiale": "",
        "Copertura fonti": "fixture",
        "Attendibilità": "B",
        "Data acquisizione": "2026-08-20 00:00:00",
    }


def _inline_cell(ref: str, value: str) -> str:
    escaped = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>'


def _tiny_xlsx(path: Path) -> None:
    headers = [
        "ID MIRROR81+",
        "Nome canonico",
        "Alias / versioni",
        "Stato prudenziale",
        "Token",
        "Contratti / indirizzi",
        "Copertura fonti",
        "Attendibilità",
        "Data acquisizione",
    ]
    data = [
        headers,
        ["M81-1", "Alpha", "Alpha Protocol", "STATUS_UNVERIFIED", "ALP", "0x1111111111111111111111111111111111111111", "fixture", "A", "2026-08-20 00:00:00"],
        ["M81-2", "Beta", "Common", "STATUS_UNVERIFIED", "SAME", "", "fixture", "B", "2026-08-20 00:00:00"],
        ["M81-3", "Gamma", "Common", "STATUS_UNVERIFIED", "SAME", "", "fixture", "C", "2026-08-20 00:00:00"],
    ]
    rows = []
    for r_index, row in enumerate(data, start=1):
        cells = []
        for c_index, value in enumerate(row, start=1):
            letters = ""
            number = c_index
            while number:
                number, remainder = divmod(number - 1, 26)
                letters = chr(65 + remainder) + letters
            cells.append(_inline_cell(f"{letters}{r_index}", value))
        rows.append(f'<row r="{r_index}">{"".join(cells)}</row>')
    sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(rows)}</sheetData></worksheet>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Registro dApp" sheetId="1" r:id="rId1"/></sheets></workbook>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'''
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def test_registry_index_resolves_known_alias_ticker_and_contract_without_promotion():
    index = MirrorRegistryIndex.from_rows(
        [_row("M81-1", "Alpha", aliases="Alpha Protocol", token="ALP", contract="0x1111111111111111111111111111111111111111")],
        source_version="mirror81-test",
    )
    for query in ("Alpha", "Alpha Protocol", "ALP", "0x1111111111111111111111111111111111111111"):
        record = index.resolve_one(query)
        assert record is not None and record.twin_id == "M81-1"
        assert record.status == TwinStatus.KNOWN


def test_registry_index_rejects_duplicate_canonical_ids():
    with pytest.raises(ValueError, match="duplicate MIRROR/Twin id"):
        MirrorRegistryIndex.from_rows([_row("M81-1", "Alpha"), _row("M81-1", "Other")], source_version="mirror81-test")


def test_registry_index_never_first_picks_ambiguous_alias_or_ticker():
    index = MirrorRegistryIndex.from_rows(
        [_row("M81-2", "Beta", aliases="Common", token="SAME"), _row("M81-3", "Gamma", aliases="Common", token="SAME")],
        source_version="mirror81-test",
    )
    assert {record.twin_id for record in index.resolve("Common")} == {"M81-2", "M81-3"}
    assert {record.twin_id for record in index.resolve("SAME")} == {"M81-2", "M81-3"}
    with pytest.raises(ValueError, match="ambiguous MIRROR entity"):
        index.resolve_one("Common")


def test_unknown_stays_to_verify_and_can_continue_case():
    index = MirrorRegistryIndex.from_rows([_row("M81-1", "Alpha")], source_version="mirror81-test")
    result = index.search_or_candidate("Unknown Web3 Project")
    assert result == {
        "state": "TO_VERIFY",
        "candidate_status": "USER_SUBMITTED_TO_VERIFY",
        "query": "Unknown Web3 Project",
        "chain_id": None,
        "case_available": True,
        "promoted": False,
        "truth_label": "TO_VERIFY",
    }


def test_xlsx_loader_is_read_only_hash_pinned_and_reports_collision_stats(tmp_path: Path):
    workbook = tmp_path / "mirror.xlsx"
    _tiny_xlsx(workbook)
    source_hash = file_sha256(workbook)
    rows = list(iter_mirror_rows(workbook))
    assert len(rows) == 3
    assert rows[0]["Nome canonico"] == "Alpha"
    index = MirrorRegistryIndex.from_xlsx(workbook, source_version="mirror81-test", expected_sha256=source_hash)
    assert index.resolve_one("Alpha Protocol").twin_id == "M81-1"
    stats = index.stats()
    assert stats["records"] == 3
    assert stats["ambiguous_term_keys"] >= 2
    assert stats["source_sha256"] == source_hash
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        MirrorRegistryIndex.from_xlsx(workbook, source_version="mirror81-test", expected_sha256="0" * 64)
