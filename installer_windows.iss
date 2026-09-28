; Inno Setup Script for KOverlay
; Generates a single-file setup wizard: KOverlay_Setup.exe

#define MyAppName "KOverlay"
#define MyAppVersion "0.1.19"
#define MyAppPublisher "Arkanis"
#define MyAppURL "https://github.com/Arkanis/KOverlay"
#define MyAppExeName "koverlay.py"

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
OutputDir=.
OutputBaseFilename=KOverlay_Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "*.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "installer_windows.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "mumble_plugin\*"; DestDir: "{app}\mumble_plugin"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "mumble_plugin\koverlay_mumble.dll"; DestDir: "{userappdata}\Mumble\Plugins"; Flags: ignoreversion uninsneveruninstall; Check: DirExists(ExpandConstant('{userappdata}\Mumble'))

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "wscript.exe"; Parameters: """{app}\launch.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "wscript.exe"; Parameters: """{app}\launch.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer_windows.ps1"""; StatusMsg: "Configuring Python and installing required packages (PyQt6, ts3, edge-tts)..."; Flags: runhidden
Filename: "wscript.exe"; Parameters: """{app}\launch.vbs"""; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
