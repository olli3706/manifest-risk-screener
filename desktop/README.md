# Drag-and-drop screener (Option B)

Screen a shipment manifest by **dragging the file onto an icon** — no terminal,
no commands.

## Two ways to use it

### 1. Right now, on a PC that has the project + Python
Drag a manifest `.xlsx` onto **`Screen Manifest.bat`** (or a desktop shortcut to
it). A window opens, it runs the screen, and the report PDF pops up when done.

To put an icon on the Desktop: right-click `Screen Manifest.bat` →
**Send to → Desktop (create shortcut)**, then rename the shortcut to
"Screen Manifest". Drop files onto that.

### 2. For any PC (no Python needed) — build the standalone app
On a Windows PC that has Python + the dependencies, run:

```powershell
cd desktop
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

This produces **`desktop\dist\Screen Manifest.exe`**. Copy that `.exe` to any
Windows machine and drag manifests onto it — nothing else to install.

## Turning on the AI web-search screen
The shell-company web research uses the Anthropic API. Put a file named **`.env`**
next to the `.bat`/`.exe` containing:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Without a key it still runs the four deterministic checks (shippers, routes,
HTS, volume) and produces a report — just no web research.

## What the user sees
1. Drop a `.xlsx` on the icon.
2. A window shows "Screening… (web research can take 1–3 minutes)".
3. It prints the verdict — **REVIEW REQUIRED** or **Routine** — and the report
   PDF opens automatically.
4. Reports are saved under `python_scripts\output\<CUSTOMER>_<DATE>\`.

## Notes
- If the workbook is open in Excel, that's fine — the launcher works from a copy.
- Wrong file type or a sheet with no shipment columns gives a plain-English
  message, not an error dump.
