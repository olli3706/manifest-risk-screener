"""Tests for the AI shell-screen client (mocked — no network calls)."""
from llm import client
from models.manifest import CheckResult


def _configure(monkeypatch, key="real-key-123", enabled="1"):
    monkeypatch.setattr(client.settings, "ANTHROPIC_API_KEY", key)
    monkeypatch.setattr(client.settings, "AI_ENABLED", enabled)


def test_not_configured_when_key_blank(monkeypatch):
    _configure(monkeypatch, key="")
    assert client.is_configured() is False
    assert client.is_enabled() is False


def test_configured_and_enabled(monkeypatch):
    _configure(monkeypatch)
    assert client.is_enabled() is True


def test_disabled_flag_overrides_key(monkeypatch):
    _configure(monkeypatch, enabled="0")
    assert client.is_enabled() is False


def test_screen_skips_when_disabled(monkeypatch):
    _configure(monkeypatch, key="")

    def _fail(prompt, n_parties):
        raise AssertionError("_invoke should not run when disabled")

    monkeypatch.setattr(client, "_invoke", _fail)
    report, flag = client.screen_parties("Acme", ["A", "B"], [], "summary")
    assert report is None and flag is False


def test_screen_returns_report_and_flag_when_enabled(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(client, "_invoke",
                        lambda prompt, n_parties: "Report...\nOVERALL FLAG: REVIEW REQUIRED")
    checks = [CheckResult(name="Deviation from standard shippers", status="flag",
                          detail="new shipper", items=["GAMMA CO"])]
    report, flag = client.screen_parties("Acme", ["A"], checks, "summary")
    assert "OVERALL FLAG" in report
    assert flag is True


def test_parse_flag_cleared():
    assert client._parse_flag("stuff\nOVERALL FLAG: CLEARED") is False


def test_parse_flag_review():
    assert client._parse_flag("stuff\nOVERALL FLAG: REVIEW REQUIRED") is True


def test_parse_flag_missing_is_conservative():
    assert client._parse_flag("no verdict here") is True


def test_clean_report_strips_narration():
    raw = ("I'll research each party. Let me search...\n"
           "The searches returned data. Now the report.\n"
           "# COMPLIANCE RISK REPORT\n\nBody text.\nOVERALL FLAG: REVIEW REQUIRED")
    cleaned = client._clean_report(raw)
    assert cleaned.startswith("# COMPLIANCE RISK REPORT")
    assert "I'll research" not in cleaned


def test_build_prompt_includes_parties_and_flags():
    checks = [CheckResult(name="Deviation from standard routes", status="flag",
                          detail="new route", items=["CNXAM -> USLAX"])]
    prompt = client._build_prompt("Acme", ["VOYAGER TRADING"], checks, "Routes: ...")
    assert "VOYAGER TRADING" in prompt
    assert "CNXAM -> USLAX" in prompt
    assert "[FLAG]" in prompt
