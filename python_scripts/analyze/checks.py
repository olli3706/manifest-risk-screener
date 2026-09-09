"""Deterministic anomaly checks: new shippers / routes / HTS + volume spikes.

Each check compares the recent window against the customer's historical baseline
and returns a CheckResult with status "flag", "ok", or "skipped".
"""
from __future__ import annotations

from models.manifest import CheckResult, Shipment


def _distinct(shipments: list[Shipment], attr: str) -> set[str]:
    values: set[str] = set()
    for s in shipments:
        v = getattr(s, attr)
        if v:
            values.add(v)
    return values


def _new_items_check(name: str, attr: str, baseline: list[Shipment],
                     recent: list[Shipment], noun: str) -> CheckResult:
    base = _distinct(baseline, attr)
    if not base:
        return CheckResult(name=name, status="skipped",
                           detail=f"No baseline history to compare {noun} against.")
    new = sorted(_distinct(recent, attr) - base)
    if new:
        return CheckResult(
            name=name, status="flag", items=new,
            detail=f"{len(new)} {noun} in the recent window were never seen in "
                   f"the customer's {len(base)}-strong history.",
        )
    return CheckResult(name=name, status="ok",
                       detail=f"All recent {noun} match the established baseline.")


def check_shippers(baseline, recent) -> CheckResult:
    return _new_items_check("Deviation from standard shippers", "shipper",
                            baseline, recent, "shippers")


def check_routes(baseline, recent) -> CheckResult:
    return _new_items_check("Deviation from standard routes", "route",
                            baseline, recent, "routes")


def check_hts(baseline, recent) -> CheckResult:
    has_hts = any(s.hts for s in baseline) or any(s.hts for s in recent)
    if not has_hts:
        return CheckResult(name="Deviation from standard HTS codes", status="skipped",
                           detail="No HTS/tariff column present in this manifest.")
    return _new_items_check("Deviation from standard HTS codes", "hts",
                            baseline, recent, "HTS codes")


def check_volume(baseline, recent, spike_factor: float) -> CheckResult:
    name = "Unexplained volume spike"
    if not baseline or not recent:
        return CheckResult(name=name, status="skipped",
                           detail="Not enough dated history to assess volume trend.")

    def rate_per_week(ships: list[Shipment]) -> float:
        dates = [s.ship_date for s in ships if s.ship_date]
        vol = sum(s.volume for s in ships)
        if not dates:
            return 0.0
        span_days = max((max(dates) - min(dates)).days, 1)
        weeks = max(span_days / 7.0, 1.0)
        return vol / weeks

    base_rate = rate_per_week(baseline)
    recent_rate = rate_per_week(recent)
    detail = (f"Recent rate ~{recent_rate:.1f}/wk vs. historical ~{base_rate:.1f}/wk.")
    if base_rate > 0 and recent_rate >= spike_factor * base_rate:
        return CheckResult(name=name, status="flag",
                           detail=f"{detail} That is >= {spike_factor:g}x the baseline.")
    return CheckResult(name=name, status="ok", detail=detail)


def run_all(baseline: list[Shipment], recent: list[Shipment],
            spike_factor: float) -> list[CheckResult]:
    return [
        check_shippers(baseline, recent),
        check_routes(baseline, recent),
        check_hts(baseline, recent),
        check_volume(baseline, recent, spike_factor),
    ]
