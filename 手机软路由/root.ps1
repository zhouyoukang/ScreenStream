# OPPO Reno4 SE (PEAM00) Root Activation Script
# Prerequisites: BL unlocked (verified), Magisk v27.0 installed (verified)
# Firmware: PEAM00_11_F.22, Android 12, MTK MT6853
#
# Usage:
#   .\root.ps1 extract   - Extract boot.img from stock firmware
#   .\root.ps1 patch     - Push boot.img to phone for Magisk patching
#   .\root.ps1 flash     - Flash Magisk-patched boot.img via fastboot
#   .\root.ps1 verify    - Verify root is working
#   .\root.ps1 all       - Run full flow (extract -> patch -> flash -> verify)

param(
    [Parameter(Position=0)]
    [ValidateSet("extract", "patch", "flash", "verify", "all")]
    [string]$Action = "all",

    [string]$FirmwarePath = "",
    [string]$BootImg = "boot.img",
    [string]$PatchedImg = ""
)

$ADB = "D:\platform-tools\adb.exe"
$FASTBOOT = "D:\platform-tools\fastboot.exe"
$SERIAL = "WK555X5DF65PPR4L"
$DUMPER = "payload-dumper-go.exe"
$WorkDir = $PSScriptRoot

function Write-Step { param($n, $msg) Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Write-OK { param($msg) Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "  FAIL: $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "  $msg" -ForegroundColor DarkGray }

# ============================================================
# Step 1: Extract boot.img from stock firmware
# ============================================================
function Step-Extract {
    Write-Step 1 "Extract boot.img from stock firmware"

    # Check if boot.img already exists
    if (Test-Path "$WorkDir\$BootImg") {
        $size = (Get-Item "$WorkDir\$BootImg").Length
        if ($size -gt 1MB) {
            Write-OK "boot.img already exists ($([math]::Round($size/1MB, 1)) MB)"
            return $true
        }
    }

    # Check for payload-dumper-go
    $dumperPath = $null
    if (Get-Command $DUMPER -ErrorAction SilentlyContinue) {
        $dumperPath = $DUMPER
    } elseif (Test-Path "$WorkDir\$DUMPER") {
        $dumperPath = "$WorkDir\$DUMPER"
    }

    if (-not $dumperPath) {
        Write-Info "payload-dumper-go not found. Downloading..."
        $url = "https://github.com/ssut/payload-dumper-go/releases/latest"
        Write-Host @"

  payload-dumper-go is needed to extract boot.img from firmware.

  Option A: Download manually from:
    https://github.com/ssut/payload-dumper-go/releases
    Place payload-dumper-go.exe in: $WorkDir

  Option B: Provide boot.img directly:
    If you already have boot.img, place it in: $WorkDir

  Option C: Use mtkclient (MTK BROM exploit):
    pip install mtkclient
    Power off phone -> Hold Vol Down -> Connect USB
    mtk r boot boot.img

"@
        Write-Fail "Need payload-dumper-go.exe or boot.img to continue"
        return $false
    }

    # Check for firmware file
    if (-not $FirmwarePath) {
        $ozips = Get-ChildItem "$WorkDir\*.ozip","$WorkDir\*.zip" -ErrorAction SilentlyContinue
        if ($ozips) {
            $FirmwarePath = $ozips[0].FullName
            Write-Info "Found firmware: $FirmwarePath"
        }
    }

    if (-not $FirmwarePath -or -not (Test-Path $FirmwarePath)) {
        Write-Host @"

  Stock firmware not found.
  Download OPPO Reno4 SE (PEAM00) firmware build PEAM00_11_F.22:
    - Search: "OPPO PEAM00 firmware download"
    - Or: https://www.coloros.com/firmware
  Place the .zip/.ozip file in: $WorkDir
  Then run: .\root.ps1 extract -FirmwarePath "path\to\firmware.zip"

"@
        Write-Fail "Firmware file not found"
        return $false
    }

    Write-Info "Extracting boot.img from $FirmwarePath ..."
    & $dumperPath -o "$WorkDir" -partitions boot "$FirmwarePath" 2>&1
    if (Test-Path "$WorkDir\$BootImg") {
        $size = (Get-Item "$WorkDir\$BootImg").Length
        Write-OK "boot.img extracted ($([math]::Round($size/1MB, 1)) MB)"
        return $true
    } else {
        Write-Fail "Failed to extract boot.img"
        return $false
    }
}

# ============================================================
# Step 2: Push boot.img to phone for Magisk patching
# ============================================================
function Step-Patch {
    Write-Step 2 "Magisk patching (requires phone interaction)"

    if (-not (Test-Path "$WorkDir\$BootImg")) {
        Write-Fail "boot.img not found in $WorkDir. Run 'extract' first."
        return $false
    }

    # Check device connected
    $dev = & $ADB devices 2>&1 | Select-String $SERIAL
    if (-not $dev) {
        Write-Fail "Device $SERIAL not found. Connect USB and retry."
        return $false
    }

    # Push boot.img to phone
    Write-Info "Pushing boot.img to phone..."
    & $ADB -s $SERIAL push "$WorkDir\$BootImg" /sdcard/Download/boot.img 2>&1
    Write-OK "boot.img pushed to /sdcard/Download/"

    Write-Host @"

  === MANUAL STEP (on phone) ===

  1. Open Magisk app
  2. Tap "Install" (next to Magisk row)
  3. Select "Select and Patch a File"
  4. Navigate to Downloads -> boot.img
  5. Tap "LET'S GO" and wait for patching
  6. Note: patched file will be at /sdcard/Download/magisk_patched-XXXXX.img

  Press ENTER when Magisk patching is complete...

"@ -ForegroundColor Yellow
    Read-Host

    # Pull patched boot.img
    Write-Info "Looking for patched boot.img..."
    $patchedFile = & $ADB -s $SERIAL shell "ls -t /sdcard/Download/magisk_patched*.img 2>/dev/null | head -1" 2>&1
    $patchedFile = $patchedFile.Trim()

    if (-not $patchedFile -or $patchedFile -match "No such file") {
        Write-Fail "Patched boot.img not found on phone"
        Write-Info "Check /sdcard/Download/ for magisk_patched-*.img"
        return $false
    }

    Write-Info "Found: $patchedFile"
    $localPatched = "$WorkDir\magisk_patched_boot.img"
    & $ADB -s $SERIAL pull $patchedFile $localPatched 2>&1
    if (Test-Path $localPatched) {
        $size = (Get-Item $localPatched).Length
        Write-OK "Patched boot.img pulled ($([math]::Round($size/1MB, 1)) MB)"
        $script:PatchedImg = $localPatched
        return $true
    } else {
        Write-Fail "Failed to pull patched boot.img"
        return $false
    }
}

# ============================================================
# Step 3: Flash patched boot.img via fastboot
# ============================================================
function Step-Flash {
    Write-Step 3 "Flash Magisk-patched boot.img"

    # Find patched image
    $imgToFlash = $PatchedImg
    if (-not $imgToFlash -or -not (Test-Path $imgToFlash)) {
        $candidates = Get-ChildItem "$WorkDir\magisk_patched*.img" -ErrorAction SilentlyContinue
        if ($candidates) {
            $imgToFlash = $candidates[0].FullName
        }
    }

    if (-not $imgToFlash -or -not (Test-Path $imgToFlash)) {
        Write-Fail "No patched boot.img found. Run 'patch' first."
        return $false
    }

    Write-Info "Image to flash: $imgToFlash"
    $size = (Get-Item $imgToFlash).Length
    Write-Info "Size: $([math]::Round($size/1MB, 1)) MB"

    Write-Host "`n  WARNING: This will reboot phone to bootloader and flash boot partition!" -ForegroundColor Red
    Write-Host "  V2rayNG will be temporarily unavailable during reboot." -ForegroundColor Yellow
    $confirm = Read-Host "  Type 'YES' to proceed"
    if ($confirm -ne "YES") {
        Write-Info "Cancelled by user"
        return $false
    }

    # Reboot to bootloader
    Write-Info "Rebooting to bootloader..."
    & $ADB -s $SERIAL reboot bootloader 2>&1
    Start-Sleep -Seconds 10

    # Wait for fastboot device
    $retries = 0
    $found = $false
    while ($retries -lt 30 -and -not $found) {
        $fb = & $FASTBOOT devices 2>&1
        if ($fb -match "fastboot") {
            $found = $true
        } else {
            Start-Sleep -Seconds 2
            $retries++
        }
    }

    if (-not $found) {
        Write-Fail "Device not found in fastboot mode after 60s"
        Write-Info "Try: hold Vol Down + Power to enter fastboot manually"
        return $false
    }

    Write-OK "Device in fastboot mode"

    # Flash boot partition
    Write-Info "Flashing boot partition..."
    $result = & $FASTBOOT flash boot $imgToFlash 2>&1
    Write-Info $result

    if ($result -match "OKAY|Finished") {
        Write-OK "Boot partition flashed successfully"
    } else {
        Write-Fail "Flash may have failed. Check output above."
    }

    # Reboot
    Write-Info "Rebooting..."
    & $FASTBOOT reboot 2>&1
    Write-Info "Waiting 30s for phone to boot..."
    Start-Sleep -Seconds 30

    Write-OK "Phone rebooting. Root should be active after boot."
    return $true
}

# ============================================================
# Step 4: Verify root is working
# ============================================================
function Step-Verify {
    Write-Step 4 "Verifying root access"

    # Wait for device
    $retries = 0
    $found = $false
    while ($retries -lt 30 -and -not $found) {
        $dev = & $ADB devices 2>&1 | Select-String $SERIAL
        if ($dev) { $found = $true } else { Start-Sleep -Seconds 2; $retries++ }
    }

    if (-not $found) {
        Write-Fail "Device not found after reboot"
        return $false
    }
    Write-OK "Device connected"

    # Test su
    $id = & $ADB -s $SERIAL shell "su -c 'id'" 2>&1
    if ($id -match "uid=0\(root\)") {
        Write-OK "ROOT ACTIVE: $id"
    } else {
        Write-Fail "su not working: $id"
        Write-Info "Open Magisk app on phone -> it may ask to complete setup"
        Write-Info "Grant su permission if prompted"
        return $false
    }

    # Test iptables
    $ipt = & $ADB -s $SERIAL shell "su -c 'iptables -L -n | head -3'" 2>&1
    if ($ipt -match "Chain") {
        Write-OK "iptables accessible"
    } else {
        Write-Info "iptables: $ipt"
    }

    # Test ip_forward capability
    $fwd = & $ADB -s $SERIAL shell "su -c 'cat /proc/sys/net/ipv4/ip_forward'" 2>&1
    Write-Info "ip_forward = $fwd"

    Write-Host "`n  Root verification complete!" -ForegroundColor Green
    Write-Host "  Next: Run transparent proxy setup (VPNHotspot or iptables)" -ForegroundColor Cyan
    return $true
}

# ============================================================
# Main
# ============================================================
Write-Host "=== OPPO Reno4 SE Root Activation ===" -ForegroundColor Magenta
Write-Host "Device: PEAM00 | BL: unlocked | Magisk: v27.0" -ForegroundColor DarkGray

switch ($Action) {
    "extract" { Step-Extract }
    "patch"   { Step-Patch }
    "flash"   { Step-Flash }
    "verify"  { Step-Verify }
    "all" {
        $ok = Step-Extract
        if (-not $ok) { Write-Host "`nStopped at Step 1. Fix issues above and retry." -ForegroundColor Red; return }
        $ok = Step-Patch
        if (-not $ok) { Write-Host "`nStopped at Step 2. Fix issues above and retry." -ForegroundColor Red; return }
        $ok = Step-Flash
        if (-not $ok) { Write-Host "`nStopped at Step 3. Fix issues above and retry." -ForegroundColor Red; return }
        Step-Verify
    }
}
