"""App configuration for the shipment-manifest risk screener."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Where reports are written. When packaged as an .exe, BASE_DIR points into a
# temporary PyInstaller extraction folder that is deleted on exit, so write
# next to the .exe instead (a persistent, findable location).
if getattr(sys, "frozen", False):
    OUTPUT_DIR = Path(sys.executable).resolve().parent / "output"
else:
    OUTPUT_DIR = BASE_DIR / "output"

# --- Screening thresholds ----------------------------------------------------
# "Recent" window: shipments within this many days of the file's latest shipment
# are compared against everything before them (the customer's baseline).
RECENT_DAYS: int = int(os.getenv("MRS_RECENT_DAYS", "30"))
# Flag a volume spike when the recent shipment rate exceeds this multiple of the
# customer's historical average rate.
VOLUME_SPIKE_FACTOR: float = float(os.getenv("MRS_VOLUME_SPIKE_FACTOR", "2.0"))

# --- Anthropic (Claude) API — shell-company web search + risk synthesis -------
# ⚠️ When set, manifest/party data is sent to api.anthropic.com (outside your network),
# and Claude performs live web searches on the parties. Leave the key blank to
# run the deterministic checks only (no web research, no AI synthesis).
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-opus-4-8")
AI_ENABLED: str = os.getenv("MRS_AI_ENABLED", "1")
