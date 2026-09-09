"""Centralized Claude (Anthropic) client for shell-company web research + synthesis.

Single source of truth for every outbound LLM call. Given the parties on a
manifest and the deterministic anomaly findings, Claude runs live web searches
on each party (registration, address, web footprint) and writes a compliance
risk report ending in an OVERALL FLAG for the manager.

⚠️ DATA EGRESS — this is the one place that sends manifest/party data OUTSIDE
your systems, to Anthropic's API (api.anthropic.com), and issues live web
searches. It stays disabled unless BOTH:
  1. ANTHROPIC_API_KEY is set (in .env — never commit it), and
  2. MRS_AI_ENABLED is not turned off.
When disabled the screen still runs the deterministic checks; the AI report is
skipped. AI failures never block a run.

The `anthropic` package is imported lazily so the app imports/runs without it.
"""
from __future__ import annotations

import logging
from typing import Optional

from config import settings
from models.manifest import CheckResult

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4-8"
_MAX_TOKENS = 4096
_MAX_CONTINUATIONS = 4          # pause_turn continuations while web search runs

_SYSTEM_PROMPT = (
    "You are a US trade-compliance analyst for a freight forwarder / NVOCC "
    "(a freight forwarder), screening an import shipment manifest. Use the web_search "
    "tool to research EACH party (shippers and consignees): business "
    "registration, physical address, age, website / footprint, and any adverse "
    "media. You do NOT have live OFAC/BIS/UN/EU denied-party list access, so do "
    "NOT assert that any party is or isn't sanctioned — instead flag who "
    "warrants formal screening and why. Assess shell-company likelihood from "
    "the evidence (thin/absent web presence, shared or virtual addresses, "
    "generic names, very recent registration, no real operations). Combine your "
    "findings with the deterministic anomaly flags provided. Be specific, cite "
    "what you found, and state uncertainty honestly. Output ONLY the final "
    "structured report starting with a markdown heading — do NOT narrate your "
    "search steps in the response text. End your report with a final line "
    "exactly of the form 'OVERALL FLAG: REVIEW REQUIRED' or 'OVERALL FLAG: "
    "CLEARED'."
)


def is_configured() -> bool:
    key = (settings.ANTHROPIC_API_KEY or "").strip()
    return bool(key) and "PLACEHOLDER" not in key.upper()


def is_enabled() -> bool:
    if not is_configured():
        return False
    flag = (settings.AI_ENABLED or "").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def screen_parties(customer: str, parties: list[str], checks: list[CheckResult],
                   shipment_summary: str) -> tuple[Optional[str], bool]:
    """Return (report_markdown, ai_review_flag).

    (None, False) when AI is disabled/unavailable/errors. Never raises.
    """
    if not is_enabled():
        log.info("AI shell screen skipped — not configured or disabled.")
        return None, False

    prompt = _build_prompt(customer, parties, checks, shipment_summary)
    report = _invoke(prompt, n_parties=len(parties))
    if report is None:
        return None, False
    flag = _parse_flag(report)
    return report, flag


def _build_prompt(customer: str, parties: list[str], checks: list[CheckResult],
                  shipment_summary: str) -> str:
    lines = [
        f"Customer / importer under review: {customer}",
        "",
        "DETERMINISTIC ANOMALY FINDINGS (computed from the manifest history):",
    ]
    for c in checks:
        marker = {"flag": "[FLAG]", "ok": "[ok]", "skipped": "[skipped]"}.get(c.status, "")
        lines.append(f"- {marker} {c.name}: {c.detail}")
        if c.items:
            lines.append("    -> " + "; ".join(c.items))
    lines += [
        "",
        f"PARTIES TO RESEARCH ({len(parties)}) — web-search each one:",
    ]
    lines += [f"- {p}" for p in parties]
    lines += ["", "MANIFEST SUMMARY:", shipment_summary, "",
              "Produce the compliance risk report now."]
    return "\n".join(lines)


def _invoke(prompt: str, n_parties: int) -> Optional[str]:
    try:
        import anthropic
    except ImportError:
        log.warning("`anthropic` package not installed — skipping AI shell screen.")
        return None

    max_uses = min(max(n_parties * 2, 8), 40)
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses}]
    messages = [{"role": "user", "content": prompt}]

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        model = settings.LLM_MODEL or DEFAULT_MODEL
        response = client.messages.create(
            model=model, max_tokens=_MAX_TOKENS, system=_SYSTEM_PROMPT,
            tools=tools, messages=messages,
        )
        # The web-search server loop can pause; resume until it finishes.
        for _ in range(_MAX_CONTINUATIONS):
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
            response = client.messages.create(
                model=model, max_tokens=_MAX_TOKENS, system=_SYSTEM_PROMPT,
                tools=tools, messages=messages,
            )
    except Exception as exc:  # noqa: BLE001 — AI is optional; never break the screen
        log.warning("AI shell screen failed (%s): %s", type(exc).__name__, exc)
        return None

    if response.stop_reason == "refusal":
        log.warning("AI shell screen refused.")
        return None
    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    return _clean_report(text) or None


def _clean_report(text: str) -> str:
    """Drop any tool-use narration before the report's first markdown heading."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            return "\n".join(lines[i:]).strip()
    return text.strip()


def _parse_flag(report: str) -> bool:
    """True (review required) unless the report clearly says CLEARED."""
    for line in reversed(report.splitlines()):
        upper = line.upper()
        if "OVERALL FLAG" in upper:
            if "REVIEW" in upper:
                return True
            if "CLEAR" in upper:
                return False
    # No explicit flag line -> be conservative.
    return True
