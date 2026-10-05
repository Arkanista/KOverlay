# KOverlay Windows Automated Installer
# Supports Windows 10 and 11 (64-bit)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "            KOverlay - Windows Installer                  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

function Get-PythonPath {
    # 1. Check if python is in PATH
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $ver = & $cmd.Source --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                $major = [int]$matches[1]
                $minor = [int]$matches[2]
                if ($major -eq 3 -and $minor -ge 8) {
                    return $cmd.Source
                }
            }
        } catch {}
    }

    # 2. Check Python Launcher (py.exe)
    $pyCmd = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCmd) {
        try {
            $path = & $pyCmd.Source -3 -c "import sys; print(sys.executable)" 2>&1
            if ($path -and (Test-Path $path.Trim())) {
                return $path.Trim()
            }
        } catch {}
    }

    # 3. Check common installation directories
    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe"
    )
    foreach ($p in $commonPaths) {
        if (Test-Path $p) {
            return $p
        }
    }

    return $null
}

# -------------------------------------------------------------
# 1. Detect or Install Python
# -------------------------------------------------------------
Write-Host "[1/6] Checking Python installation..." -ForegroundColor Yellow
$pythonExe = Get-PythonPath

if ($pythonExe) {
    $verText = & $pythonExe --version 2>&1
    Write-Host "[OK] Found $verText at: $pythonExe" -ForegroundColor Green
} else {
    Write-Host "[!] Python 3.8+ not detected on your system." -ForegroundColor Yellow
    Write-Host "[+] Automatically installing Python 3.11 (64-bit)..." -ForegroundColor Cyan

    $pythonInstalled = $false

    # Attempt 1: winget (built into modern Windows 10/11)
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "    -> Attempting installation via winget..." -ForegroundColor Gray
        try {
            Start-Process -FilePath "winget.exe" -ArgumentList "install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements" -Wait -NoNewWindow
            $pythonExe = Get-PythonPath
            if ($pythonExe) { $pythonInstalled = $true }
        } catch {}
    }

    # Attempt 2: Direct download from python.org
    if (-not $pythonInstalled) {
        $installerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $installerPath = "$env:TEMP\python-3.11.9-amd64.exe"
        Write-Host "    -> Downloading Python 3.11 installer from python.org..." -ForegroundColor Gray
        
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing

        Write-Host "    -> Running silent Python setup..." -ForegroundColor Gray
        $proc = Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 SimpleInstall=1" -Wait -PassThru
        
        Remove-Item -Path $installerPath -Force -ErrorAction SilentlyContinue

        # Refresh environment PATH for current session
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        $env:Path = "$userPath;$machinePath;$env:LOCALAPPDATA\Programs\Python\Python311;$env:LOCALAPPDATA\Programs\Python\Python311\Scripts"

        $pythonExe = Get-PythonPath
        if (-not $pythonExe) {
            $candidate = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
            if (Test-Path $candidate) {
                $pythonExe = $candidate
            }
        }
    }

    if ($pythonExe) {
        Write-Host "[OK] Python installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Could not automatically install Python." -ForegroundColor Red
        Write-Host "Please install Python 3.10+ manually from https://www.python.org/downloads/ (make sure to check 'Add Python to PATH') and re-run this installer."
        Exit 1
    }
}

# -------------------------------------------------------------
# 2. Setup Application Files in %LOCALAPPDATA%\Programs\KOverlay
# -------------------------------------------------------------
$InstallDir = "$env:LOCALAPPDATA\Programs\KOverlay"
Write-Host "`n[2/6] Installing KOverlay to: $InstallDir" -ForegroundColor Yellow

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Copy files
Get-ChildItem -Path $ScriptDir -Filter "*.py" | Copy-Item -Destination $InstallDir -Force
Get-ChildItem -Path $ScriptDir -Filter "*.txt" | Copy-Item -Destination $InstallDir -Force

if (Test-Path "$ScriptDir\icon.png") { Copy-Item "$ScriptDir\icon.png" -Destination $InstallDir -Force }
if (Test-Path "$ScriptDir\icon.ico") { Copy-Item "$ScriptDir\icon.ico" -Destination $InstallDir -Force }

if (Test-Path "$ScriptDir\icons") {
    Copy-Item -Path "$ScriptDir\icons" -Destination $InstallDir -Recurse -Force
}
if (Test-Path "$ScriptDir\mumble_plugin") {
    Copy-Item -Path "$ScriptDir\mumble_plugin" -Destination $InstallDir -Recurse -Force
}

# -------------------------------------------------------------
# 3. Create Python Virtual Environment (venv)
# -------------------------------------------------------------
$venvDir = "$InstallDir\venv"
Write-Host "`n[3/6] Setting up isolated Python virtual environment..." -ForegroundColor Yellow

if (-not (Test-Path "$venvDir\Scripts\python.exe")) {
    & $pythonExe -m venv $venvDir
}

