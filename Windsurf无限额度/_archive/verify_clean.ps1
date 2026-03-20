<#
.SYNOPSIS
    Windsurf无限额度清理状态一键验证
.DESCRIPTION
    验证台式机141上WU/CFW残留是否已彻底清理
.USAGE
    # 本地执行(台式机)
    powershell -File verify_clean.ps1
    
    # 远程执行(笔记本→台式机)
    $cred = New-Object PSCredential('administrator',(ConvertTo-SecureString 'wsy057066wsy' -AsPlainText -Force))
    Invoke-Command -ComputerName 192.168.31.141 -Credential $cred -FilePath "Windsurf无限额度\verify_clean.ps1"
#>

$pass = 0; $fail = 0; $warn = 0

function Check($name, $condition, $detail) {
    if ($condition) {
        Write-Host "[PASS] $name" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "[FAIL] $name - $detail" -ForegroundColor Red
        $script:fail++
    }
}

function Warn($name, $detail) {
    Write-Host "[WARN] $name - $detail" -ForegroundColor Yellow
    $script:warn++
}

Write-Host "=== Windsurf Clean State Verification ===" -ForegroundColor Cyan
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host ""

# 1. Hosts
$hosts = [System.IO.File]::ReadAllText('C:\Windows\System32\drivers\etc\hosts')
Check "Hosts: no codeium hijack" ($hosts -notmatch 'codeium') "hosts contains codeium entry"
Check "Hosts: no windsurf hijack" ($hosts -notmatch 'self-serve.*windsurf') "hosts contains windsurf entry"
Check "Hosts: no 127.65.43.21" ($hosts -notmatch '127\.65\.43\.21') "hosts contains WU IP"

# 2. Certificates
$mitmCert = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -match 'MITM|Local Proxy' }
Check "Cert: no MITM CA" ($null -eq $mitmCert) "MITM CA still in Root store: $($mitmCert.Subject)"

# 3. WU Processes
$wuProc = Get-Process -Name 'WindsurfUnlimited' -ErrorAction SilentlyContinue
Check "Process: no WU running" ($null -eq $wuProc) "$($wuProc.Count) WU processes found"

$guardian = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'wu_guardian' }
Check "Process: no Guardian" ($null -eq $guardian) "wu_guardian.py still running"

# 4. WU Installation
Check "Install: WU app removed" (-not (Test-Path "$env:LOCALAPPDATA\Programs\WindsurfUnlimited")) "WU app dir exists"
Check "Install: WU roaming removed" (-not (Test-Path "$env:APPDATA\windsurf-unlimited")) "WU roaming dir exists"

# 5. Scheduled Tasks
$task = Get-ScheduledTask -TaskName 'WU_Guardian' -ErrorAction SilentlyContinue
Check "Task: WU_Guardian gone" ($null -eq $task -or $task.State -eq 'Disabled') "WU_Guardian task active"

# 6. SSL Environment
$sslFile = [Environment]::GetEnvironmentVariable('SSL_CERT_FILE','Machine')
$nodeCa = [Environment]::GetEnvironmentVariable('NODE_EXTRA_CA_CERTS','Machine')
$nodeTls = [Environment]::GetEnvironmentVariable('NODE_TLS_REJECT_UNAUTHORIZED','Machine')
Check "Env: no SSL_CERT_FILE" ([string]::IsNullOrEmpty($sslFile)) "SSL_CERT_FILE=$sslFile"
Check "Env: no NODE_EXTRA_CA_CERTS" ([string]::IsNullOrEmpty($nodeCa)) "NODE_EXTRA_CA_CERTS=$nodeCa"
Check "Env: no NODE_TLS_REJECT" ([string]::IsNullOrEmpty($nodeTls)) "NODE_TLS_REJECT=$nodeTls"

# 7. ProgramData certs
$pdCerts = @('C:\ProgramData\cfw_server_cert.pem','C:\ProgramData\windsurf_proxy_ca.pem') | Where-Object { Test-Path $_ }
Check "Files: no ProgramData certs" ($pdCerts.Count -eq 0) "Found: $pdCerts"

# 8. DNS Resolution
$dns = Resolve-DnsName server.codeium.com -Type A -ErrorAction SilentlyContinue
Check "DNS: codeium resolves real IP" ($dns.IPAddress -notmatch '127\.65') "Resolves to $($dns.IPAddress)"

# 9. Proxy connectivity
try {
    $result = & curl.exe -x "http://127.0.0.1:7890" -sk --max-time 10 -o NUL -w "%{http_code}" 'https://server.codeium.com/' 2>&1
    Check "Curl: codeium reachable via proxy" ($result -match '4\d\d|2\d\d') "HTTP $result"
} catch {
    $script:fail++
    Write-Host "[FAIL] Curl: codeium unreachable" -ForegroundColor Red
}

# 10. Windsurf settings
$settingsPath = "$env:APPDATA\Windsurf\User\settings.json"
if (Test-Path $settingsPath) {
    $settings = Get-Content $settingsPath -Raw
    Check "Settings: proxySupport=override" ($settings -match '"http\.proxySupport":\s*"override"') "proxySupport not override"
}

# Summary
Write-Host ""
Write-Host "=== Results: $pass PASS / $fail FAIL / $warn WARN ===" -ForegroundColor $(if($fail -eq 0){"Green"}else{"Red"})
if ($fail -eq 0) {
    Write-Host "Windsurf is clean and ready for official service." -ForegroundColor Green
} else {
    Write-Host "WARNING: $fail checks failed. Run cleanup again." -ForegroundColor Red
}
