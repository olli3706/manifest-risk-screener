"""Pydantic models for the shipment-manifest risk screener."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class Shipment(BaseModel):
    """One shipment row parsed from a manifest workbook."""
    row: int
    ship_date: Optional[date] = None
    shipper: Optional[str] = None            # origin-side shipper
    consignee: Optional[str] = None          # AMS/manifest US consignee
    ultimate_consignee: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    hts: Optional[str] = None
    volume: float = 1.0                       # TEU/qty if present, else 1 (= 1 shipment)
    goods: Optional[str] = None
    container: Optional[str] = None
    hbl: Optional[str] = None
    mbl: Optional[str] = None

    @property
    def route(self) -> Optional[str]:
        if self.origin and self.destination:
            return f"{self.origin} -> {self.destination}"
        return None


class CheckResult(BaseModel):
    """Outcome of one deterministic anomaly check."""
    name: str
    status: str          # "flag" | "ok" | "skipped"
    detail: str
    items: list[str] = Field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return self.status == "flag"


class ScreenResult(BaseModel):
    """Full result of screening one manifest."""
    customer: str
    manifest_path: str
    sheet: Optional[str] = None
    total_shipments: int
    baseline_count: int
    recent_count: int
    recent_days: int
    checks: list[CheckResult] = Field(default_factory=list)
    parties: list[str] = Field(default_factory=list)
    ai_report: Optional[str] = None          # web-search shell screen + synthesis
    ai_used: bool = False
    review_required: bool = False
    output_folder: Optional[str] = None

    @property
    def flagged_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if c.flagged]
