; Inno Setup 6 installer script for Apink 熊貓桌面寵物 (PandaDesktopPet)
; Build with: ISCC.exe installer\PandaDesktopPet.iss
; Requires PyInstaller output under ..\dist\PandaDesktopPet\ and ..\build\PandaDesktopPet.ico

#define MyAppName "Apink 熊貓桌面寵物 (PandaDesktopPet)"
#define MyAppShortName "PandaDesktopPet"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "PandaDesktopPet Project"
#define MyAppExeName "PandaDesktopPet.exe"

[Setup]
AppId={{8E9A7A5D-4C2B-4E19-9D6E-2A7F8419A011}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppShortName}
DefaultGroupName=Apink 熊貓桌面寵物
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=PandaDesktopPet-Setup
SetupIconFile=..\build\PandaDesktopPet.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=yes

[Languages]
Name: "zh_TW"; MessagesFile: "ChineseTraditional.isl"
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
zh_TW.CreateDesktopIcon=建立桌面捷徑(&D)
zh_TW.LaunchApp=立即啟動 Apink 熊貓桌寵
zh_TW.AdditionalIcons=其他捷徑:
zh_TW.UninstallShortcut=解除安裝 Apink 熊貓桌寵
ko.CreateDesktopIcon=바탕 화면 바로 가기 만들기(&D)
ko.LaunchApp=지금 Apink 판다 데스크톱 펫 실행
ko.AdditionalIcons=추가 바로 가기:
ko.UninstallShortcut=Apink 판다 데스크톱 펫 제거
en.CreateDesktopIcon=Create a &desktop shortcut
en.LaunchApp=Launch PandaDesktopPet now
en.AdditionalIcons=Additional shortcuts:
en.UninstallShortcut=Uninstall PandaDesktopPet

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Bundle the entire PyInstaller one-folder distribution (keeps _internal\assets.pak intact, no loose art files)
Source: "..\dist\PandaDesktopPet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Apink 熊貓桌面寵物 (PandaDesktopPet)"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallShortcut}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Apink 熊貓桌面寵物"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent
