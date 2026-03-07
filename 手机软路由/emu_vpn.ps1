# LDPlayer Emulator VPN Full Chain Script
# Usage: .\emu_vpn.ps1 [start|stop|status|test|setup]
# VM[3] (开发测试1) — V2rayNG + SOCKS5 + allow-lan
#
# Architecture:
#   LDPlayer VM[3] ──► V2rayNG (tun0) ──► Trojan (HK)
#       │ wlan0=192.168.31.x (bridged to PC LAN)
#       │ SOCKS5 :::10808 (allow-lan)
#       └─► Any LAN device can use socks5://VM_IP:10808

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "status", "test", "setup")]
    [string]$Action = "status",
    [int]$VMIndex = 3,
    [string]$LDPath = "D:\leidian\LDPlayer9"
)

$ADB = "$LDPath\adb.exe"
$LDCONSOLE = "$LDPath\ldconsole.exe"
$DNCONSOLE = "$LDPath\dnconsole.exe"
$NodesFile = "$PSScriptRoot\nodes.txt"
$ErrorCount = 0

function Get-VMSerial {
    # Get ADB serial from dnconsole list2
    $list = & $DNCONSOLE list2 2>&1
    foreach ($line in $list) {
        $parts = $line -split ","
        if ($parts[0] -eq "$VMIndex" -and $parts[4] -eq "1") {
            # VM is running, try standard serial
            return "emulator-$(5554 + $VMIndex * 2)"
        }
    }
    return $null
}

function Get-VMIP {
    param([string]$Serial)
    $ip = & $ADB -s $Serial shell "ip addr show wlan0 | grep 'inet '" 2>&1
    if ($ip -match "inet\s+([\d.]+)") { return $Matches[1] }
    return $null
}

function Do-Status {
    Write-Host "`n=== LDPlayer VM[$VMIndex] VPN Status ===" -ForegroundColor Cyan

    # 1. VM running?
    Write-Host "`n[1/7] VM status..." -ForegroundColor Yellow
    $list = & $DNCONSOLE list2 2>&1
    $vmLine = ($list | Where-Object { $_ -match "^$VMIndex," })
    if ($vmLine -match ",1,") {
        Write-Host "  OK: VM[$VMIndex] running" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: VM[$VMIndex] not running" -ForegroundColor Red
        $script:ErrorCount++
        return
    }

    # 2. ADB connected?
    Write-Host "`n[2/7] ADB connection..." -ForegroundColor Yellow
    $serial = Get-VMSerial
    if (-not $serial) { Write-Host "  FAIL: Cannot determine serial" -ForegroundColor Red; $script:ErrorCount++; return }
    $devices = & $ADB devices 2>&1 | Select-String $serial
    if ($devices) {
        Write-Host "  OK: $serial connected" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: $serial not in adb devices" -ForegroundColor Red
        $script:ErrorCount++
        return
    }

    # 3. V2rayNG running?
    Write-Host "`n[3/7] V2rayNG process..." -ForegroundColor Yellow
    $v2ray = & $ADB -s $serial shell "ps -A | grep v2ray" 2>&1
    if ($v2ray -match "v2ray") {
        Write-Host "  OK: V2rayNG running" -ForegroundColor Green
    } else {
        Write-Host "  WARN: V2rayNG not running" -ForegroundColor DarkYellow
    }

    # 4. VPN tunnel?
    Write-Host "`n[4/7] VPN tunnel (tun0)..." -ForegroundColor Yellow
    $tun = & $ADB -s $serial shell "ip addr show tun0 2>/dev/null | grep 'inet '" 2>&1
    if ($tun -match "inet\s+([\d./]+)") {
        Write-Host "  OK: tun0 = $($Matches[1])" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: tun0 not found (VPN not connected)" -ForegroundColor Red
        $script:ErrorCount++
    }

    # 5. SOCKS5 port?
    Write-Host "`n[5/7] SOCKS5 :10808..." -ForegroundColor Yellow
    $socks = & $ADB -s $serial shell "netstat -tlnp 2>/dev/null | grep 10808" 2>&1
    if ($socks -match ":::10808") {
        Write-Host "  OK: SOCKS5 listening on all interfaces (allow-lan)" -ForegroundColor Green
    } elseif ($socks -match "127.0.0.1:10808") {
        Write-Host "  WARN: SOCKS5 localhost only (enable allow-lan in V2rayNG settings)" -ForegroundColor DarkYellow
    } else {
        Write-Host "  FAIL: SOCKS5 not listening" -ForegroundColor Red
        $script:ErrorCount++
    }

    # 6. VM IP
    Write-Host "`n[6/7] Network..." -ForegroundColor Yellow
    $ip = Get-VMIP -Serial $serial
    if ($ip) {
        Write-Host "  OK: wlan0 = $ip" -ForegroundColor Green
        Write-Host "  Proxy: socks5://${ip}:10808" -ForegroundColor Cyan
    }

    # 7. Root
    Write-Host "`n[7/7] Root..." -ForegroundColor Yellow
    $root = & $ADB -s $serial shell "su 0 id 2>/dev/null" 2>&1
    if ($root -match "uid=0") {
        Write-Host "  OK: Root available (uid=0)" -ForegroundColor Green
    } else {
        Write-Host "  WARN: No root (enable in LDPlayer settings)" -ForegroundColor DarkYellow
    }

    # Summary
    Write-Host "`n=== Result ===" -ForegroundColor Cyan
    if ($script:ErrorCount -eq 0) {
        Write-Host "ALL OK! Proxy: socks5://${ip}:10808" -ForegroundColor Green
    } else {
        Write-Host "$($script:ErrorCount) issues found" -ForegroundColor Red
    }
}

