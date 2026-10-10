@echo off
REM RelayDesk - double-click to start. Uses the project's own Python (backend\venv),
REM installs anything missing, starts the server and opens the browser.
title RelayDesk
cd /d "%~dp0backend"

if not exist "venv\Scripts\python.exe" (
    echo [1/3] Creating the Python environment ^(first run only^)...
    python -m venv venv
    if errorlevel 1 goto :no_python
)

venv\Scripts\python.exe -c "import fastapi, sqlalchemy, alembic, sklearn, jose, bcrypt" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installing required libraries ^(first run only, needs internet^)...
    venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 goto :install_failed
)

if not exist ".env" (
    echo Creating backend\.env from .env.example...
    copy /y ".env.example" ".env" >nul
)

echo [3/3] Starting RelayDesk at http://localhost:8000  ^(close this window to stop^)
echo       Your browser opens automatically as soon as the server is ready.
REM Open the browser only once the server actually answers (up to 3 minutes)
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i = 0; $i -lt 180; $i++) { try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 2 | Out-Null; Start-Process 'http://localhost:8000'; break } catch { Start-Sleep -Seconds 1 } }"
REM Auto-reload is a developer feature that doubles start-up time
set RELAYDESK_RELOAD=0
venv\Scripts\python.exe main.py
echo.
echo The server stopped. If you see an error above, copy it and ask for help.
pause
exit /b 0

:no_python
echo.
echo Python 3.10+ was not found. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" during setup), then run start.bat again.
pause
exit /b 1

:install_failed
echo.
echo Installing the libraries failed - check your internet connection and run start.bat again.
pause
exit /b 1
