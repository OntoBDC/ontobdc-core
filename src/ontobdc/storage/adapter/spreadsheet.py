
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from tableschema import Schema
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile
from ontobdc.storage.core.port.spreadsheet import SpreadsheetPort, TableSchemaPort


def _column_letter(index_1_based: int) -> str:
    if index_1_based <= 0:
        raise ValueError("Column index must be >= 1")
    out = ""
    n = index_1_based
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(ord("A") + r) + out
    return out


@dataclass(frozen=True)
class _SheetCell:
    row: int
    col: int
    value: str
    style_id: int = 0


def _make_sheet_xml(
    *,
    cells: List[_SheetCell],
    header_row_height: int = 120,
    column_width: float = 14.0,
) -> str:
    max_row = 1
    max_col = 1
    for c in cells:
        max_row = max(max_row, c.row)
        max_col = max(max_col, c.col)
    dim = f"A1:{_column_letter(max_col)}{max_row}"

    cols_xml = "\n".join(
        f'<col min="{i}" max="{i}" width="{column_width:.2f}" customWidth="1"/>'
        for i in range(1, max_col + 1)
    )
    rows: Dict[int, List[_SheetCell]] = {}
    for c in cells:
        rows.setdefault(c.row, []).append(c)

    row_xml_parts: List[str] = []
    for r in sorted(rows.keys()):
        attrs: List[str] = [f'r="{r}"']
        if r == 1:
            attrs.append(f'ht="{header_row_height}"')
            attrs.append('customHeight="1"')
        cell_parts: List[str] = []
        for c in sorted(rows[r], key=lambda x: x.col):
            ref = f"{_column_letter(c.col)}{c.row}"
            v = escape(c.value)
            cell_parts.append(
                f'<c r="{ref}" t="inlineStr" s="{c.style_id}"><is><t>{v}</t></is></c>'
            )
        row_xml_parts.append(f"<row {' '.join(attrs)}>{''.join(cell_parts)}</row>")

    sheet_data_xml = "".join(row_xml_parts)

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dim}"/>'
        '<sheetViews>'
        '<sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        "</sheetView>"
        "</sheetViews>"
        '<sheetFormatPr defaultRowHeight="15"/>'
        f"<cols>{cols_xml}</cols>"
        f"<sheetData>{sheet_data_xml}</sheetData>"
        "</worksheet>"
    )


def _make_styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2">'
        "<font><sz val=\"11\"/><color theme=\"1\"/><name val=\"Calibri\"/><family val=\"2\"/></font>"
        "<font><b/><sz val=\"11\"/><color theme=\"1\"/><name val=\"Calibri\"/><family val=\"2\"/></font>"
        "</fonts>"
        '<fills count="2">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        "</fills>"
        '<borders count="1">'
        '<border><left/><right/><top/><bottom/><diagonal/></border>'
        "</borders>"
        '<cellStyleXfs count="1">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
        "</cellStyleXfs>"
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1">'
        '<alignment horizontal="center" vertical="center" textRotation="90" wrapText="1"/>'
        "</xf>"
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _write_xlsx(path: Path, *, sheet_name: str, cells: List[_SheetCell]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )

    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        f'<sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/>'
        "</sheets>"
        "</workbook>"
    )

    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )

    sheet_xml = _make_sheet_xml(cells=cells)
    styles_xml = _make_styles_xml()

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        z.writestr("xl/styles.xml", styles_xml)


