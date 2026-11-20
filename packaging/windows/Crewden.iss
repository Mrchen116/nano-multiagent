[Setup]
AppId=CrewdenWindowsBootstrap
AppName=Crewden 电脑端
AppVersion=1.0
DefaultDirName={localappdata}\Crewden
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CreateAppDir=no
Uninstallable=no
DisableProgramGroupPage=yes
DisableDirPage=yes
UsePreviousLanguage=no
OutputDir=..\..\dist\windows-release
OutputBaseFilename=Crewden-Setup-x64
WizardStyle=modern
Compression=lzma2

[Files]
Source: "..\..\dist\windows-build\Crewden.exe"; Flags: dontcopy
Source: "..\..\dist\windows-build\Crewden.exe.config"; Flags: dontcopy

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ExitCode: Integer;
begin
  if CurStep = ssPostInstall then begin
    ExtractTemporaryFile('Crewden.exe');
    ExtractTemporaryFile('Crewden.exe.config');
    if not Exec(ExpandConstant('{tmp}\Crewden.exe'),
      'install "' + ExpandConstant('{srcexe}') + '"', '', SW_HIDE, ewWaitUntilTerminated, ExitCode)
      or (ExitCode <> 0) then RaiseException('未能安装 Crewden。请从原网页重新下载安装器。');
  end;
end;
procedure InitializeWizard();
begin
  WizardForm.FinishedLabel.Caption := '返回原网页，点击「连接这台电脑」。之后可从开始菜单打开 Crewden。';
end;
