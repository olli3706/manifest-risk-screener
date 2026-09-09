# Builds "Screen Manifest.exe" — a standalone drag-and-drop screener that needs
# NO Python install on the target machine. Run this once on a Windows PC that
# has Python + the project dependencies installed:
#
#     cd "desktop"
#     powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
#
# Output: desktop\dist\Screen Manifest.exe  (copy it anywhere; put a .env with
# ANTHROPIC_API_KEY next to it to enable the AI web-search screen).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing build tool (pyinstaller) and dependencies..."
python -m pip install --quiet pyinstaller
python -m pip install --quiet -r "..\python_scripts\requirements.txt"

Write-Host "Building the executable (this can take a couple of minutes)..."
python -m PyInstaller `
    --onefile `
    --console `
    --noconfirm `
    --name "Screen Manifest" `
    --paths "..\python_scripts" `
    --collect-all anthropic `
    --collect-all reportlab `
    --collect-submodules pydantic `
    --collect-submodules pydantic_core `
    --hidden-import openpyxl `
    --hidden-import dotenv `
    "screen_launcher.py"

Write-Host ""
Write-Host "Done. The app is at:  desktop\dist\Screen Manifest.exe"
Write-Host "Put a .env file (with ANTHROPIC_API_KEY=...) next to the .exe to enable AI."
