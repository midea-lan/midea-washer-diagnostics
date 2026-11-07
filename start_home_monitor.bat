@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Missing Python environment: %PY%
  echo Run install.bat first.
  pause
  exit /b 1
)

if not exist "%~dp0home_devices.json" (
  echo First run: discovering supported Midea LAN devices...
  "%PY%" "%~dp0initialize_home_devices.py"
  if errorlevel 1 (
    pause
    exit /b 1
  )
)

"%PY%" "%~dp0home_monitor.py" --interval 5 --open-browser
echo.
echo Home monitor stopped. Press Ctrl+C to stop safely while it is running.
pause
