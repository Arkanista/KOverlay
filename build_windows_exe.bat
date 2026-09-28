@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===================================================
echo   Building KOverlay Windows Standalone Executable (.exe)
echo ===================================================
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

echo.
echo Compiling executable with PyInstaller...
pyinstaller --noconsole --onefile --name "KOverlay" ^
    --add-data "icon.png;." ^
    --add-data "icons;icons" ^
    koverlay.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===================================================
    echo   BUILD SUCCESSFUL!
    echo   The executable is ready at: dist\KOverlay.exe
    echo ===================================================
) else (
    echo.
    echo [ERROR] Build failed with error code %ERRORLEVEL%.
)

pause