class MicrosoftSpreadsheetAdapter(SpreadsheetPort):
    def __init__(self, target: Any, schema: TableSchemaPort) -> None:
        self._schema = schema
        self._resource_xlsx = type(self)._resolve_target(target)
        ok, data = type(self)._validate_and_load(self._resource_xlsx, schema)
        if not ok:
            raise ValueError(f"Invalid data for {target}")
        self._data = data

    @property
    def fields(self) -> List[Dict[str, Any]]:
        return self._schema.fields if self._schema else []

    @property
    def data(self) -> List[Dict[str, Any]]:
        return list(self._data or [])

    @classmethod
    def _col_index_from_ref(cls, ref: str) -> int:
        letters = "".join(ch for ch in (ref or "") if ch.isalpha())
        if not letters:
            return 0
        col_idx = 0
        for ch in letters:
            col_idx = col_idx * 26 + (ord(ch.upper()) - ord("A") + 1)
        return col_idx

    @classmethod
    def _cell_text(
        cls,
        cell: ET.Element,
        *,
        ns: Dict[str, str],
        shared_strings: List[str],
    ) -> str:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            text_parts = [t.text or "" for t in cell.findall(".//x:is/x:t", ns)]
            return "".join(text_parts).strip()
        if cell_type == "s":
            idx_el = cell.find("x:v", ns)
            try:
                idx = int((idx_el.text or "0").strip()) if idx_el is not None else 0
                if 0 <= idx < len(shared_strings):
                    return (shared_strings[idx] or "").strip()
            except (ValueError, TypeError):
                return ""
            return ""
        v = cell.find("x:v", ns)
        return ((v.text or "") if v is not None else "").strip()

    @classmethod
    def _read_sheet(cls, resource_xlsx: Path) -> Tuple[List[str] | None, List[Dict[str, str]] | None]:
        ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        required_entries = {
            "[Content_Types].xml",
            "_rels/.rels",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
            "xl/worksheets/sheet1.xml",
        }

        try:
            with ZipFile(resource_xlsx, "r") as z:
                names = set(z.namelist())
                if not required_entries.issubset(names):
                    return None, None

                shared_strings: List[str] = []
                if "xl/sharedStrings.xml" in names:
                    shared_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in shared_root.findall(".//x:si", ns):
                        text_parts = [t.text or "" for t in si.findall(".//x:t", ns)]
                        shared_strings.append("".join(text_parts))

                ws_root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
                rows = ws_root.findall(".//x:sheetData/x:row", ns)
                if not rows:
                    return [], []

                header_row = None
                for r in rows:
                    if (r.attrib.get("r") or "").strip() == "1":
                        header_row = r
                        break
                if header_row is None:
                    return [], []

                headers_by_col: Dict[int, str] = {}
                for c in header_row.findall("x:c", ns):
                    col_idx = cls._col_index_from_ref(c.attrib.get("r", ""))
                    if not col_idx:
                        continue
                    headers_by_col[col_idx] = cls._cell_text(c, ns=ns, shared_strings=shared_strings)

                if not headers_by_col:
                    return [], []
                headers = [headers_by_col[i] for i in sorted(headers_by_col.keys())]
                header_count = len(headers)

                data_rows: List[Dict[str, str]] = []
                for r in rows:
                    r_idx = (r.attrib.get("r") or "").strip()
                    if not r_idx or r_idx == "1":
                        continue

                    values_by_col: Dict[int, str] = {}
                    for c in r.findall("x:c", ns):
                        col_idx = cls._col_index_from_ref(c.attrib.get("r", ""))
                        if not col_idx or col_idx > header_count:
                            continue
                        values_by_col[col_idx] = cls._cell_text(c, ns=ns, shared_strings=shared_strings)

                    row_dict: Dict[str, str] = {}
                    any_value = False
                    for i, h in enumerate(headers, start=1):
                        v = values_by_col.get(i, "")
                        if v != "":
                            any_value = True
                        row_dict[h] = v

                    if any_value:
                        data_rows.append(row_dict)

                return headers, data_rows
        except (BadZipFile, ET.ParseError, OSError, KeyError):
            return None, None

    @classmethod
    def _resolve_target(cls, target: Any) -> Path:
        target_path = Path(target)
        if target_path.suffix.lower() == ".xlsx":
            return target_path
        if target_path.exists() and target_path.is_dir():
            return target_path / "resource.xlsx"
        if target_path.suffix:
            return target_path
        return target_path.with_suffix(".xlsx")

    @classmethod
    def _validate_and_load(cls, target: Any, schema: TableSchemaPort) -> Tuple[bool, List[Dict[str, Any]]]:
        fields: List[Dict[str, Any]] = schema.fields if schema else []
        expected_headers = [str(f.get("name", "")).strip() for f in fields]
        if not expected_headers:
            return False, []
        if len(set(expected_headers)) != len(expected_headers):
            return False, []

        xlsx_path = cls._resolve_target(target)
        if not xlsx_path.exists() or not xlsx_path.is_file():
            return False, []

        headers, rows = cls._read_sheet(xlsx_path)
        if headers is None or rows is None:
            return False, []
        if headers != expected_headers:
            return False, []

        schema_obj = Schema({"fields": fields})
        casted_rows: List[Dict[str, Any]] = []
        for r in rows:
            values = [(r.get(h) or "") for h in expected_headers]
            try:
                casted = schema_obj.cast_row(values)
            except Exception:
                return False, []
            casted_rows.append(dict(zip(expected_headers, casted)))
        return True, casted_rows

    @classmethod
    def validate(cls, target: Any, schema: TableSchemaPort) -> bool:
        ok, _ = cls._validate_and_load(target, schema)
        return ok

    @classmethod
    def create(cls, target: Any, schema: TableSchemaPort) -> Path:
        xlsx_path = cls._resolve_target(target)

        fields: List[Dict[str, Any]] = schema.fields if schema else []
        cells: List[_SheetCell] = []
        for i, f in enumerate(fields, start=1):
            cells.append(_SheetCell(row=1, col=i, value=str(f.get("name") or ""), style_id=1))

        if not cells:
            cells = [_SheetCell(row=1, col=1, value="id", style_id=1)]

        _write_xlsx(xlsx_path, sheet_name="resource", cells=cells)
        return xlsx_path
