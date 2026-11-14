@echo off
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.12 from https://www.python.org/downloads/windows/ with the Python launcher.
  exit /b 1
)
py -3.12 "%~dp0setup.py" %*
set "SETUP_RESULT=%errorlevel%"
if not "%SETUP_RESULT%"=="0" echo Setup failed. See docs\runtime\installation.md
exit /b %SETUP_RESULT%
