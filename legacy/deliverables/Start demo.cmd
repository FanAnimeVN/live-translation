@echo off
setlocal
set "DEMO_ROOT=%~dp0.."
if not exist "%DEMO_ROOT%\.venv\Scripts\pythonw.exe" (
  echo Development runtime is missing. This demo requires the original project folder.
  pause
  exit /b 1
)
start "" "%DEMO_ROOT%\.venv\Scripts\pythonw.exe" "%DEMO_ROOT%\scripts\demo_launcher.py"
