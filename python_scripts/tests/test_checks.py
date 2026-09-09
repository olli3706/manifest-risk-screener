"""Tests for the deterministic anomaly checks and baseline split."""
from datetime import date

from analyze import baseline as bl
from analyze import checks as chk
from models.manifest import Shipment


def _s(row, d=None, shipper=None, origin=None, dest=None, hts=None, volume=1.0, cnee=None):
    return Shipment(row=row, ship_date=d, shipper=shipper, origin=origin,
                    destination=dest, hts=hts, volume=volume, consignee=cnee)


def test_split_recent_vs_baseline():
    ships = [
        _s(1, date(2025, 1, 1)), _s(2, date(2025, 5, 1)),
        _s(3, date(2025, 6, 25)), _s(4, date(2025, 6, 30)),
    ]
    base, recent = bl.split(ships, recent_days=30)
    assert {s.row for s in recent} == {3, 4}   # within 30 days of 2025-06-30
    assert {s.row for s in base} == {1, 2}


def test_new_shipper_flags():
    base = [_s(1, shipper="ALPHA CO"), _s(2, shipper="BETA CO")]
    recent = [_s(3, shipper="ALPHA CO"), _s(4, shipper="GAMMA CO")]
    r = chk.check_shippers(base, recent)
    assert r.status == "flag"
    assert r.items == ["GAMMA CO"]


def test_no_new_shipper_ok():
    base = [_s(1, shipper="ALPHA CO")]
    recent = [_s(2, shipper="ALPHA CO")]
    assert chk.check_shippers(base, recent).status == "ok"


def test_new_route_flags():
    base = [_s(1, origin="CNXAM", dest="USNYC")]
    recent = [_s(2, origin="CNXAM", dest="USLAX")]
    r = chk.check_routes(base, recent)
    assert r.status == "flag"
    assert r.items == ["CNXAM -> USLAX"]


def test_hts_skipped_when_absent():
    base = [_s(1, shipper="A")]
    recent = [_s(2, shipper="A")]
    assert chk.check_hts(base, recent).status == "skipped"


def test_hts_new_code_flags():
    base = [_s(1, hts="6304.91")]
    recent = [_s(2, hts="9403.60")]
    assert chk.check_hts(base, recent).status == "flag"


def test_volume_spike_flags():
    # Baseline: ~1/week over ~10 weeks. Recent: 8 shipments in one week.
    base = [_s(i, date(2025, 1, 1) + __import__("datetime").timedelta(weeks=i))
            for i in range(10)]
    recent = [_s(100 + i, date(2025, 6, 2)) for i in range(8)]
    r = chk.check_volume(base, recent, spike_factor=2.0)
    assert r.status == "flag"


def test_volume_ok_when_steady():
    import datetime as _dt
    base = [_s(i, date(2025, 1, 1) + _dt.timedelta(weeks=i)) for i in range(10)]
    recent = [_s(100, date(2025, 3, 12) + _dt.timedelta(days=3))]
    r = chk.check_volume(base, recent, spike_factor=2.0)
    assert r.status == "ok"


def test_detect_customer_uses_dominant_consignee():
    ships = [_s(1, cnee="ACME"), _s(2, cnee="ACME"), _s(3, cnee="OTHER")]
    assert bl.detect_customer(ships) == "ACME"
