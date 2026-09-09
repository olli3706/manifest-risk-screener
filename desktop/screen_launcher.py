"""Drag-and-drop launcher for the Manifest Risk Screener.

A user drags a manifest workbook onto the icon (or into the window); Windows
passes the path in. The app screens it, opens the report, then asks whether
there are more files — looping until the user answers No, at which point it
prints a big "COPY" so casual users clearly see it's finished.

Works two ways:
  * from source:   python desktop/screen_launcher.py "C:\\path\\manifest.xlsx"
  * frozen (.exe): "Screen Manifest.exe" is the drop target (no Python needed)
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

_COPY_ART = r"""
   ____    ___    ____   __   __
  / ___|  / _ \  |  _ \  \ \ / /
 | |     | | | | | |_) |  \ V /
 | |___  | |_| | |  __/    | |
  \____|  \___/  |_|       |_|
"""


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bootstrap() -> None:
    """Make the engine importable and load the API key from .env."""
    app_dir = _app_dir()
    pkg_dir = app_dir.parent / "python_scripts"
    if pkg_dir.exists() and str(pkg_dir) not in sys.path:
        sys.path.insert(0, str(pkg_dir))
    try:
        from dotenv import load_dotenv
        for candidate in (app_dir / ".env", pkg_dir / ".env"):
            if candidate.exists():
                load_dotenv(candidate)
                break
    except Exception:
        pass  # deterministic checks still run without a key


def _clean_path(raw: str) -> str:
    """Normalize a path that was typed or dragged into the window."""
    return raw.strip().strip('"').strip("'").strip()


def screen_file(raw_path: str) -> None:
    """Screen one file, print the verdict, and open the report."""
    src = Path(_clean_path(raw_path))
    if not src.exists():
        print(f"\n  Couldn't find that file:\n    {src}\n")
        return
    if src.suffix.lower() not in (".xlsx", ".xlsm"):
        print(f"\n  That isn't an Excel workbook (got '{src.suffix}').")
        print("  Please drop a shipment manifest saved as .xlsx.\n")
        return

    # Work from a copy so a file open in Excel doesn't block us.
    work = Path(tempfile.gettempdir()) / f"screen_{src.name}"
    try:
        shutil.copy2(src, work)
    except Exception:
        work = src

    from main import run_screen  # imported after _bootstrap()

    print(f"\n  Screening: {src.name}")
    print("  Running checks and researching parties on the web...")
    print("  (The web research can take 1-3 minutes - please wait.)\n")

    try:
        result = run_screen(work)
    except ValueError as exc:
        print(f"\n  This file couldn't be screened: {exc}\n")
        return
    except Exception:  # noqa: BLE001
        print("\n  Something went wrong while screening this file. Details:")
        traceback.print_exc()
        return

    verdict = "REVIEW REQUIRED" if result.review_required else "Routine - no automatic flags"
    print("  " + "-" * 56)
    print(f"    Customer : {result.customer}")
    print(f"    Shipments: {result.total_shipments}")
    print(f"    Result   : {verdict}")
    print("  " + "-" * 56)

    pdf = Path(result.output_folder) / "Manifest_Risk_Screen.pdf"
    print(f"\n  Report saved to:\n    {result.output_folder}")
    if pdf.exists() and hasattr(os, "startfile"):
        try:
            os.startfile(str(pdf))  # noqa: S606
            print("  Opening the report...")
        except Exception:
            print("  (Open the PDF above to read the report.)")


def _ask_yes_no(question: str) -> bool:
    """Return True for Y, False for N; re-ask on anything else."""
    while True:
        try:
            answer = input(f"\n{question} (Y/N): ").strip().lower()
        except EOFError:
            return False
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please type Y for yes or N for no.")


def _prompt_for_file() -> str:
    try:
        return input("\n  Drag the next manifest into this window, then press Enter:\n  > ")
    except EOFError:
        return ""


def main() -> int:
    print("=" * 60)
    print("  Shipment Manifest Risk Screener")
    print("=" * 60)

    _bootstrap()

    # First file(s): from the icon drop (argv) or, if none, ask for one.
    initial = [a for a in sys.argv[1:] if a.strip()]
    if initial:
        for path in initial:
            screen_file(path)
    else:
        first = _prompt_for_file()
        if first.strip():
            screen_file(first)

    # Loop: any more files?
    while _ask_yes_no("Any more files?"):
        path = _prompt_for_file()
        if path.strip():
            screen_file(path)
        else:
            print("  (No file received.)")

    # Done — big, unmistakable confirmation.
    print(_COPY_ART)
    print("  All done. You can close this window.")
    try:
        input()
    except EOFError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
