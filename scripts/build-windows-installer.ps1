# Build against the exact locked dependency tree installed on a native Windows x64 runner.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
function Checked([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "$exe exited with $LASTEXITCODE" }
}
$build = 'dist/windows-build'
$out = 'dist/windows-release'
New-Item -ItemType Directory -Force $build,$out | Out-Null
$csc = Join-Path $env:SystemRoot 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$ref = @('/nologo','/platform:x64','/optimize+','/codepage:65001','/r:System.Web.Extensions.dll',
    '/r:System.Windows.Forms.dll','/r:Microsoft.CSharp.dll','/r:System.Management.dll')
$launcher = @('/r:System.IO.Compression.dll','/r:System.IO.Compression.FileSystem.dll','/r:System.Drawing.dll',
    'packaging/windows/Package.cs','packaging/windows/Launcher.cs')
Checked $csc ($ref + @('/target:winexe',"/out:$build/Crewden.exe") + $launcher)
Copy-Item packaging/windows/Crewden.exe.config $build -Force
Checked $csc ($ref + @('/target:winexe',"/out:$build/GatewayHost.exe",'packaging/windows-host/GatewayHost.cs'))
Checked 'node' @('--test','apps/node/tests/windows-host.test.mjs')
$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe'
Checked $iscc @('packaging/windows/Crewden.iss')
if ((Get-Item "$out/Crewden-Setup-x64.exe").Length -gt 5MB) { throw 'Installer exceeded the 5 MiB budget' }
New-Item -ItemType Directory -Force "$build/pnpm" | Out-Null
# npm verifies the tarball's registry integrity. No package manager is needed on the customer PC.
Checked 'npm.cmd' @('pack','pnpm@11.7.0','--pack-destination',"$build/pnpm",'--silent')
Checked 'tar.exe' @('-xf',"$build/pnpm/pnpm-11.7.0.tgz",'-C',"$build/pnpm")
$node = (Get-Command node.exe).Source
$nodeLicense = Join-Path (Split-Path $node) 'LICENSE'
Checked 'python' @('scripts/build-windows-archives.py',$node,$nodeLicense)
