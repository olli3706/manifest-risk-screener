@echo off
rem  Drag a manifest .xlsx onto this file (or a shortcut to it) to screen it.
rem  %~dp0 = the folder this .bat lives in, so it finds the launcher next to it.
python "%~dp0screen_launcher.py" %*
if errorlevel 1 (
  echo.
  echo If you saw "python is not recognized", Python is not installed on this PC.
  echo Use the packaged "Screen Manifest.exe" instead ^(no install needed^).
  pause
)
