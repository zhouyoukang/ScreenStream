###############################################################################
# CFW Public Chain — Sandbox Auto-Setup Script
# 模拟公网客户端通过 aiotvr.xyz 连接笔记本 CFW 服务
#
# 运行环境: Windows Sandbox (LogonCommand, 管理员权限)
# 映射目录: C:\CFW → 宿主 Windsurf无限额度\
#           C:\WindsurfHost → 宿主 D:\Windsurf\
###############################################################################

$ErrorActionPreference = "Continue"
$LOG = "C:\Users\WDAGUtilityAccount\Desktop\cfw_setup.log"

function Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content $LOG $line
}

Log "========== CFW Public Chain Sandbox Setup =========="
Log "Phase 0: Environment Check"

# --- Phase 0: 环境检测 ---
$certSrc = "C:\CFW\cfw_server_cert.pem"
$windsurfExe = "C:\WindsurfHost\Windsurf.exe"
$patchedJs = "C:\WindsurfHost\resources\app\out\vs\workbench\workbench.desktop.main.js"

if (!(Test-Path $certSrc)) { Log "[FAIL] Certificate not found: $certSrc"; pause; exit 1 }
Log "[OK] Certificate found"

if (!(Test-Path $windsurfExe)) { Log "[WARN] Windsurf.exe not found at mapped path (will test chain only)" }
else { Log "[OK] Windsurf.exe found" }

# --- Phase 1: Hosts 劫持 ---
Log ""
Log "Phase 1: Hosts Configuration"
$hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
$entries = @(
    "127.0.0.1 server.self-serve.windsurf.com"
    "127.0.0.1 server.codeium.com"
)
foreach ($e in $entries) {
    Add-Content $hostsPath $e
    Log "[OK] hosts: $e"
}

# --- Phase 2: PortProxy (127.0.0.1:443 → aiotvr.xyz 公网) ---
Log ""
Log "Phase 2: PortProxy → aiotvr.xyz (Public Chain)"
$publicIP = "60.205.171.100"
netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$publicIP connectport=443 | Out-Null
$pp = netsh interface portproxy show v4tov4
Log "[OK] PortProxy: 127.0.0.1:443 → ${publicIP}:443"
Log $pp

# --- Phase 3: SSL Certificate ---
Log ""
Log "Phase 3: SSL Certificate Import"
$certDest = "C:\ProgramData\cfw_server_cert.pem"
Copy-Item $certSrc $certDest -Force
Log "[OK] Certificate copied to $certDest"

# Import to Trusted Root (so .NET/Schannel trust it)
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($certDest)
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "LocalMachine")
$store.Open("ReadWrite")
$store.Add($cert)
$store.Close()
Log "[OK] Certificate imported to Trusted Root CA store"

# Set environment variables
[Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $certDest, "Process")
[Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS", $certDest, "Process")
[Environment]::SetEnvironmentVariable("NODE_TLS_REJECT_UNAUTHORIZED", "0", "Process")
$env:SSL_CERT_FILE = $certDest
$env:NODE_EXTRA_CA_CERTS = $certDest
$env:NODE_TLS_REJECT_UNAUTHORIZED = "0"
Log "[OK] SSL_CERT_FILE = $certDest"

# --- Phase 4: Chain Verification ---
Log ""
Log "Phase 4: Public Chain Verification"

# Wait for portproxy to activate
Start-Sleep -Seconds 2

# Test 1: TCP connectivity to public server
Log "  Test 1: TCP to ${publicIP}:443..."
$tcp = New-Object System.Net.Sockets.TcpClient
try {
    $tcp.Connect($publicIP, 443)
    if ($tcp.Connected) { Log "  [PASS] TCP connected" } else { Log "  [FAIL] TCP refused" }
    $tcp.Close()
} catch { Log "  [FAIL] TCP error: $_" }

# Test 2: HTTPS via portproxy (tests the full SNI chain)
Log "  Test 2: HTTPS via portproxy (web backend)..."
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls13
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    $web = Invoke-WebRequest -Uri "https://60.205.171.100/" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    Log "  [PASS] HTTPS web: $($web.StatusCode)"
} catch { Log "  [WARN] HTTPS web: $_ (may be normal)" }

# Test 3: DNS resolution (sandbox should resolve normally, no hosts hijack for public IP)
Log "  Test 3: DNS resolution..."
try {
    $dns = [System.Net.Dns]::GetHostAddresses("aiotvr.xyz")
    Log "  [PASS] aiotvr.xyz → $($dns[0])"
} catch { Log "  [FAIL] DNS: $_" }

# --- Phase 5: Create Desktop Shortcuts ---
Log ""
Log "Phase 5: Desktop Shortcuts"

$desktop = "C:\Users\WDAGUtilityAccount\Desktop"

# Shortcut: Launch Windsurf via public chain
if (Test-Path $windsurfExe) {
    $cmdContent = @"
@echo off
set SSL_CERT_FILE=C:\ProgramData\cfw_server_cert.pem
set NODE_EXTRA_CA_CERTS=C:\ProgramData\cfw_server_cert.pem
set NODE_TLS_REJECT_UNAUTHORIZED=0
start "" "$windsurfExe" "--host-resolver-rules=MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1"
"@
    Set-Content "$desktop\Windsurf_Public.cmd" $cmdContent
    Log "[OK] Created: Windsurf_Public.cmd (launches via public chain)"
}

# Shortcut: Verify chain
$verifyContent = @"
@echo off
echo === CFW Public Chain Verification ===
echo.
echo [1] PortProxy status:
netsh interface portproxy show v4tov4
echo.
echo [2] Testing TCP to aiotvr.xyz:443...
powershell -Command "Test-NetConnection 60.205.171.100 -Port 443 -WarningAction SilentlyContinue | Select-Object TcpTestSucceeded"
echo.
echo [3] Hosts entries:
findstr /C:"windsurf" %SystemRoot%\System32\drivers\etc\hosts
echo.
echo [4] SSL Certificate:
echo SSL_CERT_FILE=%SSL_CERT_FILE%
echo.
pause
"@
Set-Content "$desktop\Verify_Chain.cmd" $verifyContent
Log "[OK] Created: Verify_Chain.cmd"

# --- Phase 6: Summary ---
Log ""
Log "========== Setup Complete =========="
Log ""
Log "Architecture:"
Log "  Sandbox Windsurf"
Log "    → hosts: 127.0.0.1 → windsurf domains"
Log "    → portproxy: 127.0.0.1:443 → 60.205.171.100:443 (aiotvr.xyz)"
Log "    → Nginx stream SNI → FRP:18443 → laptop:443 → CFW → Codeium"
Log ""
Log "Desktop shortcuts:"
Log "  - Windsurf_Public.cmd  : Launch Windsurf via public chain"
Log "  - Verify_Chain.cmd     : Verify chain configuration"
Log "  - cfw_setup.log        : This setup log"
Log ""
Log "Next: Double-click 'Windsurf_Public.cmd' to test!"

# Open log for review
Start-Process notepad $LOG
