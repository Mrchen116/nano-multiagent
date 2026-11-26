# Build Crewden Desktop Windows x64 installer (Crewden-Desktop-Setup-x64.exe) and split archives.
param(
    [string]$Version = $env:RELEASE_VERSION,
    [string]$SourceCommit = '',
    [string]$BaseUrl = '',
    [string]$OutDir = 'dist\desktop-windows-release',
    [string]$ExtraAppNote = '',
    [switch]$SkipHostTests
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

function Checked([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "$exe exited with $LASTEXITCODE" }
}

$build = 'dist\desktop-windows-build'
$seedDir = Join-Path $build 'seed-archives'
New-Item -ItemType Directory -Force $build, $seedDir, $OutDir | Out-Null

if (!(Test-Path 'src\IM\frontend\dist\index.html')) {
    if (!(Test-Path 'src\IM\frontend\node_modules')) {
        Checked 'npm.cmd' @('--prefix', 'src/IM/frontend', 'ci')
    }
    Checked 'npm.cmd' @('--prefix', 'src/IM/frontend', 'run', 'build')
}

if (!(Test-Path 'apps\node\lib\cli.js') -or !(Test-Path 'packages\dsh-trajectory-viewer\dist\index.html')) {
    Checked 'pnpm.cmd' @('build')
}

$csc = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$ref = @(
    '/nologo', '/platform:x64', '/optimize+', '/codepage:65001',
    '/r:System.Web.Extensions.dll', '/r:System.Windows.Forms.dll',
    '/r:Microsoft.CSharp.dll', '/r:System.Management.dll'
)
Checked $csc ($ref + @('/target:winexe', "/out:$build\DesktopGatewayHost.exe", 'packaging\desktop\windows\DesktopGatewayHost.cs'))
Copy-Item "$build\DesktopGatewayHost.exe" 'apps\node\lib\DesktopGatewayHost.exe' -Force

if (!$SkipHostTests) {
    if (Test-Path 'packaging\windows-host\GatewayHost.cs') {
        New-Item -ItemType Directory -Force 'dist\windows-build' | Out-Null
        Checked $csc ($ref + @('/target:winexe', '/out:dist\windows-build\GatewayHost.exe', 'packaging\windows-host\GatewayHost.cs'))
    }
    Checked 'node' @('--test', 'apps/node/tests/desktop-windows-host.test.mjs')
    Checked 'cargo' @('test', '--manifest-path', 'apps/desktop/Cargo.toml')
}

if (!(Test-Path 'apps\desktop\target\release\crewden-desktop.exe')) {
    Checked 'cargo' @('build', '--manifest-path', 'apps/desktop/Cargo.toml', '--release')
}
Copy-Item 'apps\desktop\target\release\crewden-desktop.exe' "$build\CrewdenDesktop.exe" -Force

$wv2Bootstrapper = Join-Path $build 'MicrosoftEdgeWebView2Setup.exe'
if (!(Test-Path $wv2Bootstrapper)) {
    Checked 'curl.exe' @(
        '--proto', '=https', '--proto-redir', '=https', '--retry', '3',
        '-fsSL', 'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
        '-o', $wv2Bootstrapper
    )
    if ((Get-Item $wv2Bootstrapper).Length -lt 500KB) {
        throw 'Downloaded MicrosoftEdgeWebView2Setup.exe is unexpectedly small'
    }
}

$placeholderInstaller = Join-Path $build 'placeholder-setup.exe'
Copy-Item "$build\CrewdenDesktop.exe" $placeholderInstaller -Force

$pyArgs = @(
    'scripts/build-desktop-archives.py',
    '--platform', 'desktop-win32-x64',
    '--out-dir', $seedDir,
    '--installer', $placeholderInstaller
)
if ($Version) { $pyArgs += @('--version', $Version) }
if ($SourceCommit) { $pyArgs += @('--source-commit', $SourceCommit) }
if ($BaseUrl) { $pyArgs += @('--base-url', $BaseUrl) }
if ($ExtraAppNote) { $pyArgs += @('--extra-app-note', $ExtraAppNote) }
Checked 'python' $pyArgs

$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (!(Test-Path $iscc)) {
    $iscc = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
}
if (!(Test-Path $iscc)) {
    throw 'Inno Setup 6 (ISCC.exe) was not found'
}
$appVer = if ($Version -and $Version -match '^[0-9]+\.[0-9]+\.[0-9]+$') { $Version } else { '1.0.0' }
$resolvedOut = (Resolve-Path $OutDir).Path
Checked $iscc @("/DMyAppVersion=$appVer", "/O$resolvedOut", 'packaging\desktop\windows\CrewdenDesktop.iss')

$finalExe = Join-Path $resolvedOut 'Crewden-Desktop-Setup-x64.exe'
if (!(Test-Path $finalExe)) {
    throw "Expected installer output missing: $finalExe"
}

foreach ($assetName in @('desktop-runtime-win32-x64.tar.gz', 'desktop-app-win32-x64.tar.gz', 'desktop-win32-x64.json')) {
    Copy-Item (Join-Path $seedDir $assetName) (Join-Path $resolvedOut $assetName) -Force
}

$installerHash = (Get-FileHash -Algorithm SHA256 $finalExe).Hash.ToLowerInvariant()
$installerSize = (Get-Item $finalExe).Length
$manifestObj = Get-Content -Raw (Join-Path $seedDir 'manifest.desktop-win32-x64.json') | ConvertFrom-Json
$manifestObj.installer.sha256 = $installerHash
$manifestObj.installer.size = $installerSize
$manifestJson = ($manifestObj | ConvertTo-Json -Depth 6) + "`n"
[System.IO.File]::WriteAllText((Join-Path $resolvedOut 'manifest.desktop-win32-x64.json'), $manifestJson, [System.Text.UTF8Encoding]::new($false))
