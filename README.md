# Shipment Manifest Risk Screener

Screens a customer's shipment manifest for compliance anomalies and shell-company
risk. It learns each customer's "normal" from the history in their own manifest,
flags deviations, has Claude **web-search every party** for shell-company signals,
and produces a report that **flags for compliance-manager review**.

## What it checks

| Check | How |
|-------|-----|
| **Deviation from standard shippers** | New shippers in the recent window vs. the customer's history |
| **Deviation from standard routes** | New origin→destination lanes vs. history |
| **Deviation from standard HTS codes** | New/shifted HTS codes *(runs only if the file has an HTS column)* |
| **Unexplained volume spike** | Recent shipment rate vs. historical average (≥ threshold ×) |
| **Shell-company screen** | Claude web-searches every shipper & consignee (registration, address, footprint) |
| **Overall flag** | `REVIEW REQUIRED` / routine, for the compliance manager |

The first four checks are deterministic (computed locally). The shell screen and
the final synthesis use the Anthropic (Claude) API with live web search.

---

## Quick start

```bash
# 1. Install dependencies (Python 3.11+)
cd python_scripts
pip install -r requirements.txt

# 2. Configure the API key (optional — see "AI screen" below)
cp .env.example .env      # then paste your ANTHROPIC_API_KEY into .env

# 3. Screen a manifest
python main.py screen --manifest "C:\path\to\shipments.xlsx"
```

Output lands in `output/<CUSTOMER>_<DATE>/`:

```
Manifest_Risk_Screen.pdf   # the report, with the compliance-manager flag banner
Manifest_Risk_Screen.md    # same content as markdown for quick reading/archiving
```

### Options

| Flag | Meaning |
|------|---------|
| `--manifest <file.xlsx>` | **Required.** The shipment workbook to screen. |
| `--sheet <name>` | Which sheet to analyze (auto-detected if omitted). |
| `--customer <name>` | Customer name (auto-detected from the dominant consignee if omitted). |
| `--recent-days <n>` | Size of the "recent" window in days (default 30). |

---

## How the baseline works

The tool splits the manifest by date: shipments within `--recent-days` of the
file's **latest** shipment are the **recent window**; everything before is the
**baseline**. Deviations are measured as "seen in recent but never in baseline."
So the manifest you feed it should contain the customer's **history**, not just
the latest batch — that history *is* the baseline.

## Input format

Manifests vary, so columns are matched by **header keywords** (not fixed
positions) and the header row is found automatically. Recognized fields:
shipper, consignee (US/AMS), ultimate consignee, origin, destination, ETA/ETD,
HTS, volume/TEU/quantity, goods, container, HBL, MBL. Missing columns just
disable the checks that need them (e.g. no HTS column → the HTS check is skipped
and noted).

---

## AI screen (Anthropic / Claude)

The shell-company research and final synthesis use the Anthropic API with live
web search. All LLM access funnels through
[`llm/client.py`](python_scripts/llm/client.py).

> ⚠️ **Data egress.** When enabled, party/manifest data is sent to
> `api.anthropic.com` and Claude issues live web searches on the parties — this
> leaves your systems. Keep the key in `.env` (git-ignored); rotate if exposed.

```bash
# in python_scripts/.env
ANTHROPIC_API_KEY=sk-ant-...     # blank = deterministic checks only, no web/AI
LLM_MODEL=claude-opus-4-8        # default
MRS_AI_ENABLED=1                 # 0 to hard-disable even with a key
```

If the key is blank (or the `anthropic` package isn't installed), the screen
still runs the four deterministic checks and produces a report — just without
the web research and AI synthesis. AI failures never block a run.

---

## Project layout

```
python_scripts/
├── main.py              # CLI `screen` command + orchestration
├── config/settings.py   # thresholds (recent window, volume factor) + AI config
├── models/manifest.py   # Shipment, CheckResult, ScreenResult
├── ingest/manifest.py   # flexible manifest workbook parser
├── analyze/             # baseline split + deterministic checks
├── llm/client.py        # Claude web-search shell screen + synthesis
├── generate/report.py   # PDF + markdown report with the review flag
└── tests/               # pytest suite
```

## Development

```bash
cd python_scripts
python -m pytest        # run the test suite
python -m ruff check .  # lint
```

Tests are self-contained — they build synthetic workbooks and mock the API, so
they need no real files, key, or network.

## Configuration notes

- `MRS_RECENT_DAYS` / `MRS_VOLUME_SPIKE_FACTOR` env vars override the defaults
  (30 days, 2.0×).
- `.env` is git-ignored — never commit real keys.
