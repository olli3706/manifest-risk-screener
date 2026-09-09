"""Render a manifest risk-screen ScreenResult into a PDF (+ markdown) report."""
from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models.manifest import ScreenResult

_STATUS_COLOR = {
    "flag": colors.HexColor("#c62828"),
    "ok": colors.HexColor("#2e7d32"),
    "skipped": colors.HexColor("#757575"),
}


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _markdown_to_flowables(md: str, styles) -> list:
    """Very small markdown renderer: #/##/### headings and -/* bullets."""
    out = []
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            out.append(Spacer(1, 4))
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = min(len(heading.group(1)), 3)
            out.append(Paragraph(_escape(heading.group(2)), styles[f"Heading{level}"]))
            continue
        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet:
            out.append(Paragraph("• " + _escape(bullet.group(1)), styles["Normal"]))
            continue
        # bold **text** -> <b>
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _escape(line))
        out.append(Paragraph(line, styles["Normal"]))
    return out


def generate(result: ScreenResult, output_dir: Path,
             filename: str = "Manifest_Risk_Screen.pdf") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            title=f"Manifest Risk Screen — {result.customer}")
    story = [
        Paragraph("Shipment Manifest Risk Screen", styles["Title"]),
        Spacer(1, 6),
    ]

    # Overall flag banner
    review = result.review_required
    banner_color = colors.HexColor("#c62828") if review else colors.HexColor("#2e7d32")
    banner_text = ("⚠ FLAGGED FOR COMPLIANCE MANAGER REVIEW" if review
                   else "✓ No automatic flags — routine")
    banner = Table([[banner_text]], colWidths=[6.5 * inch])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), banner_color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [banner, Spacer(1, 14)]

    # Dataset summary
    rows = [
        ["Customer", result.customer],
        ["Manifest", Path(result.manifest_path).name],
        ["Sheet analyzed", result.sheet or "—"],
        ["Total shipments", str(result.total_shipments)],
        ["Baseline / recent split",
         f"{result.baseline_count} historical  vs  {result.recent_count} recent "
         f"(last {result.recent_days} days)"],
        ["Distinct parties", str(len(result.parties))],
        ["AI web-search screen", "Yes" if result.ai_used else "No (deterministic only)"],
    ]
    table = Table(rows, colWidths=[2.2 * inch, 4.3 * inch])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eceff1")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [table, Spacer(1, 16)]

    # Deterministic checks
    story.append(Paragraph("Automated Anomaly Checks", styles["Heading2"]))
    for c in result.checks:
        tag = {"flag": "FLAG", "ok": "OK", "skipped": "N/A"}.get(c.status, "")
        head = (f'<font color="#{_STATUS_COLOR[c.status].hexval()[2:]}">'
                f"<b>[{tag}] {_escape(c.name)}</b></font>")
        story.append(Paragraph(head, styles["Normal"]))
        story.append(Paragraph(_escape(c.detail), styles["Normal"]))
        if c.items:
            preview = c.items[:12]
            story.append(Paragraph("• " + "; ".join(_escape(i) for i in preview),
                                   styles["Normal"]))
        story.append(Spacer(1, 8))

    # AI shell-company screen + synthesis
    story.append(Spacer(1, 6))
    story.append(Paragraph("Party Research &amp; Risk Synthesis (AI + web search)",
                           styles["Heading2"]))
    if result.ai_report:
        story += _markdown_to_flowables(result.ai_report, styles)
    else:
        story.append(Paragraph(
            "AI web-search screen not run (no API key or disabled). "
            "Findings above are from the deterministic checks only.",
            styles["Normal"]))

    doc.build(story)

    # Companion markdown for quick reading / archiving.
    md_path = output_dir / "Manifest_Risk_Screen.md"
    md_path.write_text(_result_to_markdown(result), encoding="utf-8")
    return path


def _result_to_markdown(result: ScreenResult) -> str:
    lines = [
        f"# Manifest Risk Screen — {result.customer}",
        "",
        f"**Overall:** {'FLAGGED FOR REVIEW' if result.review_required else 'Routine'}",
        f"**Manifest:** {result.manifest_path}  (sheet: {result.sheet})",
        f"**Shipments:** {result.total_shipments}  "
        f"(baseline {result.baseline_count} / recent {result.recent_count}, "
        f"last {result.recent_days} days)",
        f"**Parties:** {len(result.parties)}",
        "",
        "## Automated anomaly checks",
    ]
    for c in result.checks:
        lines.append(f"- **[{c.status.upper()}] {c.name}** — {c.detail}")
        if c.items:
            lines.append("  - " + "; ".join(c.items))
    lines += ["", "## Party research & synthesis (AI + web search)", ""]
    lines.append(result.ai_report or "_AI screen not run._")
    return "\n".join(lines)
