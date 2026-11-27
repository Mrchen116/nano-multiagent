#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{7D9E4A21-6C15-4D88-9E23-4B0F8819C790}
AppName=Crewden Desktop
AppVersion={#MyAppVersion}
AppPublisher=Crewden
CloseApplications=yes
CloseApplicationsFilter=*.exe
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

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "附加快捷方式:"

[InstallDelete]
Type: files; Name: "{app}\seed-archives\desktop-defaults.json"
Type: files; Name: "{code:DesktopHome}\desktop-defaults.json"

[Files]
Source: "..\..\..\dist\desktop-windows-build\DesktopGatewayHost.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\..\dist\desktop-windows-build\CrewdenDesktop.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\..\apps\desktop\icons\128x128.png"; DestDir: "{app}"; DestName: "crewden-toast-icon.png"; Flags: ignoreversion
Source: "..\..\..\dist\desktop-windows-build\seed-archives\manifest.desktop-win32-x64.json"; DestDir: "{app}\seed-archives"; Flags: ignoreversion
Source: "..\..\..\dist\desktop-windows-build\seed-archives\desktop-win32-x64.json"; DestDir: "{app}\seed-archives"; Flags: ignoreversion
Source: "..\..\..\dist\desktop-windows-build\seed-archives\desktop-defaults.json"; DestDir: "{app}\seed-archives"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\..\dist\desktop-windows-build\seed-archives\desktop-defaults.json"; DestDir: "{code:DesktopHome}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\..\dist\desktop-windows-build\seed-archives\desktop-runtime-win32-x64.tar.gz"; DestDir: "{app}\seed-archives"; Flags: ignoreversion nocompression
Source: "..\..\..\dist\desktop-windows-build\seed-archives\desktop-app-win32-x64.tar.gz"; DestDir: "{app}\seed-archives"; Flags: ignoreversion nocompression
Source: "..\..\..\dist\desktop-windows-build\MicrosoftEdgeWebView2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{userprograms}\Crewden Desktop"; Filename: "{app}\CrewdenDesktop.exe"; WorkingDir: "{app}"; AppUserModelID: "work.crewden.desktop"; Comment: "Crewden Desktop 工作台与本机助手管理"
Name: "{userdesktop}\Crewden Desktop"; Filename: "{app}\CrewdenDesktop.exe"; WorkingDir: "{app}"; AppUserModelID: "work.crewden.desktop"; Tasks: desktopicon; Comment: "Crewden Desktop 工作台与本机助手管理"

[Registry]
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\work.crewden.desktop"; ValueType: string; ValueName: "DisplayName"; ValueData: "Crewden"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\work.crewden.desktop"; ValueType: string; ValueName: "IconBackgroundColor"; ValueData: "0"
Root: HKCU; Subkey: "Software\Classes\AppUserModelId\work.crewden.desktop"; ValueType: string; ValueName: "IconUri"; ValueData: "{app}\crewden-toast-icon.png"
Root: HKCU; Subkey: "Software\Classes\crewden-desktop"; ValueType: string; ValueName: ""; ValueData: "URL:Crewden Desktop"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\crewden-desktop"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\crewden-desktop\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\CrewdenDesktop.exe"",0"
Root: HKCU; Subkey: "Software\Classes\crewden-desktop\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\CrewdenDesktop.exe"" ""%1"""

[Run]
Filename: "{app}\CrewdenDesktop.exe"; Description: "立即启动 Crewden Desktop"; Flags: nowait postinstall skipifsilent

[Code]
var
  ReplacePrivateSeed: Boolean;

function DesktopHome(Param: String): String;
begin
  Result := GetEnv('CREWDEN_DESKTOP_HOME');
  if Result = '' then Result := ExpandConstant('{localappdata}\CrewdenDesktop');
end;

procedure CurUninstallStepChanged(Step: TUninstallStep);
var
  ExitCode: Integer;
  RunKey, RunValue, AppExe: String;
begin
  if Step <> usUninstall then Exit;
  AppExe := ExpandConstant('{app}\CrewdenDesktop.exe');
  if not Exec(ExpandConstant('{app}\DesktopGatewayHost.exe'),
      'uninstall "' + AppExe + '" "' + DesktopHome('') + '"', '', SW_HIDE, ewWaitUntilTerminated, ExitCode)
      or (ExitCode <> 0) then begin
    SuppressibleMsgBox('未能停止桌面后台服务。请等待电脑端更新结束后重试卸载。', mbError, MB_OK, IDOK);
    Abort;
  end;
  RunKey := 'Software\Microsoft\Windows\CurrentVersion\Run';
  if RegQueryStringValue(HKCU, RunKey, 'CrewdenDesktop', RunValue) and
      (CompareText(RunValue, '"' + AppExe + '" --background') = 0) then
    if not RegDeleteValue(HKCU, RunKey, 'CrewdenDesktop') then begin
      SuppressibleMsgBox('未能移除 Crewden Desktop 登录启动项。', mbError, MB_OK, IDOK);
      Abort;
    end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  InstalledExe: String;
  ExitCode: Integer;
begin
  Result := '';
  InstalledExe := ExpandConstant('{app}\CrewdenDesktop.exe');
  ReplacePrivateSeed := FileExists(ExpandConstant('{app}\seed-archives\desktop-defaults.json')) and
      FileExists(DesktopHome('') + '\seed-current.json');
  if FileExists(InstalledExe) then begin
    if not Exec(InstalledExe, '--stop', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ExitCode)
        or (ExitCode <> 0) then begin
      Result := '未能停止已安装的桌面客户端。';
      Exit;
    end;
    ExtractTemporaryFile('DesktopGatewayHost.exe');
    if not Exec(ExpandConstant('{tmp}\DesktopGatewayHost.exe'),
        'prepare-overwrite "' + InstalledExe + '" "' + DesktopHome('') + '"', '', SW_HIDE, ewWaitUntilTerminated, ExitCode)
        or (ExitCode <> 0) then Result := '未能停止桌面后台服务。请等待电脑端更新结束后重试。';
  end;
end;

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
  if (CurStep = ssPostInstall) and ReplacePrivateSeed then begin
    if not Exec(ExpandConstant('{app}\CrewdenDesktop.exe'), '--prepare-seed', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ExitCode)
        or (ExitCode <> 0) then RaiseException('未能切换到新安装包内置的发布源。');
  end;
  if (CurStep = ssPostInstall) and (not IsWebView2Installed()) then begin
    ExtractTemporaryFile('MicrosoftEdgeWebView2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebView2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
      RaiseException('未能完成 Microsoft Edge WebView2 运行环境安装（错误码 ' + IntToStr(ExitCode) + '）。请检查网络连接后重试。');
  end;
end;

[Messages]
FinishedLabelNoIcons=Crewden Desktop 已安装完成。打开后登录你的 IM 账号即可一键启用这台电脑的助手。
FinishedLabel=Crewden Desktop 已安装完成。打开后登录你的 IM 账号即可一键启用这台电脑的助手。
