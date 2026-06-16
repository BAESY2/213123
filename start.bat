@echo off
REM ==========================================================================
REM  BTC 5-min bot - ONE-CLICK launcher for Windows.
REM  Double-click this file. It will:
REM    1) create a local Python virtual environment (.venv) if missing
REM    2) install dependencies
REM    3) create .env from .env.example on first run
REM    4) start the bot (DRY-RUN by default - no real money)
REM  Requires Python 3.9+ installed and on PATH (https://www.python.org/downloads/).
REM ==========================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python 3.9+ from https://www.python.org/downloads/
  echo         During install, CHECK "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv" (
  echo [setup] creating virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [setup] installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

if not exist ".env" (
  echo [setup] creating .env from .env.example - edit it to enable live trading.
  copy /Y ".env.example" ".env" >nul
)

echo.
echo ==========================================================
echo  Starting bot. Mode is controlled by ENABLE_LIVE in .env.
echo  Default = DRY-RUN (safe, no real orders). Ctrl+C to stop.
echo ==========================================================
echo.
python run_bot.py

pause
endlocal
