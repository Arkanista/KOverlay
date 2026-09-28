@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Starting KOverlay (Windows)
echo ===================================================

:: Check if virtual environment exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

:: Run KOverlay
python koverlay.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)
