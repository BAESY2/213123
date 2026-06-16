@echo off
REM ==========================================================================
REM  BTC 5-min bot - ONE-CLICK launcher for Windows (robust Python detection).
REM  Double-click. Creates venv, installs deps, makes .env, runs the bot.
REM  Requires REAL Python 3.9+ (python.org). Handles the Microsoft Store stub.
REM ==========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- Find a WORKING python: prefer the 'py' launcher, then 'python' ---
set "PYEXE="
py -3 -c "import sys" >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
  python -c "import sys" >nul 2>nul && set "PYEXE=python"
)

if not defined PYEXE (
  echo.
  echo ============================================================
  echo  [!] Python 이 설치되어 있지 않습니다 ^(또는 스토어 가짜 버전만 있음^).
  echo.
  echo  해결:
  echo   1^) https://www.python.org/downloads/ 에서 Python 3 설치
  echo   2^) 설치 화면에서 "Add python.exe to PATH" 반드시 체크
  echo   3^) 이 start.bat 을 다시 더블클릭
  echo.
  echo  (스토어 가짜 python 끄기: 설정 ^> 앱 ^> 앱 실행 별칭 ^>
  echo   python.exe / python3.exe 둘 다 OFF)
  echo ============================================================
  echo.
  pause
  exit /b 1
)

echo [setup] using: %PYEXE%
%PYEXE% --version

if not exist ".venv" (
  echo [setup] creating virtual environment...
  %PYEXE% -m venv .venv
  if errorlevel 1 (
    echo [!] venv 생성 실패. Python 재설치 후 다시 시도하세요.
    pause
    exit /b 1
  )
)

REM --- Use the venv's python directly (most reliable) ---
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
  echo [!] venv python 을 찾을 수 없습니다: %VPY%
  pause
  exit /b 1
)

echo [setup] installing dependencies...
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [!] 의존성 설치 실패 ^(인터넷 연결 확인^).
  pause
  exit /b 1
)

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
"%VPY%" run_bot.py

pause
endlocal
