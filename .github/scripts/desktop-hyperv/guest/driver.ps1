$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$cfg = Get-Content -Raw 'C:\CrewdenQA\guest-config.json' | ConvertFrom-Json
$edition = $cfg.edition
$hostIp = $cfg.host_ip

$lab = Join-Path $env:LOCALAPPDATA 'Crewden-QA'
$shotsDir = Join-Path $lab 'screenshots'
New-Item -ItemType Directory -Force $lab, $shotsDir | Out-Null

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win32Helper {
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
"@
[Win32Helper]::SetProcessDPIAware() | Out-Null

function Push-Receipt([string]$name, $obj) {
    $json = $obj | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText((Join-Path $lab $name), $json, [System.Text.UTF8Encoding]::new($false))
    try {
        Invoke-RestMethod -Method Put -Uri "http://${hostIp}:8078/$name" -Body ([System.Text.Encoding]::UTF8.GetBytes($json)) -TimeoutSec 5 | Out-Null
    } catch {}
}

function Capture-Screen([string]$fileName) {
    $path = Join-Path $shotsDir $fileName
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $gfx.Dispose()
    $bmp.Dispose()
    try {
        Invoke-RestMethod -Method Put -Uri "http://${hostIp}:8078/screenshots/$fileName" -InFile $path -ContentType 'image/png' -TimeoutSec 10 | Out-Null
    } catch {}
}

try {
    $elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($env:USERNAME -ne 'nanoqa' -or $elevated) {
        throw "Expected non-elevated standard user nanoqa, got user=$($env:USERNAME) elevated=$elevated"
    }
    $preinstalled = @('node', 'npm', 'pnpm') | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue }
    if ($preinstalled) {
        throw "Unexpected preinstalled Node tooling in guest PATH: $($preinstalled -join ',')"
    }

    # Wait for host portproxy + IM + Asset server readiness
    $deadline = (Get-Date).AddMinutes(8)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $h1 = Invoke-RestMethod -Uri 'http://127.0.0.1:18080/health' -TimeoutSec 3
            $h2 = Invoke-RestMethod -Uri 'http://127.0.0.1:18081/__admin/health' -TimeoutSec 3
            if ($h1 -and $h2.ok) { $ready = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (!$ready) { throw 'Timed out waiting for 127.0.0.1:18080/18081 portproxy to host stack' }

    $os = Get-CimInstance Win32_OperatingSystem
    $hw = Get-CimInstance Win32_ComputerSystem
    Push-Receipt 'environment.json' @{
        edition = $edition
        user = $env:USERNAME
        elevated = $elevated
        os_caption = $os.Caption
        os_version = $os.Version
        arch = $os.OSArchitecture
        ram_bytes = $hw.TotalPhysicalMemory
        boot_utc = $os.LastBootUpTime.ToUniversalTime().ToString('o')
        node = $false
        npm = $false
        pnpm = $false
    }

    $stepFile = Join-Path $lab 'step.txt'
    $step = if (Test-Path $stepFile) { [int](Get-Content $stepFile).Trim() } else { 1 }
    Push-Receipt 'current.json' @{ step = $step; edition = $edition; at = (Get-Date).ToUniversalTime().ToString('o') }

    if ($step -eq 1) {
        # Persist loopback test overrides in nanoqa user environment so Task Scheduler & reboot autostart inherit them
        [Environment]::SetEnvironmentVariable('NANO_ALLOW_LOOPBACK_UPDATE_HTTP', '1', 'User')
        [Environment]::SetEnvironmentVariable('NANO_LOOPBACK_RELEASE_ORIGIN', 'http://127.0.0.1:18081', 'User')
        $env:NANO_ALLOW_LOOPBACK_UPDATE_HTTP = '1'
        $env:NANO_LOOPBACK_RELEASE_ORIGIN = 'http://127.0.0.1:18081'

        # 1A. Install feat-781 lightweight Crewden-Setup-x64.exe & prepare standalone version for coexistence/takeover test
        $f781Stage = Join-Path $lab 'feat781-stage'
        New-Item -ItemType Directory -Force $f781Stage | Out-Null
        foreach ($f in @('Crewden-Setup-x64.exe', 'Smoke.exe', 'Smoke.exe.config', 'manifest.win32-x64.json')) {
            Invoke-WebRequest -Uri "http://127.0.0.1:18081/feat781/$f" -OutFile (Join-Path $f781Stage $f) -UseBasicParsing
        }
        $p781 = Start-Process -FilePath (Join-Path $f781Stage 'Crewden-Setup-x64.exe') -ArgumentList '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES' -Wait -PassThru
        if ($p781.ExitCode -ne 0) { throw "feat-781 Crewden-Setup-x64.exe failed ($($p781.ExitCode))" }
        & (Join-Path $f781Stage 'Smoke.exe') (Join-Path $f781Stage 'manifest.win32-x64.json') 'http://127.0.0.1:18081/feat781/'
        if ($LASTEXITCODE -ne 0) { throw 'feat-781 Smoke.exe preparation failed' }
        $m781 = Get-Content -Raw (Join-Path $f781Stage 'manifest.win32-x64.json') | ConvertFrom-Json
        $f781VerRoot = Join-Path $env:LOCALAPPDATA "Crewden\versions\$($m781.sha256)"

        # 1B. Download & install Crewden-Desktop-Setup-x64.exe (including clean Win10 WebView2 bootstrap!)
        $deskInstaller = Join-Path $lab 'Crewden-Desktop-Setup-x64.exe'
        $deskManifestRaw = Invoke-WebRequest -Uri 'http://127.0.0.1:18080/install/manifest.desktop-win32-x64.json' -UseBasicParsing
        $deskManifest = $deskManifestRaw.Content | ConvertFrom-Json
        Invoke-WebRequest -Uri 'http://127.0.0.1:18081/v1.0.0/Crewden-Desktop-Setup-x64.exe' -OutFile $deskInstaller -UseBasicParsing
        if ((Get-Item $deskInstaller).Length -ne $deskManifest.installer.size) {
            throw 'Downloaded Crewden-Desktop-Setup-x64.exe size mismatch'
        }
        $dlHash = (Get-FileHash -Algorithm SHA256 $deskInstaller).Hash.ToLowerInvariant()
        if ($dlHash -ne $deskManifest.installer.sha256) {
            throw 'Downloaded Crewden-Desktop-Setup-x64.exe SHA-256 mismatch'
        }

        $pDesk = Start-Process -FilePath $deskInstaller -ArgumentList '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES' -Wait -PassThru
        if ($pDesk.ExitCode -ne 0) { throw "Crewden-Desktop-Setup-x64.exe failed ($($pDesk.ExitCode))" }

        # Verify WebView2 runtime registry on clean Windows 10 & Windows 11
        $wv2Paths = @(
            'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
            'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
            'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
        )
        $wv2Version = $null
        foreach ($rp in $wv2Paths) {
            if (Test-Path $rp) {
                $pv = (Get-ItemProperty -Path $rp -Name 'pv' -ErrorAction SilentlyContinue).pv
                if ($pv -and $pv -ne '0.0.0.0') { $wv2Version = $pv; break }
            }
        }
        if (!$wv2Version) { throw "WebView2 runtime not detected after installer finished on $edition" }

        # Unpack seed archives by launching CrewdenDesktop.exe briefly (or let verify-guest.mjs drive it)
        $desktopExe = Join-Path $env:LOCALAPPDATA 'CrewdenDesktop\bin\CrewdenDesktop.exe'
        if (!(Test-Path $desktopExe)) { throw "Missing installed $desktopExe" }

        $bootProc = Start-Process -FilePath $desktopExe -ArgumentList '--im-origin', 'http://127.0.0.1:18080' -PassThru
        $hostStatePath = Join-Path $env:LOCALAPPDATA 'CrewdenDesktop\host-state.json'
        $hostReady = $false
        for ($i = 0; $i -lt 360; $i++) {
            if ($bootProc.HasExited) {
                throw "CrewdenDesktop.exe exited prematurely during first-boot seed unpack ($($bootProc.ExitCode))"
            }
            if (Test-Path $hostStatePath) {
                try {
                    $hs = Get-Content -Raw $hostStatePath | ConvertFrom-Json
                    if ($hs.ready) { $hostReady = $true; break }
                } catch {}
            }
            Start-Sleep -Seconds 1
        }
        if (!$hostReady) { throw 'CrewdenDesktop.exe did not finish first-boot seed unpack within 360s' }
        Start-Sleep -Seconds 4
        Capture-Screen "$edition-01-login-gui.png"
        & $desktopExe '--stop'
        $bootProc.WaitForExit(10000) | Out-Null

        $seedMarker = Get-Content -Raw (Join-Path $env:LOCALAPPDATA 'CrewdenDesktop\seed-current.json') | ConvertFrom-Json
        $bundledNode = Join-Path $seedMarker.version_root 'runtime\node.exe'
        if (!(Test-Path $bundledNode)) { throw "Missing unpacked bundled node.exe at $bundledNode" }

        # Run comprehensive Step 1 verification using bundled Node v24.22.1 (guest PATH remains zero-Node!)
        & $bundledNode 'C:\CrewdenQA\verify-guest.mjs' 'step1' $edition $hostIp $lab $desktopExe $f781VerRoot $wv2Version
        if ($LASTEXITCODE -ne 0) { throw "verify-guest.mjs step1 failed ($LASTEXITCODE)" }

        Set-Content -Path $stepFile -Value '2' -NoNewline
        Push-Receipt 'reboot1-scheduled.json' @{ edition = $edition; next_step = 2 }
        shutdown.exe /r /t 2 /f
        exit 0
    }

    if ($step -eq 2) {
        $seedMarker = Get-Content -Raw (Join-Path $env:LOCALAPPDATA 'CrewdenDesktop\seed-current.json') | ConvertFrom-Json
        $bundledNode = Join-Path $seedMarker.version_root 'runtime\node.exe'
        & $bundledNode 'C:\CrewdenQA\verify-guest.mjs' 'step2' $edition $hostIp $lab
        if ($LASTEXITCODE -ne 0) { throw "verify-guest.mjs step2 failed ($LASTEXITCODE)" }

        Set-Content -Path $stepFile -Value '3' -NoNewline
        Push-Receipt 'reboot2-scheduled.json' @{ edition = $edition; next_step = 3 }
        shutdown.exe /r /t 2 /f
        exit 0
    }

    if ($step -eq 3) {
        $seedMarker = Get-Content -Raw (Join-Path $env:LOCALAPPDATA 'CrewdenDesktop\seed-current.json') | ConvertFrom-Json
        $bundledNode = Join-Path $seedMarker.version_root 'runtime\node.exe'
        & $bundledNode 'C:\CrewdenQA\verify-guest.mjs' 'step3' $edition $hostIp $lab
        if ($LASTEXITCODE -ne 0) { throw "verify-guest.mjs step3 failed ($LASTEXITCODE)" }

        Push-Receipt 'pass.json' @{ passed = $true; edition = $edition; completed_at = (Get-Date).ToUniversalTime().ToString('o') }
        shutdown.exe /s /t 3 /f
        exit 0
    }
} catch {
    Push-Receipt 'failed.json' @{
        edition = $edition
        error = $_.Exception.Message
        line = $_.InvocationInfo.ScriptLineNumber
        stack = $_.ScriptStackTrace
    }
    shutdown.exe /s /t 5 /f
    exit 1
}