$venvPython = "$venvDir\Scripts\python.exe"
$venvPythonW = "$venvDir\Scripts\pythonw.exe"

# -------------------------------------------------------------
# 4. Install Required Packages (PyQt6, ts3, edge-tts)
# -------------------------------------------------------------
Write-Host "`n[4/6] Installing required Python packages (PyQt6, ts3, edge-tts)..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r "$InstallDir\requirements.txt" --quiet

# -------------------------------------------------------------
# 5. Create Launchers & Shortcuts
# -------------------------------------------------------------
Write-Host "`n[5/6] Creating launchers and shortcuts..." -ForegroundColor Yellow

# 5a. VBS launcher (runs silently without a console window)
$vbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$InstallDir"
WshShell.Run """$venvPythonW"" ""$InstallDir\koverlay.py""", 0, False
"@
Set-Content -Path "$InstallDir\launch.vbs" -Value $vbsContent -Encoding ASCII

# 5b. BAT launcher (optional alternative)
$batContent = @"
@echo off
cd /d "%~dp0"
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0koverlay.py" %*
"@
Set-Content -Path "$InstallDir\start.bat" -Value $batContent -Encoding ASCII

# 5c. Windows Shortcuts (Desktop & Start Menu)
$WshShell = New-Object -ComObject WScript.Shell
$iconLocation = "$InstallDir\icon.ico"
if (-not (Test-Path $iconLocation)) {
    $iconLocation = "$venvPythonW,0"
}

# Desktop Shortcut
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutDesktop = $WshShell.CreateShortcut("$DesktopPath\KOverlay.lnk")
$ShortcutDesktop.TargetPath = "wscript.exe"
$ShortcutDesktop.Arguments = "`"$InstallDir\launch.vbs`""
$ShortcutDesktop.WorkingDirectory = $InstallDir
$ShortcutDesktop.IconLocation = "$iconLocation, 0"
$ShortcutDesktop.Description = "KOverlay Voice Overlay for TeamSpeak 3 and Mumble"
$ShortcutDesktop.Save()

# Start Menu Shortcut
$StartMenuPrograms = [Environment]::GetFolderPath("Programs")
$ShortcutStart = $WshShell.CreateShortcut("$StartMenuPrograms\KOverlay.lnk")
$ShortcutStart.TargetPath = "wscript.exe"
$ShortcutStart.Arguments = "`"$InstallDir\launch.vbs`""
$ShortcutStart.WorkingDirectory = $InstallDir
$ShortcutStart.IconLocation = "$iconLocation, 0"
$ShortcutStart.Description = "KOverlay Voice Overlay for TeamSpeak 3 and Mumble"
$ShortcutStart.Save()

# -------------------------------------------------------------
# 6. Create Uninstaller & Register in Windows Settings
# -------------------------------------------------------------
Write-Host "`n[6/6] Registering uninstaller..." -ForegroundColor Yellow

$uninstallBatContent = @"
@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Uninstalling KOverlay...
echo ===================================================

:: Terminate running instance if any
powershell -NoProfile -Command "Get-Process -Name pythonw,python -ErrorAction SilentlyContinue | Where-Object { `$_.Path -like '*KOverlay*' } | Stop-Process -Force" >nul 2>&1

:: Remove shortcuts
del /f /q "%USERPROFILE%\Desktop\KOverlay.lnk" >nul 2>&1
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\KOverlay.lnk" >nul 2>&1

:: Remove Registry entry
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\KOverlay" /f >nul 2>&1

echo KOverlay has been uninstalled.
echo Cleaning up files...
start /b "" cmd /c "timeout /t 1 /nobreak >nul & rd /s /q \"%~dp0\""
exit
"@
Set-Content -Path "$InstallDir\uninstall_windows.bat" -Value $uninstallBatContent -Encoding ASCII

# Register in Windows Add/Remove Programs (HKCU)
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\KOverlay"
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}
Set-ItemProperty -Path $regPath -Name "DisplayName" -Value "KOverlay"
Set-ItemProperty -Path $regPath -Name "DisplayVersion" -Value "1.1.2"
Set-ItemProperty -Path $regPath -Name "Publisher" -Value "Arkanis"
Set-ItemProperty -Path $regPath -Name "DisplayIcon" -Value "$iconLocation"
Set-ItemProperty -Path $regPath -Name "UninstallString" -Value "`"$InstallDir\uninstall_windows.bat`""
Set-ItemProperty -Path $regPath -Name "InstallLocation" -Value "$InstallDir"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "       KOverlay has been installed successfully!          " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "A shortcut has been placed on your Desktop and in the Start Menu."
Write-Host "You can also manage or uninstall KOverlay from Windows Settings -> Installed Apps."
Write-Host ""

# Ask to launch
$response = Read-Host "Would you like to start KOverlay now? (Y/N)"
if ($response -match "^[yYtT1]") {
    Start-Process "wscript.exe" -ArgumentList "`"$InstallDir\launch.vbs`"" -WorkingDirectory $InstallDir
}
