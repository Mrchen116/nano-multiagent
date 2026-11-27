# Run on a disposable Windows runner: this exercises the current user's real
# Run registry value, Task Scheduler, installed shell, and Inno uninstaller.
$ErrorActionPreference = 'Stop'
if ($env:RUNNER_ENVIRONMENT -ne 'github-hosted') { throw 'This smoke needs a disposable GitHub-hosted Windows user' }
Set-Location (Join-Path $PSScriptRoot '../../..')
$root = Join-Path $env:RUNNER_TEMP 'installer-lifecycle'
$env:CREWDEN_DESKTOP_HOME = Join-Path $root 'Desktop Home'
$env:NANO_INSTALL_ROOT = Join-Path $root 'Nano Home'
$env:IM_PUBLIC_URL = 'http://127.0.0.1:18712'
$env:IM_DB_PATH = Join-Path $root 'im.sqlite3'
$bin = Join-Path $env:LOCALAPPDATA 'CrewdenDesktop\bin'
$exe = Join-Path $bin 'CrewdenDesktop.exe'
$release = 'dist\desktop-windows-release'
$policy = 'desktop-defaults.json'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$installArgs = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')

function Install-Or-Uninstall($program, [switch]$expectFailure) {
    $p = Start-Process $program -ArgumentList $installArgs -PassThru -Wait
    if ($expectFailure) {
        if ($p.ExitCode -eq 0) { throw "$program unexpectedly reported success" }
        return
    }
    if ($p.ExitCode -ne 0) { throw "$program exited with $($p.ExitCode)" }
}
function Wait-For($description, [scriptblock]$probe, $attempts = 120) {
    for ($i = 0; $i -lt $attempts; $i++) {
        $result = & $probe
        if ($result) { return $result }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for $description"
}
function Wait-Ready($shellProcess) {
    Wait-For 'installed shell and seed' {
        if ($shellProcess.HasExited) { throw "Shell exited with $($shellProcess.ExitCode)" }
        $statePath = Join-Path $env:CREWDEN_DESKTOP_HOME 'host-state.json'
        if (Test-Path $statePath) {
            $s = Get-Content -Raw $statePath | ConvertFrom-Json
            if ($s.ready -and $s.pid -eq $shellProcess.Id) { return $s }
        }
    } 600
}
New-Item -ItemType Directory -Force $root | Out-Null
if (Test-Path (Join-Path $release $policy)) { throw 'Official build published the previous private policy' }
$im = Start-Process node -ArgumentList 'apps/im-server/lib/main.js','serve','--port','18712' -PassThru
try {
    Install-Or-Uninstall "$env:RUNNER_TEMP/private-setup.exe"
    $privateShell = Start-Process $exe -ArgumentList '--headless-host' -PassThru
    $state = Wait-Ready $privateShell
    $defaults = Get-Content -Raw (Join-Path $env:CREWDEN_DESKTOP_HOME $policy) | ConvertFrom-Json
    if ($state.im_origin -ne $env:IM_PUBLIC_URL -or !$defaults.allow_private_http_release_base -or
        $defaults.trusted_release_base_url -ne 'http://crewden-ci.local/releases/') { throw 'Private policy was not applied' }

    $loopback = "http://127.0.0.1:$($state.port)"
    $null = Invoke-WebRequest "$loopback/desktop/bootstrap?nonce=$($state.boot_nonce)" -SessionVariable web
    $account = @{username='installer-smoke'; display_name='Installer Smoke'; password=[guid]::NewGuid().ToString()} | ConvertTo-Json
    $session = Invoke-RestMethod "$loopback/im/v1/auth/register" -WebSession $web -Method Post -ContentType 'application/json' -Body $account
    $bound = Invoke-RestMethod "$loopback/desktop/v1/local-node/connect" -WebSession $web -Method Post -ContentType 'application/json' -Body '{}' -Headers @{Authorization="Bearer $($session.access_token)"}
    if (!$bound.ok) { throw 'Desktop did not bind the disposable account' }
    $conn = @(Get-ChildItem "$env:NANO_INSTALL_ROOT/connections" -Directory)[0].FullName
    $config = Join-Path $conn 'config.yaml'
    $configHash = (Get-FileHash $config).Hash
    $workspace = New-Item -Force -ItemType Directory (Join-Path $conn 'workspaces/fixture')
    $doc = Join-Path $workspace.FullName 'preserve.txt'
    Set-Content $doc 'owner workspace'
    $privatePtr = Get-Content -Raw "$conn/.desktop-active.json" | ConvertFrom-Json

    $official = Join-Path $release 'Crewden-Desktop-Setup-x64.exe'
    $privateTask = Get-ScheduledTask -TaskPath '\' -TaskName 'CrewdenDesktop-*' | Where-Object {$_.Actions.Arguments.Contains($config)}
    $workerPackage = Join-Path $root 'blocked worker'
    New-Item -Type Directory -Force "$workerPackage/apps/node/lib" | Out-Null
    New-Item -Type Junction -Path "$workerPackage/runtime" -Target "$($privatePtr.version_root)/runtime" | Out-Null
    Set-Content "$workerPackage/apps/node/lib/update-worker.js" "const fs=require('node:fs'); fs.writeFileSync('started', ''); const timer=setInterval(()=>{if(fs.existsSync('finish')) clearInterval(timer)}, 50)"
    $updateAction = New-ScheduledTaskAction -Execute $privateTask.Actions.Execute -Argument ('worker "' + $config + '" ' + [guid]::NewGuid() + ' "' + $workerPackage + '"')
    $updateName = "$($privateTask.TaskName)-Update"
    Register-ScheduledTask -TaskName $updateName -Action $updateAction -Principal $privateTask.Principal | Out-Null
    Start-ScheduledTask -TaskName $updateName
    $null = Wait-For 'active update worker' { Test-Path "$workerPackage/started" }
    Install-Or-Uninstall $official -expectFailure
    Install-Or-Uninstall (Join-Path $bin 'unins000.exe') -expectFailure
    if ($privateShell.HasExited -or !(Get-Process -Id $bound.pid -ErrorAction SilentlyContinue)) { throw 'Rejected maintenance interrupted the running binding' }
    Set-Content "$workerPackage/finish" 'finish'
    $null = Wait-For 'update to finish' { !(Get-ScheduledTask -TaskPath '\' -TaskName $updateName -ErrorAction SilentlyContinue) }

    # Reject seed write failure before replacing the private installation, then retry.
    $descriptor = Get-Content -Raw (Join-Path $release 'desktop-win32-x64.json') | ConvertFrom-Json
    $cacheBlock = Join-Path $env:CREWDEN_DESKTOP_HOME "cache/$($descriptor.app.sha256)-$($descriptor.app.name)"
    New-Item -ItemType Directory $cacheBlock | Out-Null
    Install-Or-Uninstall $official -expectFailure
    if (!(Test-Path "$bin/seed-archives/$policy") -or
        (Get-Content -Raw "$conn/.desktop-active.json" | ConvertFrom-Json).sha256 -ne $privatePtr.sha256) { throw 'Failed overwrite lost the selected private release' }
    Remove-Item -LiteralPath $cacheBlock
    Install-Or-Uninstall $official
    if (!$privateShell.HasExited) { throw 'Overwrite left private shell running' }
    foreach ($dir in @((Join-Path $bin 'seed-archives'), $env:CREWDEN_DESKTOP_HOME)) {
        if (Test-Path (Join-Path $dir $policy)) { throw "Stale policy in $dir" }
    }
    $active = Get-Content -Raw "$conn/.desktop-active.json" | ConvertFrom-Json
    $manifest = Get-Content -Raw (Join-Path $release 'manifest.desktop-win32-x64.json') | ConvertFrom-Json
    if ($active.sha256 -eq $privatePtr.sha256 -or $active.sha256 -ne $manifest.sha256) { throw 'Bound task still selects the private release' }
    $options = & "$($active.version_root)/runtime/node.exe" --input-type=module -e "import {pathToFileURL} from 'node:url'; const r=await import(pathToFileURL(process.argv[1])); console.log(JSON.stringify(await r.loadTrustedReleaseOptions()))" "$($active.version_root)/apps/node/lib/release.js"
    if ($LASTEXITCODE -ne 0 -or $options -ne '{}') { throw "Unexpected official release trust options: $options" }

    $shell = Start-Process $exe -ArgumentList '--headless-host' -PassThru
    $null = Wait-Ready $shell
    $gateway = Wait-For 'bound official gateway' {
        $file = Join-Path $conn '.gateway-state.json'
        if (Test-Path $file) {
            $g = Get-Content -Raw $file | ConvertFrom-Json
            if ($g.ready -and $g.release.sha256 -eq $manifest.sha256) { return $g }
        }
    }
    $run = Get-ItemPropertyValue $runKey CrewdenDesktop
    if ($run -ne ('"' + $exe + '" --background')) { throw 'Bound desktop did not register its login item' }
    $task = @(Get-ScheduledTask -TaskPath '\' -TaskName 'CrewdenDesktop-*' | Where-Object {$_.Actions.Arguments -like 'serve *' -and $_.Actions.Arguments.Contains($config)})
    if ($task.Count -ne 1 -or $task[0].State -ne 'Running' -or !$task[0].Triggers) { throw 'Expected a live bound gateway login task' }
    $taskName = $task[0].TaskName
    $updateAction = New-ScheduledTaskAction -Execute $task[0].Actions.Execute -Argument ('worker "' + $config + '" ' + [guid]::NewGuid() + ' "' + $active.version_root + '"')
    Register-ScheduledTask -TaskName "$taskName-Update" -Action $updateAction -Principal $task[0].Principal | Out-Null
    $standaloneConfig = Join-Path $root 'standalone/config.yaml'
    New-Item -Force -ItemType Directory (Split-Path $standaloneConfig) | Out-Null
    Set-Content $standaloneConfig 'standalone fixture'
    $standaloneExe = (Resolve-Path 'dist/windows-build/GatewayHost.exe').Path
    $p = Start-Process $standaloneExe -ArgumentList "autostart-on `"$standaloneConfig`" 250 true" -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw 'Could not register standalone login task' }
    $standaloneTask = Get-ScheduledTask -TaskPath '\' -TaskName 'Crewden-Gateway-*' | Where-Object {$_.Actions.Arguments.Contains($standaloneConfig)}
    if (!$standaloneTask) { throw 'Missing standalone control task' }

    Install-Or-Uninstall (Join-Path $bin 'unins000.exe')
    if (!$shell.HasExited -or (Test-Path $exe) -or (Get-Process -Id $gateway.pid,$gateway.runtime_pid -ErrorAction SilentlyContinue)) { throw 'Desktop shell, gateway or DSH survived uninstall' }
    if ((Get-Item $runKey).GetValue('CrewdenDesktop') -or (Get-ScheduledTask -TaskPath '\' -TaskName "$taskName*" -ErrorAction SilentlyContinue)) { throw 'Desktop login or update registration survived uninstall' }
    if ((Test-Path "$conn/.desktop-active.json") -or (Get-FileHash $config).Hash -ne $configHash -or (Get-Content $doc) -ne 'owner workspace') { throw 'Uninstall changed node identity or workspace, or retained desktop ownership' }
    if (!(Test-Path "$env:CREWDEN_DESKTOP_HOME/sessions.json") -or (Get-Content $standaloneConfig) -ne 'standalone fixture' -or !(Get-ScheduledTask -TaskName $standaloneTask.TaskName).Triggers) { throw 'Lost session or standalone node' }
} finally {
    if ($standaloneTask) { Unregister-ScheduledTask -TaskName $standaloneTask.TaskName -Confirm:$false }
    if (!$im.HasExited) { $im.Kill(); $im.WaitForExit() }
}
