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
cp icon.png icon.ico requirements.txt LICENSE "$BUNDLE_DIR/"
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
echo   Starting KOverlay in diagnostic mode (console)
echo ========================================================
echo.
"%~dp0python\python.exe" "%~dp0koverlay.py" %*
echo.
echo [KOverlay exited with code: %ERRORLEVEL%]
pause
EOF

cat << 'EOF' > "$BUNDLE_DIR/INSTALL_MUMBLE_PLUGIN.bat"
@echo off
setlocal
echo ========================================================
echo   Installing KOverlay Mumble Plugin
echo ========================================================
echo.

set "DEST=%APPDATA%\Mumble\Mumble\Plugins"
if not exist "%DEST%" (
    mkdir "%DEST%" 2>nul
)

if not exist "%~dp0mumble_plugin\koverlay_mumble.dll" (
    echo [ERROR] Plugin file koverlay_mumble.dll not found in mumble_plugin folder!
    pause
    exit /b 1
)

copy /y "%~dp0mumble_plugin\koverlay_mumble.dll" "%DEST%\" >nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Successfully installed koverlay_mumble.dll to:
    echo      %DEST%
    echo.
    echo Please restart Mumble and verify the plugin is enabled in:
    echo Settings -^> Plugins -^> KOverlay Mumble Plugin
) else (
    echo [ERROR] Failed to copy plugin. If Mumble is running, please close it and try again.
)
echo.
pause
EOF

cat << 'EOF' > "$BUNDLE_DIR/PORTABLE_README.txt"
========================================================================
                      KOverlay Portable for Windows
========================================================================

1. HOW TO RUN KOVERLAY:
   - Double-click "KOverlay.bat" inside this folder to start KOverlay
     silently in the background (using pythonw.exe).
   - An icon will appear in your Windows System Tray (near the clock).
   - Right-click the tray icon to open Settings or adjust your overlays.
   - IMPORTANT: KOverlay must remain running in the background for
     the voice overlay to appear over your games.
   - Diagnostic mode: If you ever need to view live console logs,
     run "KOverlay_Debug.bat" instead.

2. CREATING A DESKTOP SHORTCUT:
   - Right-click "KOverlay.bat" -> "Send to" -> "Desktop (create shortcut)".
   - (Optional): Right-click your new shortcut -> Properties -> "Change Icon"
     and select "icon.ico" from this folder.

3. ADDING TO WINDOWS STARTUP (AUTOSTART ON BOOT):
   - Press Win + R, type "shell:startup", and press Enter.
   - Copy and paste your desktop shortcut into that Startup folder.
   - KOverlay will now start automatically in the system tray when Windows boots.

4. FOR MUMBLE USERS:
   - Make sure Mumble is closed first.
   - Double-click "INSTALL_MUMBLE_PLUGIN.bat" to automatically copy
     "koverlay_mumble.dll" to %APPDATA%\Mumble\Mumble\Plugins.
   - Alternatively, copy "mumble_plugin\koverlay_mumble.dll" manually.
   - Restart Mumble, go to Settings -> Plugins, and make sure
     "KOverlay Mumble Plugin" is enabled.

5. FOR TEAMSPEAK 3 USERS:
   - Open TeamSpeak 3, enable ClientQuery plugin (Tools -> Options -> Addons).
   - In KOverlay Settings, choose "TeamSpeak 3" and enter your API Key.

6. FOR DISCORD USERS:
   - Ensure Discord desktop app is running.
   - In KOverlay tray icon or Settings, switch Voice Platform to "Discord".
   - When prompted by Discord, click "Authorize" to allow KOverlay to display voice channel activity.
========================================================================
EOF

# 4. Generate Inno Setup Script
VERSION=$(grep -m1 '^pkgver=' "$SCRIPT_DIR/PKGBUILD" | cut -d= -f2 | tr -d ' ')
if [ -z "$VERSION" ]; then
    VERSION="1.1.2"
fi

cat << EOF > "$BUILD_DIR/installer.iss"
#define MyAppName "KOverlay"
#define MyAppVersion "$VERSION"
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
LicenseFile=Z:\\$SCRIPT_DIR\\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "polish"; MessagesFile: "compiler:Languages\\Polish.isl"

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

[Code]
function IsProcessRunning(const ExeName: string): Boolean;
var
  ResultCode: Integer;
  Cmd: string;
begin
  Cmd := '/c tasklist /FI "IMAGENAME eq ' + ExeName + '" /NH | find /i "' + ExeName + '"';
  if Exec(ExpandConstant('{cmd}'), Cmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0)
  else
    Result := False;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  while IsProcessRunning('mumble.exe') do
  begin
    if MsgBox('Mumble is currently running and must be closed before installing KOverlay.'#13#10#13#10 +
              'Please close Mumble, then click Retry to continue (or Cancel to abort installation).',
              mbError, MB_RETRYCANCEL) = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;
  end;
end;
EOF

ISCC_BIN="$HOME/.wine/drive_c/innosetup/ISCC.exe"
WINEDEBUG=-all wine "$ISCC_BIN" "Z:\\$BUILD_DIR\\installer.iss"

# 5. Build Portable ZIP archive
echo "[5/5] Creating portable ZIP archive: dist/KOverlay_Portable.zip..."
rm -f "$OUTPUT_DIR/KOverlay_Portable.zip"
(cd "$BUILD_DIR" && 7z a -tzip -mx=7 "$OUTPUT_DIR/KOverlay_Portable.zip" ./bundle/* >/dev/null)

echo "=========================================================="
echo "    SUCCESS! Build artifacts ready at: $OUTPUT_DIR        "
echo "=========================================================="
ls -lh "$OUTPUT_DIR/KOverlay_Setup.exe" "$OUTPUT_DIR/KOverlay_Portable.zip"
