# The runner is disposable. Use the real per-user shell registration and install layout.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
$build = (Resolve-Path 'dist/windows-build').Path
$out = (Resolve-Path 'dist/windows-release').Path
$manifestFile = "$out/manifest.win32-x64.json"
$m = Get-Content -Raw $manifestFile | ConvertFrom-Json
$installer = "$out/Crewden-Setup-x64.exe"
$process = Start-Process -FilePath $installer -ArgumentList '/VERYSILENT','/NORESTART','/SUPPRESSMSGBOXES' -Wait -PassThru
if ($process.ExitCode) { throw "Installer failed: $($process.ExitCode)" }
$command = (Get-Item 'HKCU:/Software/Classes/crewden/shell/open/command').GetValue('')
if (!$command.Contains($m.installer.sha256)) { throw 'URI registration did not select the actual installer SHA' }
$csc = Join-Path $env:SystemRoot 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
& $csc /nologo /target:exe /platform:x64 /codepage:65001 /main:Smoke "/out:$build/Smoke.exe" /r:System.Web.Extensions.dll /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:Microsoft.CSharp.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll packaging/windows/Package.cs packaging/windows/Launcher.cs packaging/windows/Smoke.cs
if ($LASTEXITCODE) { throw 'Smoke driver failed to build' }
Copy-Item "$build/Crewden.exe.config" "$build/Smoke.exe.config" -Force
$server = Start-Process -FilePath (Get-Command python).Source -ArgumentList '-m','http.server','8129','--bind','127.0.0.1' -WorkingDirectory $out -NoNewWindow -PassThru
try {
    for ($i = 0; $i -lt 20; $i++) {
        try { Invoke-WebRequest -Uri 'http://127.0.0.1:8129/windows-x64.json' -TimeoutSec 2 | Out-Null; break }
        catch { Start-Sleep -Milliseconds 300 }
    }
    & "$build/Smoke.exe" $manifestFile 'http://127.0.0.1:8129/'
    if ($LASTEXITCODE) { throw 'Native archive preparation failed' }
} finally { Stop-Process -Id $server.Id -Force }
# Warm preparation must succeed with no asset server running.
& "$build/Smoke.exe" $manifestFile 'http://127.0.0.1:8129/'
if ($LASTEXITCODE) { throw 'Warm prepare unexpectedly required an asset' }
$version = Join-Path $env:LOCALAPPDATA "Crewden/versions/$($m.sha256)"
$drive = Join-Path $env:RUNNER_TEMP 'Crewden 测试 电脑'
New-Item -Type Directory -Force $drive | Out-Null
Copy-Item packaging/windows/smoke.mjs "$drive/probe.mjs"
Push-Location $drive
try {
    & "$version/runtime/node.exe" "$version/apps/node/lib/cli.js" --help
    if ($LASTEXITCODE) { throw 'Private Node CLI did not load' }
    & "$version/runtime/node.exe" "$version/runtime/tooling/node_modules/pnpm/bin/pnpm.cjs" --version
    if ($LASTEXITCODE) { throw 'Private pnpm did not load' }
    & "$version/runtime/node.exe" "$drive/probe.mjs" $version "$drive/DSH 用户"
    if ($LASTEXITCODE) { throw 'Installed DSH did not respond' }
} finally { Pop-Location }
