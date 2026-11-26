# Exercise Crewden-Desktop-Setup-x64.exe per-user installation, seed extraction,
# bundled official Node 24.22.1, and DSH readiness with stripped PATH.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../../..')

$out = (Resolve-Path 'dist\desktop-windows-release').Path
$manifestPath = Join-Path $out 'manifest.desktop-win32-x64.json'
$manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
$installer = Join-Path $out 'Crewden-Desktop-Setup-x64.exe'

if ((Get-Item $installer).Length -ne $manifest.installer.size) {
    throw 'Installer size does not match manifest.desktop-win32-x64.json'
}
$actualSha = (Get-FileHash -Algorithm SHA256 $installer).Hash.ToLowerInvariant()
if ($actualSha -ne $manifest.installer.sha256) {
    throw 'Installer SHA-256 does not match manifest.desktop-win32-x64.json'
}

$proc = Start-Process -FilePath $installer -ArgumentList '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES' -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    throw "Crewden-Desktop-Setup-x64.exe failed with exit code $($proc.ExitCode)"
}

$installedExe = Join-Path $env:LOCALAPPDATA 'CrewdenDesktop\bin\CrewdenDesktop.exe'
if (!(Test-Path $installedExe)) {
    throw "Installed binary missing at $installedExe"
}
$shortcut = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Crewden Desktop.lnk'
if (!(Test-Path $shortcut)) {
    throw "Start Menu shortcut missing at $shortcut"
}
$uriCmd = (Get-Item 'HKCU:\Software\Classes\crewden-desktop\shell\open\command').GetValue('')
if (!$uriCmd.Contains('CrewdenDesktop.exe')) {
    throw "URI protocol registration unexpected: $uriCmd"
}

$tmpBase = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$isoRoot = Join-Path $tmpBase "CrewdenDesktopSmoke-$([guid]::NewGuid().ToString('N').Substring(0,8))"
New-Item -ItemType Directory -Force $isoRoot | Out-Null
$savedPath = $env:PATH
$hostProc = $null
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\Wbem;$env:SystemRoot\System32\WindowsPowerShell\v1.0"
    $errLog = Join-Path $isoRoot 'host-stderr.log'
    $hostProc = Start-Process -FilePath $installedExe -ArgumentList '--isolated-root', $isoRoot, '--headless-host' -RedirectStandardError $errLog -PassThru
    $stateFile = Join-Path $isoRoot 'desktop\host-state.json'
    $state = $null
    for ($i = 0; $i -lt 300; $i++) {
        if ($hostProc.HasExited) {
            $errText = if (Test-Path $errLog) { Get-Content -Raw $errLog } else { '' }
            throw "CrewdenDesktop headless host exited prematurely ($($hostProc.ExitCode)): $errText"
        }
        if (Test-Path $stateFile) {
            try {
                $candidate = Get-Content -Raw $stateFile | ConvertFrom-Json
                if ($candidate.ready -and $candidate.port) { $state = $candidate; break }
            } catch {}
        }
        Start-Sleep -Seconds 1
    }
    if (!$state) { throw 'CrewdenDesktop headless host did not become ready from seed archives within 300s' }

    $status = Invoke-RestMethod -Headers @{ 'x-crewden-reload-token' = $state.reload_token } -Uri "http://127.0.0.1:$($state.port)/desktop/internal/status"
    if (!$status.ready) { throw 'Desktop internal status not ready' }

    $versionRoot = Join-Path $isoRoot "desktop\versions\$($manifest.sha256)"
    $bundledNode = Join-Path $versionRoot 'runtime\node.exe'
    if (!(Test-Path $bundledNode)) { throw "Unpacked bundled node.exe missing at $bundledNode" }

    $nodeVer = (& $bundledNode -v).Trim()
    if ($nodeVer -ne 'v24.22.1') { throw "Expected bundled Node v24.22.1, got $nodeVer" }

    & $bundledNode "$versionRoot\apps\node\lib\cli.js" --help | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Bundled Node CLI failed --help' }

    $probeDir = Join-Path $isoRoot 'dsh-probe'
    New-Item -ItemType Directory -Force $probeDir | Out-Null
    Copy-Item 'packaging\windows\smoke.mjs' "$probeDir\probe.mjs" -Force
    & $bundledNode "$probeDir\probe.mjs" $versionRoot "$probeDir\home"
    if ($LASTEXITCODE -ne 0) { throw 'Bundled DSH probe failed' }

    & $installedExe '--isolated-root' $isoRoot '--stop'
    $hostProc.WaitForExit(10000) | Out-Null
} finally {
    $env:PATH = $savedPath
    if ($hostProc -and !$hostProc.HasExited) { Stop-Process -Id $hostProc.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $isoRoot -Recurse -Force -ErrorAction SilentlyContinue
}
