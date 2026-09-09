"""Shipment Manifest Risk Screener (entry point).

Usage:
    python main.py screen --manifest "path/to/shipments.xlsx"
    python main.py screen --manifest file.xlsx --customer "Acme Inc" --recent-days 45
"""
import re
from collections import Counter
from datetime import date
from pathlib import Path

import click

from config import settings
from analyze import baseline as bl
from analyze import checks as chk
from ingest import manifest as manifest_ingest
from generate import report as report_gen
from llm import client as llm_client
from models.manifest import ScreenResult


@click.group()
def cli():
    """Shipment Manifest Risk Screener v0.2"""


@cli.command()
@click.option("--manifest", "manifest_path", required=True, type=click.Path(exists=True),
              help="Shipment manifest workbook (.xlsx).")
@click.option("--sheet", default=None, help="Sheet name to analyze (auto-detected if omitted).")
@click.option("--customer", default=None, help="Customer name (auto-detected if omitted).")
@click.option("--recent-days", "recent_days", default=None, type=int,
              help=f"Recent window in days (default {settings.RECENT_DAYS}).")
def screen(manifest_path: str, sheet: str | None, customer: str | None,
           recent_days: int | None):
    """Screen a shipment manifest for anomalies and shell-company risk."""
    result = run_screen(Path(manifest_path), sheet=sheet, customer=customer,
                        recent_days=recent_days)
    _echo(result)


def _run_folder(customer: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", customer).strip("_") or "customer"
    folder = settings.OUTPUT_DIR / f"{safe}_{date.today():%Y%m%d}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _manifest_summary(shipments) -> str:
    routes, origins, shippers, consignees, goods = (Counter() for _ in range(5))
    for s in shipments:
        if s.route:
            routes[s.route] += 1
        if s.origin:
            origins[s.origin] += 1
        if s.shipper:
            shippers[s.shipper] += 1
        if s.consignee:
            consignees[s.consignee] += 1
        if s.goods:
            goods[s.goods[:40]] += 1

    def top(counter, n=12):
        return "; ".join(f"{k} (x{v})" for k, v in counter.most_common(n)) or "none"

    return (
        f"Routes: {top(routes)}\n"
        f"Origins: {top(origins)}\n"
        f"Shippers: {top(shippers)}\n"
        f"US consignees: {top(consignees)}\n"
        f"Goods: {top(goods)}"
    )


def run_screen(manifest_path: Path, sheet: str | None = None,
               customer: str | None = None, recent_days: int | None = None) -> ScreenResult:
    """Full screening pipeline for one manifest workbook."""
    shipments, sheet_used = manifest_ingest.parse(manifest_path, sheet)
    customer = customer or bl.detect_customer(shipments)
    window = recent_days if recent_days is not None else settings.RECENT_DAYS

    base, recent = bl.split(shipments, window)
    checks = chk.run_all(base, recent, settings.VOLUME_SPIKE_FACTOR)
    party_list = bl.parties(shipments)
    summary = _manifest_summary(shipments)

    ai_report, ai_flag = llm_client.screen_parties(customer, party_list, checks, summary)
    deterministic_flag = any(c.flagged for c in checks)

    folder = _run_folder(customer)
    result = ScreenResult(
        customer=customer,
        manifest_path=str(manifest_path),
        sheet=sheet_used,
        total_shipments=len(shipments),
        baseline_count=len(base),
        recent_count=len(recent),
        recent_days=window,
        checks=checks,
        parties=party_list,
        ai_report=ai_report,
        ai_used=ai_report is not None,
        review_required=deterministic_flag or ai_flag,
        output_folder=str(folder),
    )
    report_gen.generate(result, folder)
    return result


def _echo(result: ScreenResult) -> None:
    click.echo(f"Customer: {result.customer}")
    click.echo(f"Shipments: {result.total_shipments} "
               f"(baseline {result.baseline_count} / recent {result.recent_count})")
    for c in result.checks:
        tag = {"flag": "FLAG", "ok": "ok", "skipped": "n/a"}.get(c.status, "")
        click.echo(f"  [{tag}] {c.name}: {c.detail}")
    click.echo(f"AI web-search screen: {'yes' if result.ai_used else 'no'}")
    if result.review_required:
        click.echo("==> FLAGGED FOR COMPLIANCE MANAGER REVIEW")
    else:
        click.echo("==> No automatic flags")
    click.echo(f"Report: {result.output_folder}")


if __name__ == "__main__":
    cli()
