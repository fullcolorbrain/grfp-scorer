; installer/grfp_scorer.iss — Inno Setup 6 script for GRFP Scorer (Windows).
; Shows the Apache license (must be accepted) and the disclaimer before installing.
; Built by installer/build_windows.ps1:   ISCC.exe /DAppVersion=1.1.0 installer\grfp_scorer.iss

#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{C3377F17-1320-4FE0-8893-37A544F00D17}
AppName=GRFP Scorer
AppVersion={#AppVersion}
AppPublisher=Vincent D. Costa
AppPublisherURL=https://fullcolorbrain.com
AppSupportURL=https://github.com/fullcolorbrain/grfp-scorer/issues
DefaultDirName={autopf}\GRFP Scorer
DefaultGroupName=GRFP Scorer
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=GRFP-Scorer-Setup-{#AppVersion}
LicenseFile=..\LICENSE
InfoBeforeFile=..\DISCLAIMER.md
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\GRFP Scorer.exe
#if FileExists("icon\grfp_icon.ico")
SetupIconFile=icon\grfp_icon.ico
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\GRFP Scorer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\DISCLAIMER.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\PRIVACY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\USER_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\GRFP Scorer"; Filename: "{app}\GRFP Scorer.exe"
Name: "{group}\User Guide"; Filename: "{app}\USER_GUIDE.md"
Name: "{autodesktop}\GRFP Scorer"; Filename: "{app}\GRFP Scorer.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\GRFP Scorer.exe"; Description: "Launch GRFP Scorer"; Flags: nowait postinstall skipifsilent
