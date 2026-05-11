; setup.iss — Inno Setup installer script for AutoTyper v2.0
;
; Requirements: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Build:  1. Run build.bat to produce dist\AutoTyper.exe
;         2. Open this file in Inno Setup Compiler and press F9
; Output: installer\AutoTyper_Setup.exe

#define AppName      "AutoTyper"
#define AppVersion   "2.0.0"
#define AppPublisher "u-pawan"
#define AppURL       "https://github.com/u-pawan/auto_typer"
#define AppExeName   "AutoTyper.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=AutoTyper_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}";    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupentry";   Description: "Launch AutoTyper at Windows startup"; GroupDescription: "System:"; Flags: unchecked

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";                Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";     Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";       Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Startup entry (only if user selected the task)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupentry

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove data directory on uninstall (optional — comment out to keep user data)
; Type: filesandordirs; Name: "{userappdata}\AutoTyper"
