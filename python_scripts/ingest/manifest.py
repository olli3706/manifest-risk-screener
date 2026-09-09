"""Parse a shipment-manifest workbook into Shipment records.

Manifests vary in layout, so columns are matched by header keywords rather than
fixed positions, and the header row is detected automatically (it isn't always
row 1). When the workbook has several sheets, the one that looks most like a
shipment log is chosen unless a sheet name is passed explicitly.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook

from models.manifest import Shipment

# Header keyword → Shipment field. First matching header (case-insensitive
# substring) wins, in the order listed here.
_FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ship_date": ("eta", "etd", "arrival", "date"),
    "shipper": ("shipper",),
    "consignee": ("cnee", "us consignee"),
    "ultimate_consignee": ("consignee full", "ultimate consignee", "consignee"),
    "origin": ("origin", "pol", "port of load"),
    "destination": ("dest", "pod", "port of discharge"),
    "hts": ("hts", "tariff", "hs code", "harmoniz"),
    "volume": ("teu", "quantity", "qty", "volume", "pieces", "cartons", "ctns"),
    "goods": ("goods", "commodity", "description"),
    "container": ("cntr", "container"),
    "hbl": ("hbl", "house bill"),
    "mbl": ("mbl", "master bill"),
}

# Words that mark a row as a header row (used to locate it).
_HEADER_HINTS = ("shipper", "consignee", "cnee", "origin", "dest", "eta", "hbl", "mbl", "hts")


def _text(v: object) -> str:
    return str(v).strip() if v is not None else ""


def _match_columns(header: tuple) -> dict[str, int]:
    """Map Shipment field -> column index using the header row's cell text."""
    lowered = [_text(c).lower() for c in header]
    mapping: dict[str, int] = {}
    used: set[int] = set()
    for field, keywords in _FIELD_KEYWORDS.items():
        for kw in keywords:
            idx = next((i for i, h in enumerate(lowered)
                        if kw in h and i not in used), None)
            if idx is not None:
                mapping[field] = idx
                used.add(idx)
                break
    return mapping


def _find_header_row(rows: list[tuple]) -> int:
    """Index of the row that best resembles a header (most header hints)."""
    best_i, best_score = 0, -1
    for i, row in enumerate(rows[:20]):
        lowered = " ".join(_text(c).lower() for c in row)
        score = sum(1 for hint in _HEADER_HINTS if hint in lowered)
        if score > best_score:
            best_i, best_score = i, score
    return best_i


def _score_sheet(rows: list[tuple]) -> int:
    if not rows:
        return 0
    hdr = rows[_find_header_row(rows)]
    lowered = " ".join(_text(c).lower() for c in hdr)
    hits = sum(1 for hint in _HEADER_HINTS if hint in lowered)
    return hits * 100 + min(len(rows), 500)  # header quality dominates, then size


def _to_date(v: object) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    text = _text(v)
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.split(".")[0], fmt).date()
        except ValueError:
            continue
    return None


def _to_volume(v: object) -> Optional[float]:
    text = _text(v).replace(",", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse(path: Path, sheet_name: Optional[str] = None) -> tuple[list[Shipment], str]:
    """Return (shipments, sheet_used) from a manifest workbook.

    Raises FileNotFoundError if the file is missing, or ValueError if no
    shipment-like rows can be found.
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    wb = load_workbook(path, data_only=True)

    if sheet_name:
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Sheet {sheet_name!r} not in {wb.sheetnames}")
        chosen = sheet_name
    else:
        chosen = max(
            wb.sheetnames,
            key=lambda n: _score_sheet(list(wb[n].iter_rows(values_only=True))),
        )

    rows = list(wb[chosen].iter_rows(values_only=True))
    if not rows:
        raise ValueError(f"Sheet {chosen!r} is empty")
    hdr_i = _find_header_row(rows)
    cols = _match_columns(rows[hdr_i])
    if "shipper" not in cols and "consignee" not in cols and "ultimate_consignee" not in cols:
        raise ValueError(
            f"Sheet {chosen!r} has no recognizable shipper/consignee columns; "
            f"pass --sheet or check the file layout."
        )

    shipments: list[Shipment] = []
    for r_i, row in enumerate(rows):
        if r_i <= hdr_i:
            continue

        def cell(field: str) -> object:
            idx = cols.get(field)
            return row[idx] if idx is not None and idx < len(row) else None

        shipper = _text(cell("shipper")) or None
        consignee = _text(cell("consignee")) or None
        ultimate = _text(cell("ultimate_consignee")) or None
        if not (shipper or consignee or ultimate):
            continue  # not a data row

        vol = _to_volume(cell("volume"))
        shipments.append(Shipment(
            row=r_i + 1,
            ship_date=_to_date(cell("ship_date")),
            shipper=shipper,
            consignee=consignee,
            ultimate_consignee=ultimate,
            origin=_text(cell("origin")) or None,
            destination=_text(cell("destination")) or None,
            hts=_text(cell("hts")) or None,
            volume=vol if vol is not None else 1.0,
            goods=_text(cell("goods")) or None,
            container=_text(cell("container")) or None,
            hbl=_text(cell("hbl")) or None,
            mbl=_text(cell("mbl")) or None,
        ))

    if not shipments:
        raise ValueError(f"No shipment rows found in sheet {chosen!r}")
    return shipments, chosen
