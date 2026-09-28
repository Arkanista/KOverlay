#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_DIR="$SCRIPT_DIR/build_win"
OUTPUT_DIR="$SCRIPT_DIR/dist"
BUNDLE_DIR="$BUILD_DIR/bundle"
PYTHON_DIR="$BUNDLE_DIR/python"
SITE_PACKAGES="$PYTHON_DIR/Lib/site-packages"

echo "=========================================================="
echo "    Building KOverlay Self-Contained Windows Installer    "
echo "=========================================================="

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/wheels"
mkdir -p "$SITE_PACKAGES"
mkdir -p "$OUTPUT_DIR"

# 1. Download official Python 3.11 embeddable for Windows x64
echo "[1/5] Downloading Python 3.11 embeddable (Windows x64)..."
curl -sL https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip -o "$BUILD_DIR/pyembed.zip"
7z x -y "$BUILD_DIR/pyembed.zip" -o"$PYTHON_DIR" >/dev/null

# Configure ._pth to import site-packages and parent app directory
cat << 'EOF' > "$PYTHON_DIR/python311._pth"
python311.zip
.
..
Lib\site-packages
import site
EOF

# 2. Download Windows wheels for requirements
echo "[2/5] Downloading Windows binary wheels (PyQt6, ts3, edge-tts)..."
pip download --platform win_amd64 --python-version 3.11 --only-binary=:all: -d "$BUILD_DIR/wheels" -r requirements.txt

# Extract wheels to site-packages
echo "[3/5] Extracting packages into site-packages..."
for whl in "$BUILD_DIR/wheels"/*.whl; do
    7z x -y "$whl" -o"$SITE_PACKAGES" >/dev/null
done

# 3. Ensure Windows Mumble plugin DLL is compiled
if [ -d "mumble_plugin" ]; then
    echo "Checking Mumble plugin DLL for Windows..."
    GXX="$HOME/.cache/w64devkit/w64devkit/bin/g++.exe"
    if [ ! -f "mumble_plugin/koverlay_mumble.dll" ] || [ "mumble_plugin/koverlay_mumble.cpp" -nt "mumble_plugin/koverlay_mumble.dll" ]; then
        if [ -f "$GXX" ]; then
            echo "Compiling mumble_plugin/koverlay_mumble.dll via w64devkit..."
            WINEDEBUG=-all wine "$GXX" -O2 -Wall -std=c++17 -shared -s \
                -I"mumble_plugin/include" \
                "mumble_plugin/koverlay_mumble.cpp" \
                -o "mumble_plugin/koverlay_mumble.dll" \
                -lws2_32 -static-libgcc -static-libstdc++ || echo "Warning: DLL compilation failed"
        fi
    fi
    if [ -f "mumble_plugin/koverlay_mumble.dll" ] && [ -f "mumble_plugin/manifest.xml" ]; then
        (cd mumble_plugin && 7z a -tzip koverlay_mumble.mumble_plugin manifest.xml koverlay_mumble.dll koverlay_mumble.so >/dev/null 2>&1 || true)
    fi
fi

# 4. Copy application files
echo "[4/5] Copying application files..."
cp *.py "$BUNDLE_DIR/"
cp icon.png icon.ico requirements.txt "$BUNDLE_DIR/"
cp -r icons "$BUNDLE_DIR/"
if [ -d "mumble_plugin" ]; then
    cp -r mumble_plugin "$BUNDLE_DIR/"
fi

# Add launcher scripts in bundle
cat << 'EOF' > "$BUNDLE_DIR/KOverlay.bat"
@echo off
cd /d "%~dp0"
start "" "%~dp0python\pythonw.exe" "%~dp0koverlay.py" %*
EOF

cat << 'EOF' > "$BUNDLE_DIR/KOverlay_Debug.bat"
@echo off
cd /d "%~dp0"
echo ========================================================
echo   Uruchamianie KOverlay w trybie diagnostycznym (konsola)
echo ========================================================
echo.
"%~dp0python\python.exe" "%~dp0koverlay.py" %*
echo.
echo [KOverlay zakonczyl dzialanie z kodem: %ERRORLEVEL%]
pause
EOF

# 4. Generate Inno Setup Script
echo "[5/5] Compiling standalone KOverlay_Setup.exe via Inno Setup..."

cat << EOF > "$BUILD_DIR/installer.iss"
#define MyAppName "KOverlay"
#define MyAppVersion "0.1.18"
#define MyAppPublisher "Arkanis"
#define MyAppURL "https://github.com/Arkanis/KOverlay"

[Setup]
AppId={{D37E8492-23A4-4A8B-814E-4CD5093551BB}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Z:\\$OUTPUT_DIR
OutputBaseFilename=KOverlay_Setup
SetupIconFile=Z:\\$BUNDLE_DIR\\icon.ico
UninstallDisplayIcon={app}\\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "Z:\\$BUNDLE_DIR\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Z:\\$BUNDLE_DIR\\mumble_plugin\\koverlay_mumble.dll"; DestDir: "{userappdata}\\Mumble\\Mumble\\Plugins"; Flags: ignoreversion uninsneveruninstall
Source: "Z:\\$BUNDLE_DIR\\mumble_plugin\\koverlay_mumble.dll"; DestDir: "{userappdata}\\Mumble\\Plugins"; Flags: ignoreversion uninsneveruninstall
Source: "Z:\\$BUNDLE_DIR\\mumble_plugin\\koverlay_mumble.mumble_plugin"; DestDir: "{userappdata}\\Mumble\\Mumble\\Plugins"; Flags: ignoreversion uninsneveruninstall

[Icons]
Name: "{autoprograms}\\{#MyAppName}"; Filename: "{app}\\python\\pythonw.exe"; Parameters: """{app}\\koverlay.py"""; WorkingDir: "{app}"; IconFilename: "{app}\\icon.ico"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\python\\pythonw.exe"; Parameters: """{app}\\koverlay.py"""; WorkingDir: "{app}"; IconFilename: "{app}\\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\\python\\pythonw.exe"; Parameters: """{app}\\koverlay.py"""; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
EOF

ISCC_BIN="$HOME/.wine/drive_c/innosetup/ISCC.exe"
WINEDEBUG=-all wine "$ISCC_BIN" "Z:\\$BUILD_DIR\\installer.iss"

echo "=========================================================="
echo "    SUCCESS! Installer ready at: dist/KOverlay_Setup.exe  "
echo "=========================================================="
ls -lh "$OUTPUT_DIR/KOverlay_Setup.exe"