function Do-Start {
    Write-Host "`n=== Starting LDPlayer VM[$VMIndex] VPN ===" -ForegroundColor Cyan

    # 1. Check/start VM
    $list = & $DNCONSOLE list2 2>&1
    $vmLine = ($list | Where-Object { $_ -match "^$VMIndex," })
    if ($vmLine -notmatch ",1,") {
        Write-Host "Starting VM[$VMIndex]..." -ForegroundColor Yellow
        & $DNCONSOLE launch --index $VMIndex 2>&1 | Out-Null
        Write-Host "Waiting for boot (30s)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
    }

    # 2. Connect ADB
    $serial = Get-VMSerial
    if (-not $serial) {
        # Try common ports
        foreach ($port in @(5555,5557,5559,5561,5563,5565)) {
            & $ADB connect "127.0.0.1:$port" 2>&1 | Out-Null
        }
        Start-Sleep -Seconds 3
        $serial = Get-VMSerial
    }
    if (-not $serial) { Write-Host "FAIL: Cannot connect ADB" -ForegroundColor Red; return }
    Write-Host "ADB: $serial" -ForegroundColor Green

    # 3. Start V2rayNG
    Write-Host "Starting V2rayNG..." -ForegroundColor Yellow
    & $ADB -s $serial shell "am start -n com.v2ray.ang/.ui.MainActivity" 2>&1 | Out-Null
    Start-Sleep -Seconds 5

    # 4. Check if VPN already connected
    $tun = & $ADB -s $serial shell "ip addr show tun0 2>/dev/null | grep 'inet '" 2>&1
    if ($tun -match "tun0") {
        Write-Host "VPN already connected" -ForegroundColor Green
    } else {
        Write-Host "VPN not connected. Press connect button in V2rayNG." -ForegroundColor Yellow
        # Try to tap the FAB button (540x960 resolution)
        & $ADB -s $serial shell "input tap 470 870" 2>&1 | Out-Null
        Start-Sleep -Seconds 5
    }

    # 5. Port forward
    Write-Host "Setting up port forwarding..." -ForegroundColor Yellow
    & $ADB -s $serial forward tcp:10808 tcp:10808 2>&1 | Out-Null

    # 6. Final status
    Do-Status
}

function Do-Stop {
    Write-Host "`n=== Stopping VPN ===" -ForegroundColor Cyan
    $serial = Get-VMSerial
    if ($serial) {
        # Tap FAB to stop (if connected)
        $tun = & $ADB -s $serial shell "ip addr show tun0 2>/dev/null" 2>&1
        if ($tun -match "tun0") {
            & $ADB -s $serial shell "am start -n com.v2ray.ang/.ui.MainActivity" 2>&1 | Out-Null
            Start-Sleep -Seconds 2
            & $ADB -s $serial shell "input tap 470 870" 2>&1 | Out-Null
            Write-Host "VPN stop signal sent" -ForegroundColor Yellow
        } else {
            Write-Host "VPN already stopped" -ForegroundColor Green
        }
    }
}

