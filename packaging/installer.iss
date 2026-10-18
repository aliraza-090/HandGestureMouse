; Inno Setup script for HandGestureMouse.
;
; Prerequisites:
;   * Build the folder distribution first:
;       pyinstaller packaging\HandGestureMouse.spec --noconfirm --clean
;     which produces dist\HandGestureMouse\HandGestureMouse.exe
;   * Inno Setup 6 (ISCC.exe) installed: https://jrsoftware.org/isdl.php
;
; Build the installer:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
;
; The resulting installer is written to packaging\Output\HandGestureMouse-Setup.exe

#define MyAppName "HandGestureMouse"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Ali Raza Chakrani"
#define MyAppExeName "HandGestureMouse.exe"
#define MyAppId "{{A1F6B7E2-6C41-4E9B-9E2A-1B0F5D9C7A31}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=HandGestureMouse-Setup
SetupIconFile=..\src\handgesturemouse\resources\icons\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Ship the whole PyInstaller folder build.
Source: "..\dist\HandGestureMouse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Settings and logs live in %APPDATA%\HandGestureMouse and are intentionally
; left in place on uninstall. Remove the next line's comment to delete them.
; Type: filesandordirs; Name: "{userappdata}\HandGestureMouse"