"""Tests for the flexible manifest parser."""
import pytest
from openpyxl import Workbook

from ingest import manifest


def _build(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Shipments"
    ws.append(["Report title row — not a header"])
    ws.append(["Shipper from AMS", "CNEE from AMS", "Consignee Full Name",
               "ETA", "Origin", "Dest.", "HTS", "CNTR#"])
    ws.append(["SHENZHEN A CO", "VOYAGER TRADING", "INFINITY TRANS",
               "2025-10-23 16:30:00", "CNXAM", "USNYC", "6304.91", "ABCU1234567"])
    ws.append(["SHENZHEN B CO", "POLARIS TRADING", "INFINITY TRANS",
               "2025-11-08 19:30:00", "CNXAM", "USSAV", "9403.60", "ABCU7654321"])
    path = tmp_path / "manifest.xlsx"
    wb.save(path)
    return path


def test_parse_detects_header_and_columns(tmp_path):
    ships, sheet = manifest.parse(_build(tmp_path))
    assert sheet == "Shipments"
    assert len(ships) == 2
    s = ships[0]
    assert s.shipper == "SHENZHEN A CO"
    assert s.consignee == "VOYAGER TRADING"
    assert s.ultimate_consignee == "INFINITY TRANS"
    assert s.origin == "CNXAM" and s.destination == "USNYC"
    assert s.hts == "6304.91"
    assert s.route == "CNXAM -> USNYC"
    assert s.ship_date is not None and s.ship_date.year == 2025


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        manifest.parse(tmp_path / "nope.xlsx")


def test_unrecognized_layout_raises(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["foo", "bar", "baz"])
    ws.append([1, 2, 3])
    path = tmp_path / "bad.xlsx"
    wb.save(path)
    with pytest.raises(ValueError):
        manifest.parse(path)
