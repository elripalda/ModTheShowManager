; Installer for Mod the Show Manager (Inno Setup 6). Built by CI after PyInstaller.
#define AppName "Mod the Show Manager"
#ifndef AppVersion
  #define AppVersion "0.14"
#endif

[Setup]
AppId={{6C1E2B7A-3B0E-4E5B-9B55-6D2F0C9A7E11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Ripalda
AppPublisherURL=https://www.elripalda.com
AppSupportURL=https://github.com/elripalda/ModTheShowManager
DefaultDirName={autopf}\Mod the Show Manager
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=ModTheShowManager-Setup
SetupIconFile=src\modtheshow\assets\icon.ico
UninstallDisplayIcon={app}\ModTheShowManager.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Put a shortcut on the desktop"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\ModTheShowManager.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\ModTheShowManager.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\ModTheShowManager.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ModTheShowManager.exe"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent
