@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   KOverlay - Windows One-Click Installer
echo ===================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer_windows.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Installation did not finish successfully (Code: %ERRORLEVEL%).
    pause
    exit /b %ERRORLEVEL%
)
