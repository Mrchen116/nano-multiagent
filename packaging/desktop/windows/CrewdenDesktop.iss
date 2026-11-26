#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{7D9E4A21-6C15-4D88-9E23-4B0F8819C790}
AppName=Crewden Desktop
AppVersion={#MyAppVersion}
AppPublisher=Crewden
DefaultDirName={localappdata}\CrewdenDesktop\bin
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
DisableProgramGroupPage=yes
DisableDirPage=yes
UsePreviousLanguage=no
SetupIconFile=..\..\..\apps\desktop\icons\icon.ico
UninstallDisplayIcon={app}\CrewdenDesktop.exe
OutputDir=..\..\..\dist\desktop-windows-release
OutputBaseFilename=Crewden-Desktop-Setup-x64
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=no

[Files]
Source: "..\..\..\dist\desktop-windows-build\CrewdenDesktop.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\..\dist\desktop-windows-build\seed-archives\manifest.desktop-win32-x64.json"; DestDir: "{app}\seed-archives"; Flags: ignoreversion
Source: "..\..\..\dist\desktop-windows-build\seed-archives\desktop-win32-x64.json"; DestDir: "{app}\seed-archives"; Flags: ignoreversion
Source: "..\..\..\dist\desktop-windows-build\seed-archives\desktop-runtime-win32-x64.tar.gz"; DestDir: "{app}\seed-archives"; Flags: ignoreversion nocompression
Source: "..\..\..\dist\desktop-windows-build\seed-archives\desktop-app-win32-x64.tar.gz"; DestDir: "{app}\seed-archives"; Flags: ignoreversion nocompression
Source: "..\..\..\dist\desktop-windows-build\MicrosoftEdgeWebView2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{userprograms}\Crewden Desktop"; Filename: "{app}\CrewdenDesktop.exe"; WorkingDir: "{app}"; AppUserModelID: "work.crewden.desktop"; Comment: "Crewden Desktop 工作台与本机助手管理"

[Registry]
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\work.crewden.desktop"; ValueType: string; ValueName: "DisplayName"; ValueData: "Crewden"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\work.crewden.desktop"; ValueType: string; ValueName: "IconBackgroundColor"; ValueData: "0"
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\work.crewden.desktop"; ValueType: string; ValueName: "IconUri"; ValueData: "{app}\CrewdenDesktop.exe"
Root: HKCU; Subkey: "Software\Classes\crewden-desktop"; ValueType: string; ValueName: ""; ValueData: "URL:Crewden Desktop"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\crewden-desktop"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\crewden-desktop\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\CrewdenDesktop.exe"",0"
Root: HKCU; Subkey: "Software\Classes\crewden-desktop\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\CrewdenDesktop.exe"" ""%1"""

[Run]
Filename: "{app}\CrewdenDesktop.exe"; Description: "立即启动 Crewden Desktop"; Flags: nowait postinstall skipifsilent

[Code]
function IsWebView2Installed(): Boolean;
var
  Version: String;
begin
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExitCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not IsWebView2Installed()) then begin
    ExtractTemporaryFile('MicrosoftEdgeWebView2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebView2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
      RaiseException('未能完成 Microsoft Edge WebView2 运行环境安装（错误码 ' + IntToStr(ExitCode) + '）。请检查网络连接后重试。');
  end;
end;

[Messages]
FinishedLabelNoIcons=Crewden Desktop 已安装完成。打开后登录你的 IM 账号即可一键启用这台电脑的助手。
FinishedLabel=Crewden Desktop 已安装完成。打开后登录你的 IM 账号即可一键启用这台电脑的助手。
