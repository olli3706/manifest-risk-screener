"""Split a customer's shipments into a historical baseline vs. a recent window."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from models.manifest import Shipment


def detect_customer(shipments: list[Shipment]) -> str:
    """Best-guess customer = the most common ultimate/US consignee."""
    names = Counter()
    for s in shipments:
        name = s.ultimate_consignee or s.consignee
        if name:
            names[name] += 1
    return names.most_common(1)[0][0] if names else "Unknown Customer"


def split(shipments: list[Shipment], recent_days: int
          ) -> tuple[list[Shipment], list[Shipment]]:
    """Return (baseline, recent).

    Recent = shipments dated within `recent_days` of the latest shipment in the
    file; baseline = everything dated before that. Undated rows are treated as
    baseline. If the file has no dates at all, everything is 'recent' (there is
    no history to compare against).
    """
    dated = [s for s in shipments if s.ship_date]
    if not dated:
        return [], list(shipments)

    latest = max(s.ship_date for s in dated)
    cutoff = latest - timedelta(days=recent_days)
    recent = [s for s in dated if s.ship_date > cutoff]
    baseline = [s for s in shipments if s.ship_date and s.ship_date <= cutoff]
    baseline += [s for s in shipments if not s.ship_date]
    return baseline, recent


def parties(shipments: list[Shipment]) -> list[str]:
    """Distinct party names (shippers + consignees) across the manifest."""
    seen: dict[str, None] = {}
    for s in shipments:
        for name in (s.shipper, s.consignee, s.ultimate_consignee):
            if name:
                seen.setdefault(name, None)
    return list(seen)
