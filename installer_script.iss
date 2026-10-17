; Script generated for Inno Setup 6 / 7
; AirBridge - Next-Generation Local AirDrop & Universal Clipboard Hub
; Architected by Chathunga Bimsara

#define MyAppName "AirBridge"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Chathunga Bimsara"
#define MyAppURL "https://github.com/chathunga2007/AirBridge-Cross-Platform-File-Sharing-and-Universal-Clipboard-App"
#define MyAppExeName "AirBridge.exe"

[Setup]
; Basic Application Identity
AppId={{C78E4B19-F284-4821-B076-92F6B84A1A3B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation Target Paths
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Packaging and Output
OutputDir=.
OutputBaseFilename=AirBridge-Setup-v{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
LicenseFile=LICENSE

; Permissions (Installs cleanly without requiring administrator elevation)
PrivilegesRequiredOverridesAllowed=dialog commandline

; Visual Customizations
WizardSizePercent=100
UninstallDisplayIcon={app}\assets\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "shellexplorer"; Description: "Add 'Beam with AirBridge' to Windows Explorer right-click menu"; GroupDescription: "Windows Integration:"; Flags: checkedonce
Name: "autostart"; Description: "Start AirBridge automatically when Windows starts (System Tray)"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\AirBridge\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\AirBridge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\AirBridge-Icon.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"; AppUserModelID: "chathunga.airbridge.hub.v2"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\icon.ico"; AppUserModelID: "chathunga.airbridge.hub.v2"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart; IconFilename: "{app}\assets\icon.ico"

[Registry]
; Windows Explorer File Right-Click Context Menu ("Beam with AirBridge")
Root: HKCU; Subkey: "Software\Classes\*\shell\AirBridge"; ValueType: string; ValueData: "Beam with AirBridge"; Tasks: shellexplorer; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\AirBridge"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\icon.ico"""; Tasks: shellexplorer; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\*\shell\AirBridge\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: shellexplorer; Flags: uninsdeletekey

; Windows Explorer Folder Right-Click Context Menu ("Beam with AirBridge")
Root: HKCU; Subkey: "Software\Classes\Directory\shell\AirBridge"; ValueType: string; ValueData: "Beam with AirBridge"; Tasks: shellexplorer; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\AirBridge"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\assets\icon.ico"""; Tasks: shellexplorer; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Directory\shell\AirBridge\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: shellexplorer; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
