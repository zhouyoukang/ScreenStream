###############################################################################
# Post-Reboot Auto-Verify — 重启后自动验证 Sandbox + 全链路
# 注册为计划任务 ONLOGON 运行一次后自删除
###############################################################################
$LOG = "$env:USERPROFILE\Desktop\reboot_verify.log"
function Log($m) { $t = Get-Date -Format "HH:mm:ss"; "$t $m" | Tee-Object -Append $LOG }

Log "========== Post-Reboot Verification =========="

# 1. Sandbox 可用性
Log "[1] Windows Sandbox..."
$sb = Get-WindowsOptionalFeature -Online -FeatureName "Containers-DisposableClientVM" -ErrorAction SilentlyContinue
if ($sb.State -eq "Enabled") {
    $exe = "$env:SystemRoot\System32\WindowsSandbox.exe"
    if (Test-Path $exe) { Log "  [PASS] Sandbox READY ($exe)" }
    else { Log "  [WARN] Feature enabled but exe missing" }
} else { Log "  [FAIL] Sandbox not enabled" }

# 2. LAN Chain
Log "[2] LAN Chain..."
try {
    $r = curl.exe -sk --resolve "server.self-serve.windsurf.com:443:127.0.0.1" "https://server.self-serve.windsurf.com/" -o NUL -w "%{http_code}" -m 10 2>$null
    if ($r -eq "200") { Log "  [PASS] LAN HTTP 200" } else { Log "  [WARN] LAN HTTP $r" }
} catch { Log "  [FAIL] LAN: $_" }

# 3. Public Chain (OpenSSL)
Log "[3] Public Chain..."
$openssl = where.exe openssl 2>$null
if ($openssl) {
    $out = echo Q | openssl s_client -connect 60.205.171.100:443 -servername server.self-serve.windsurf.com -brief 2>&1
    if ($out -match "CONNECTION ESTABLISHED") { Log "  [PASS] Public TLS OK" }
    else { Log "  [WARN] Public TLS: $($out | Select-Object -First 2)" }
} else { Log "  [SKIP] OpenSSL not found" }

# 4. Portproxy
Log "[4] Portproxy..."
$pp = netsh interface portproxy show all 2>$null
if ($pp -match "192.168.31.179.*443") { Log "  [PASS] Portproxy 443→179" }
else { Log "  [FAIL] Portproxy missing" }

# 5. Desktop Shortcuts
Log "[5] Desktop Shortcuts..."
$d = "$env:USERPROFILE\Desktop"
@("Windsurf_Proxy.cmd","Windsurf_Public.cmd") | ForEach-Object {
    $p = Join-Path "D:\Desktop" $_
    if (Test-Path $p) { Log "  [PASS] $_" } else { Log "  [MISS] $_" }
}

# 6. Sandbox .wsb file
Log "[6] Sandbox Config..."
$wsb = "d:\道\道生一\一生二\Windsurf无限额度\vm-sandbox\CFW_Public_Test.wsb"
if (Test-Path $wsb) { Log "  [PASS] $wsb" } else { Log "  [MISS] WSB file" }

# Summary
Log ""
Log "========== ALL CHECKS COMPLETE =========="
Log "Sandbox: Launch $wsb to test full public chain in VM"
Log "No-VM:   D:\Desktop\Windsurf_Public.cmd for immediate public chain test"
Log ""

# Self-delete this scheduled task
schtasks /Delete /TN "CFW_PostReboot" /F 2>$null | Out-Null
Log "[CLEANUP] Scheduled task deleted"

# Show results
Start-Process notepad $LOG
