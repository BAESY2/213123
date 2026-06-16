@echo off
REM ==========================================================================
REM  Build a standalone Windows .exe with PyInstaller.
REM  Output: dist\btc5m-bot.exe  (double-click to run).
REM  The .exe reads .env from the SAME folder you run it in.
REM ==========================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python 3.9+ and re-run.
  pause
  exit /b 1
)

if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller

echo [build] running PyInstaller...
pyinstaller --onefile --name btc5m-bot ^
  --collect-all py_clob_client ^
  run_bot.py

echo.
echo [done] Executable at: dist\btc5m-bot.exe
echo        Put your .env next to the .exe, then double-click it.
pause
endlocal