function Do-Test {
    Write-Host "`n=== Testing VPN Proxy ===" -ForegroundColor Cyan
    $serial = Get-VMSerial
    $ip = Get-VMIP -Serial $serial

    if (-not $ip) {
        Write-Host "Cannot determine VM IP, using port forward (127.0.0.1)" -ForegroundColor Yellow
        $ip = "127.0.0.1"
        & $ADB -s $serial forward tcp:10808 tcp:10808 2>&1 | Out-Null
    }

    # Test 1: Exit IP
    Write-Host "`nTest 1: Exit IP..." -ForegroundColor Yellow
    $exitIp = & curl.exe -s -x "socks5://${ip}:10808" "https://api.ipify.org" -m 10 2>&1
    if ($exitIp -match '^\d+\.\d+\.\d+\.\d+$') {
        Write-Host "  OK: Exit IP = $exitIp" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Cannot get exit IP" -ForegroundColor Red
    }

    # Test 2: Google
    Write-Host "`nTest 2: Google..." -ForegroundColor Yellow
    $code = & curl.exe -s -o NUL -w "%{http_code}" -x "socks5://${ip}:10808" "https://www.google.com" -m 10 2>&1
    if ($code -eq "200") {
        Write-Host "  OK: Google reachable (HTTP 200)" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Google HTTP $code" -ForegroundColor Red
    }

    # Test 3: GitHub
    Write-Host "`nTest 3: GitHub..." -ForegroundColor Yellow
    $code2 = & curl.exe -s -o NUL -w "%{http_code}" -x "socks5://${ip}:10808" "https://github.com" -m 10 2>&1
    if ($code2 -match "200|301") {
        Write-Host "  OK: GitHub reachable (HTTP $code2)" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: GitHub HTTP $code2" -ForegroundColor Red
    }

    # Test 4: PC isolation
    Write-Host "`nTest 4: PC network isolation..." -ForegroundColor Yellow
    $pcIp = & curl.exe -s "https://api.ipify.org" -m 10 2>&1
    if ($pcIp -ne $exitIp) {
        Write-Host "  OK: PC IP ($pcIp) != Proxy IP ($exitIp) — isolated" -ForegroundColor Green
    } else {
        Write-Host "  WARN: Same IP — proxy may not be working" -ForegroundColor DarkYellow
    }
}

function Do-Setup {
    Write-Host "`n=== Initial Setup ===" -ForegroundColor Cyan
    $serial = Get-VMSerial
    if (-not $serial) { Write-Host "VM not running. Start it first." -ForegroundColor Red; return }

    # 1. Enable Root
    Write-Host "Enabling Root for VM[$VMIndex]..." -ForegroundColor Yellow
    & $LDCONSOLE modify --index $VMIndex --root 1 2>&1 | Out-Null
    Write-Host "  Root enabled (requires VM restart)" -ForegroundColor Green

    # 2. Push nodes.txt
    if (Test-Path $NodesFile) {
        Write-Host "Pushing nodes.txt to VM..." -ForegroundColor Yellow
        & $ADB -s $serial push $NodesFile /sdcard/Download/nodes.txt 2>&1 | Out-Null
        Write-Host "  OK: nodes.txt pushed" -ForegroundColor Green
    }

    # 3. Push hotspot_vpn.sh
    $hotspotScript = "$PSScriptRoot\hotspot_vpn.sh"
    if (Test-Path $hotspotScript) {
        & $ADB -s $serial push $hotspotScript /sdcard/Download/hotspot_vpn.sh 2>&1 | Out-Null
        Write-Host "  OK: hotspot_vpn.sh pushed" -ForegroundColor Green
    }

    # 4. Install V2rayNG if needed
    $v2ray = & $ADB -s $serial shell "pm list packages | grep v2ray" 2>&1
    if ($v2ray -notmatch "v2ray") {
        $apk = "$PSScriptRoot\v2rayNG.apk"
        if (Test-Path $apk) {
            Write-Host "Installing V2rayNG..." -ForegroundColor Yellow
            & $ADB -s $serial install -r -t $apk 2>&1 | Out-Null
            Write-Host "  OK: V2rayNG installed" -ForegroundColor Green
        }
    } else {
        Write-Host "  V2rayNG already installed" -ForegroundColor Green
    }

    # 5. Port forwarding
    Write-Host "Setting port forwards..." -ForegroundColor Yellow
    & $ADB -s $serial forward tcp:10808 tcp:10808 2>&1 | Out-Null
    Write-Host "  OK: localhost:10808 → VM:10808" -ForegroundColor Green

    Write-Host "`nSetup complete! Now:" -ForegroundColor Cyan
    Write-Host "  1. Open V2rayNG in VM" -ForegroundColor White
    Write-Host "  2. Import nodes: + → 从本地导入 → Download/nodes.txt" -ForegroundColor White
    Write-Host "  3. Settings → 允许来自局域网的连接 → enable" -ForegroundColor White
    Write-Host "  4. Press connect button" -ForegroundColor White
    Write-Host "  5. Run: .\emu_vpn.ps1 test" -ForegroundColor White
}

# Main
switch ($Action) {
    "start"  { Do-Start }
    "stop"   { Do-Stop }
    "status" { Do-Status }
    "test"   { Do-Test }
    "setup"  { Do-Setup }
}
