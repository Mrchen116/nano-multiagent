param(
    [ValidateSet('win10', 'win11')]
    [string]$Edition = 'win11'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$isWin11 = $Edition -eq 'win11'
$name = if ($isWin11) { 'CrewdenDesktopWin11' } else { 'CrewdenDesktopWin10' }
$prefix = if ($isWin11) { '192.168.184' } else { '192.168.183' }
$guestName = if ($isWin11) { 'CREWDEN-W11' } else { 'CREWDEN-W10' }
$isoUrl = if ($isWin11) {
    'https://go.microsoft.com/fwlink/?LinkId=2382600&clcid=0x409&country=us&culture=en-us'
} else {
    'https://go.microsoft.com/fwlink/p/?LinkID=2195404&clcid=0x409&culture=en-us&country=us'
}

$root = Join-Path $env:RUNNER_TEMP "crewden-hyperv-$Edition"
$evidenceOut = Join-Path $env:RUNNER_TEMP "$Edition-desktop-evidence"
$workDir = Join-Path $root 'host-work'
$bundleDir = Join-Path $env:RUNNER_TEMP 'qa-windows-bundle'
New-Item -ItemType Directory -Force $root, $evidenceOut, $workDir | Out-Null

$iso = Join-Path $root "official-$Edition.iso"
$vhd = Join-Path $root "clean-$Edition.vhdx"
$ctlPass = 'A9!' + [guid]::NewGuid().ToString('N')
$qaPass = 'B3!' + [guid]::NewGuid().ToString('N')
$cred = [pscredential]::new("$guestName\nanoctl", (ConvertTo-SecureString $ctlPass -AsPlainText -Force))
$hostStackProc = $null

try {
    Write-Host "[$Edition] Downloading official Microsoft evaluation media..."
    $final = curl.exe --proto '=https' --proto-redir '=https' --retry 3 -fsSL -o $iso -w '%{url_effective}' $isoUrl
    if ($LASTEXITCODE -or ([uri]$final).Host -notlike '*.microsoft.com') {
        throw "Failed to retrieve official Microsoft $Edition evaluation media"
    }
    $isoSha = (Get-FileHash -Algorithm SHA256 $iso).Hash.ToLowerInvariant()
    Write-Host "[$Edition] Official ISO SHA-256: $isoSha"

    $dvd = Mount-DiskImage -ImagePath $iso -PassThru | Get-Volume
    $image = "$($dvd.DriveLetter):\sources\install.wim"
    if (!(Test-Path $image)) { $image = "$($dvd.DriveLetter):\sources\install.esd" }
    $index = Get-WindowsImage -ImagePath $image -Index 1
    Write-Host "[$Edition] Official Windows image: $($index.ImageName) ($($index.Version))"
    if ($isWin11 -and $index.ImageName -notmatch 'Windows 11') { throw 'Unexpected Windows 11 WIM' }
    if (!$isWin11 -and $index.ImageName -notmatch 'Windows 10') { throw 'Unexpected Windows 10 WIM' }

    @{
        edition = $Edition
        iso_sha256 = $isoSha
        image_name = $index.ImageName
        image_version = $index.Version
    } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $evidenceOut 'host-media.json')

    if (Get-PSDrive S, W -ErrorAction SilentlyContinue) { throw 'Mount letters S/W already in use' }
    New-VHD -Path $vhd -Dynamic -SizeBytes 64GB | Out-Null
    $disk = Mount-VHD -Path $vhd -PassThru | Get-Disk
    Initialize-Disk -Number $disk.Number -PartitionStyle GPT | Out-Null
    $efi = New-Partition -DiskNumber $disk.Number -Size 260MB -GptType '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}' -DriveLetter S
    $efi | Format-Volume -FileSystem FAT32 -NewFileSystemLabel CREWDENEFI -Confirm:$false | Out-Null
    New-Partition -DiskNumber $disk.Number -Size 16MB -GptType '{e3c9e316-0b5c-4db8-817d-f92df00215ae}' | Out-Null
    $os = New-Partition -DiskNumber $disk.Number -UseMaximumSize -DriveLetter W
    $os | Format-Volume -FileSystem NTFS -NewFileSystemLabel CREWDENWIN -Confirm:$false | Out-Null

    dism.exe /Apply-Image "/ImageFile:$image" /Index:1 /ApplyDir:W:\ /Quiet
    if ($LASTEXITCODE) { throw "DISM apply failed ($LASTEXITCODE)" }
    if ($isWin11) {
        & "$env:SystemRoot\System32\bcdboot.exe" W:\Windows /s S: /f UEFI /v | Out-Null
    } else {
        & 'W:\Windows\System32\bcdboot.exe' W:\Windows /s S: /f UEFI | Out-Null
    }
    if ($LASTEXITCODE) { throw "bcdboot failed ($LASTEXITCODE)" }

    New-Item -Force -Type Directory W:\Windows\Panther | Out-Null
    $answer = @"
<unattend xmlns="urn:schemas-microsoft-com:unattend" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
<settings pass="specialize"><component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><ComputerName>$guestName</ComputerName><TimeZone>UTC</TimeZone></component></settings>
<settings pass="oobeSystem">
<component name="Microsoft-Windows-International-Core" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS"><InputLocale>0409:00000409</InputLocale><SystemLocale>en-US</SystemLocale><UILanguage>en-US</UILanguage><UserLocale>en-US</UserLocale></component>
<component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
<Display><HorizontalResolution>1440</HorizontalResolution><VerticalResolution>960</VerticalResolution><ColorDepth>32</ColorDepth></Display>
<OOBE><HideEULAPage>true</HideEULAPage><HideOEMRegistrationScreen>true</HideOEMRegistrationScreen><HideOnlineAccountScreens>true</HideOnlineAccountScreens><HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE><ProtectYourPC>3</ProtectYourPC></OOBE>
<UserAccounts><LocalAccounts><LocalAccount wcm:action="add"><Password><Value>$ctlPass</Value><PlainText>true</PlainText></Password><DisplayName>QA management</DisplayName><Group>Administrators</Group><Name>nanoctl</Name></LocalAccount><LocalAccount wcm:action="add"><Password><Value>$qaPass</Value><PlainText>true</PlainText></Password><DisplayName>Ordinary tester</DisplayName><Group>Users</Group><Name>nanoqa</Name></LocalAccount></LocalAccounts></UserAccounts>
<AutoLogon><Password><Value>$qaPass</Value><PlainText>true</PlainText></Password><Enabled>true</Enabled><Domain>$guestName</Domain><LogonCount>8</LogonCount><Username>nanoqa</Username></AutoLogon>
</component></settings></unattend>
"@
    Set-Content -Encoding utf8 'W:\Windows\Panther\unattend.xml' $answer
    Copy-Item (Join-Path $PSScriptRoot 'guest') W:\CrewdenQA -Recurse
    @{
        edition = $Edition
        host_ip = "$prefix.1"
    } | ConvertTo-Json | Set-Content -Encoding utf8 'W:\CrewdenQA\guest-config.json'

    $startup = 'W:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp\CrewdenQADriver.cmd'
    Set-Content -Encoding ASCII $startup '@start "" powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File C:\CrewdenQA\driver.ps1'

    Dismount-VHD -Path $vhd
    Dismount-DiskImage -ImagePath $iso | Out-Null
    Remove-Item $iso -Force

    $dns = @([System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() | Where-Object {
        $_.OperationalStatus -eq [System.Net.NetworkInformation.OperationalStatus]::Up
    } | ForEach-Object {
        $props = $_.GetIPProperties()
        if ($props.GatewayAddresses.Count -gt 0) {
            $props.DnsAddresses | Where-Object {
                $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and $_.ToString() -ne '127.0.0.1'
            } | ForEach-Object { $_.ToString() }
        }
    } | Select-Object -Unique)
    if (!$dns) { throw 'Hyper-V host has no IPv4 DNS server' }

    Write-Host "[$Edition] Creating internal Hyper-V NAT switch ($prefix.1/24)..."
    New-VMSwitch -Name $name -SwitchType Internal | Out-Null
    $if = Get-NetAdapter -Name "vEthernet ($name)"
    New-NetIPAddress -IPAddress "$prefix.1" -PrefixLength 24 -InterfaceIndex $if.ifIndex | Out-Null
    New-NetNat -Name $name -InternalIPInterfaceAddressPrefix "$prefix.0/24" | Out-Null
    New-NetFirewallRule -DisplayName "CrewdenQA-$Edition" -Direction Inbound -Action Allow -Protocol TCP -LocalAddress "$prefix.1" -LocalPort 8078,18080,18081,18082,18083 -RemoteAddress "$prefix.2" -Profile Any | Out-Null

    Write-Host "[$Edition] Starting host IM + Metered Asset + SSE LLM control stack..."
    $hostStackLog = Join-Path $evidenceOut 'host-stack.log'
    $hostStackErr = Join-Path $evidenceOut 'host-stack.err.log'
    $hostStackProc = Start-Process -FilePath (Get-Command node.exe).Source `
        -ArgumentList @((Join-Path $PSScriptRoot 'host-stack.mjs'), "$prefix.1", $bundleDir, $workDir, $evidenceOut, $repoRoot) `
        -RedirectStandardOutput $hostStackLog -RedirectStandardError $hostStackErr -NoNewWindow -PassThru
    $readyFile = Join-Path $workDir 'host-stack-ready.json'
    for ($i = 0; $i -lt 120; $i++) {
        if (Test-Path $readyFile) { break }
        if ($hostStackProc.HasExited) {
            $errTxt = if (Test-Path $hostStackErr) { Get-Content -Raw $hostStackErr } else { '' }
            throw "host-stack.mjs exited prematurely: $errTxt"
        }
        Start-Sleep -Milliseconds 500
    }
    if (!(Test-Path $readyFile)) {
        $outTxt = if (Test-Path $hostStackLog) { Get-Content -Raw $hostStackLog } else { '' }
        $errTxt = if (Test-Path $hostStackErr) { Get-Content -Raw $hostStackErr } else { '' }
        throw "Timed out waiting for host-stack.mjs: stdout=$outTxt stderr=$errTxt"
    }

    $ramBytes = if ($isWin11) { 8GB } else { 6GB }
    $vm = New-VM -Name $name -Generation 2 -MemoryStartupBytes $ramBytes -VHDPath $vhd -SwitchName $name -Path $root
    Set-VM -VM $vm -AutomaticCheckpointsEnabled $false
    Set-VMProcessor -VMName $name -Count 4
    Set-VMVideo -VMName $name -HorizontalResolution 1440 -VerticalResolution 960 -ResolutionType Single
    if ($isWin11) {
        Set-VMFirmware -VMName $name -EnableSecureBoot On -SecureBootTemplate MicrosoftWindows
        Set-VMKeyProtector -VMName $name -NewLocalKeyProtector
        Enable-VMTPM -VMName $name
        if (!(Get-VMSecurity -VMName $name).TpmEnabled -or (Get-VMFirmware -VMName $name).SecureBoot -ne 'On') {
            throw 'Win11 TPM2/Secure Boot requirements not met'
        }
    }

    Write-Host "[$Edition] Booting clean guest VM..."
    Start-VM -VM $vm
    $s = $null
    $until = (Get-Date).AddMinutes(14)
    do {
        Start-Sleep 8
        try { $s = New-PSSession -VMName $name -Credential $cred -ErrorAction Stop; break } catch {}
    } while ((Get-Date) -lt $until)
    if (!$s) { throw "Guest $Edition did not accept PowerShell Direct after boot" }

    Invoke-Command -Session $s -ArgumentList $prefix, ($dns -join ','), $isWin11 -ScriptBlock {
        param($prefix, $dnsList, $checkTpm)
        $net = Get-NetAdapter | Where-Object Status -eq Up | Select-Object -First 1
        New-NetIPAddress -InterfaceIndex $net.ifIndex -IPAddress "$prefix.2" -PrefixLength 24 -DefaultGateway "$prefix.1" | Out-Null
        Set-DnsClientServerAddress -InterfaceIndex $net.ifIndex -ServerAddresses ($dnsList.Split(','))
        foreach ($p in 18080, 18081, 18082, 18083) {
            netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=$p connectaddress="$prefix.1" connectport=$p | Out-Null
        }
        Set-Service iphlpsvc -StartupType Automatic
        Restart-Service iphlpsvc
        powercfg /change standby-timeout-ac 0
        $wsl = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
        if ($wsl.State -ne 'Disabled') { throw "Guest WSL feature is $($wsl.State)" }
        if ($checkTpm) {
            $tpm = Get-Tpm
            if (!$tpm.TpmPresent -or !(Confirm-SecureBootUEFI)) { throw 'Actual Win11 TPM/Secure Boot requirements not met' }
        }
        Write-Host "Guest OS $([Environment]::OSVersion.Version) ready; portproxy + NAT active"
    }
    Remove-PSSession $s -ErrorAction SilentlyContinue

    Write-Host "[$Edition] Watching guest acceptance progress..."
    $until = (Get-Date).AddMinutes(55)
    $seen = @{}
    $endReason = 'timeout'
    :watchLoop while ((Get-Date) -lt $until) {
        if ((Get-VM -Name $name).State -eq 'Off') { $endReason = 'guest shut down'; break }
        foreach ($entry in (Get-ChildItem "$evidenceOut\*.json" -ErrorAction SilentlyContinue)) {
            $text = Get-Content $entry.FullName -Raw -ErrorAction SilentlyContinue
            if (!$text -or $text -eq $seen[$entry.Name]) { continue }
            $seen[$entry.Name] = $text
            Write-Host "[$Edition receipt] $($entry.Name): $($text.Substring(0, [Math]::Min(400, $text.Length)).Replace("`r",'').Replace("`n",' '))"
            if ($entry.Name -eq 'failed.json') { $endReason = 'guest reported failure'; break watchLoop }
        }
        if (Test-Path "$evidenceOut\pass.json") { $endReason = 'guest reported pass'; break }
        Start-Sleep 4
    }

    if ($endReason -ne 'timeout') {
        $sdUntil = (Get-Date).AddSeconds(90)
        while ((Get-VM -Name $name).State -ne 'Off' -and (Get-Date) -lt $sdUntil) { Start-Sleep 2 }
    }
    $vm = Get-VM -Name $name
    if ($vm.State -ne 'Off') { Stop-VM -VM $vm -TurnOff -Force }

    try {
        $readDisk = Mount-VHD -Path $vhd -ReadOnly -PassThru | Get-Disk
        $osPart = Get-Partition -DiskNumber $readDisk.Number | Where-Object Type -eq Basic | Sort-Object Size -Descending | Select-Object -First 1
        $osVol = $osPart | Get-Volume
        if (!$osVol.DriveLetter) { $osPart | Add-PartitionAccessPath -AssignDriveLetter; $osVol = $osPart | Get-Volume }
        $diskLab = Join-Path ("$($osVol.DriveLetter):\") 'Users\nanoqa\AppData\Local\Crewden-QA'
        if (Test-Path $diskLab) {
            Get-ChildItem "$diskLab\*.json" -ErrorAction SilentlyContinue | Copy-Item -Destination $evidenceOut -Force
            Get-ChildItem "$diskLab\*.log" -ErrorAction SilentlyContinue | Copy-Item -Destination $evidenceOut -Force
            if (Test-Path "$diskLab\screenshots") {
                New-Item -ItemType Directory -Force "$evidenceOut\screenshots" | Out-Null
                Get-ChildItem "$diskLab\screenshots\*.png" -ErrorAction SilentlyContinue | Copy-Item -Destination "$evidenceOut\screenshots" -Force
            }
        }
    } finally {
        Dismount-VHD -Path $vhd -ErrorAction SilentlyContinue
    }

    if (Test-Path "$evidenceOut\failed.json") {
        $failObj = Get-Content -Raw "$evidenceOut\failed.json" | ConvertFrom-Json
        throw "[$Edition] Guest acceptance failed: $($failObj | ConvertTo-Json -Compress)"
    }
    if (!(Test-Path "$evidenceOut\pass.json")) {
        throw "[$Edition] Guest did not complete all phases ($endReason)"
    }
    Write-Host "[$Edition] CLEAN GUEST VM ACCEPTANCE PASSED 100%!"
} finally {
    if ($hostStackProc -and !$hostStackProc.HasExited) { Stop-Process -Id $hostStackProc.Id -Force -ErrorAction SilentlyContinue }
    if (Get-VM -Name $name -ErrorAction SilentlyContinue) {
        Stop-VM -Name $name -TurnOff -Force -ErrorAction SilentlyContinue
        Remove-VM -Name $name -Force -ErrorAction SilentlyContinue
    }
    Dismount-VHD -Path $vhd -ErrorAction SilentlyContinue
    if (Test-Path $iso) { Dismount-DiskImage -ImagePath $iso -ErrorAction SilentlyContinue }
    Remove-NetFirewallRule -DisplayName "CrewdenQA-$Edition" -ErrorAction SilentlyContinue
    Remove-NetNat -Name $name -Confirm:$false -ErrorAction SilentlyContinue
    Remove-VMSwitch -Name $name -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
