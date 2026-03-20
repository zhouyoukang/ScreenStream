#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Clean up CFW sharing remnants on desktop (192.168.31.141)
    Run this script ON THE DESKTOP with admin privileges.
#>

$ErrorActionPreference = "Continue"

Write-Host "`n=== Windsurf CFW Sharing Cleanup ===" -ForegroundColor Cyan

# 1. Remove portproxy
Write-Host "`n[1/7] Removing portproxy rule..."
netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null
netsh interface portproxy show v4tov4

# 2. Remove WindsurfPortProxy scheduled task
Write-Host "`n[2/7] Removing WindsurfPortProxy task..."
schtasks /Delete /TN "WindsurfPortProxy" /F 2>$null

# 3. Remove SSL_CERT_FILE environment variable
Write-Host "`n[3/7] Removing SSL_CERT_FILE..."
$old = [Environment]::GetEnvironmentVariable("SSL_CERT_FILE", "Machine")
if ($old) {
    Write-Host "  Was: $old"
    [Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $null, "Machine")
    Write-Host "  Removed"
} else {
    Write-Host "  Already clean"
}

# 4. Remove NODE_EXTRA_CA_CERTS
Write-Host "`n[4/7] Removing NODE_EXTRA_CA_CERTS..."
$old2 = [Environment]::GetEnvironmentVariable("NODE_EXTRA_CA_CERTS", "Machine")
if ($old2) {
    [Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", $null, "Machine")
    Write-Host "  Removed: $old2"
} else {
    Write-Host "  Already clean"
}

# 5. Clean hosts file
Write-Host "`n[5/7] Cleaning hosts file..."
$hosts = "C:\Windows\System32\drivers\etc\hosts"
$lines = Get-Content $hosts
$cleaned = $lines | Where-Object { $_ -notmatch "windsurf\.com|codeium\.com" }
if ($lines.Count -ne $cleaned.Count) {
    $cleaned | Set-Content $hosts -Encoding ASCII
    Write-Host "  Removed $($lines.Count - $cleaned.Count) lines"
} else {
    Write-Host "  No windsurf/codeium entries found"
}

# 6. Remove PEM files
Write-Host "`n[6/7] Removing PEM/CER files..."
foreach ($f in @("C:\ProgramData\windsurf_proxy_ca.pem", "C:\ProgramData\cfw_server_cert.pem")) {
    if (Test-Path $f) { Remove-Item $f -Force; Write-Host "  Deleted: $f" }
}

# 7. Restore Windsurf patches
Write-Host "`n[7/7] Restoring Windsurf patches..."
$js = "D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js"
$bak = "$js.bak"
if (Test-Path $bak) {
    Copy-Item $bak $js -Force
    Write-Host "  Restored from .bak"
} else {
    Write-Host "  No .bak found (patches may not have been applied)"
}

Write-Host "`n=== Cleanup Complete ===" -ForegroundColor Green
Write-Host "Desktop Windsurf is now in default (Free) mode."
Write-Host "Restart Windsurf to take effect.`n"
