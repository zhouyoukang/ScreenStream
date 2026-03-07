# Agent公网管理电脑 - 五感E2E测试
param([string]$OutDir = $PSScriptRoot)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$results = @()
$pass = 0; $fail = 0

function Test($name, $ok, $detail) {
    if($ok) { $script:pass++; Write-Host "  PASS  $name  $detail" -ForegroundColor Green }
    else { $script:fail++; Write-Host "  FAIL  $name  $detail" -ForegroundColor Red }
    $script:results += [PSCustomObject]@{Test=$name;OK=$ok;Detail=$detail}
}

$c = "C:\Windows\System32\curl.exe"
$base = "https://aiotvr.xyz/agent"

Write-Host "`n===== 视 · API端点测试 =====" -ForegroundColor Cyan

# T1: Health (public, no auth)
$h = & $c -sk "https://aiotvr.xyz/agent/health" -m 10 2>$null | ConvertFrom-Json
Test "T01 Health(public)" ($h.status -eq "ok") "v$($h.version) agents=$($h.agents.connected)"

# T2: Login
$pw = if($env:UNIFIED_PASSWORD){$env:UNIFIED_PASSWORD}else{(Select-String '^UNIFIED_PASSWORD=(.+)' "$PSScriptRoot\..\secrets.env").Matches[0].Groups[1].Value}
$body = "{`"password`":`"$pw`"}"
$lr = & $c -sk "$base/login" -X POST -H "Content-Type: application/json" -d $body -m 10 2>$null | ConvertFrom-Json
$tok = $lr.token
$tokShow = if($tok -and $tok.Length -gt 8){$tok.Substring(0,8)}else{'null'}
Test "T02 Login" ([bool]$tok) "token=$tokShow..."

# T3: Agent list
$al = & $c -sk "https://aiotvr.xyz/agent/brain/agents" -H "Authorization: Bearer $tok" -m 10 2>$null | ConvertFrom-Json
Test "T03 Agents" ($al.agents.Count -gt 0) "$($al.agents.Count) agents, selected=$($al.selected)"

# T4: Exec
$exBody = '{"cmd":"$env:COMPUTERNAME"}'
$ex = & $c -sk "$base/brain/exec" -X POST -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d $exBody -m 15 2>$null | ConvertFrom-Json
Test "T04 Exec" ($ex.ok -eq $true) "output=$($ex.output)"

# T5: Broadcast
$bcBody = '{"cmd":"Get-Date -Format o"}'
$bc = & $c -sk "$base/brain/broadcast" -X POST -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d $bcBody -m 15 2>$null | ConvertFrom-Json
Test "T05 Broadcast" ($bc.ok -eq $true) "count=$($bc.count)"

# T6: State
$st = & $c -sk "$base/brain/state" -H "Authorization: Bearer $tok" -m 10 2>$null | ConvertFrom-Json
Test "T06 State" ($st.agent.connected -eq $true) "hostname=$($st.agent.hostname) ram=$($st.agent.sysinfo.ramGB)GB"

# T7: Terminal
$tm = & $c -sk "$base/brain/terminal?n=5" -H "Authorization: Bearer $tok" -m 10 2>$null | ConvertFrom-Json
Test "T07 Terminal" ($tm.ok -eq $true) "count=$($tm.history.Count)"

# T8: Say
$syBody = '{"text":"E2E test ping","level":"system"}'
$sy = & $c -sk "$base/brain/say" -X POST -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d $syBody -m 10 2>$null | ConvertFrom-Json
Test "T08 Say" ($sy.ok -eq $true) "message sent"

# T9: Fake agentId reject
$fkBody = '{"agentId":"FAKE-123"}'
$fk = & $c -sk "$base/brain/windsurf-setup" -X POST -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d $fkBody -m 10 2>$null | ConvertFrom-Json
Test "T09 FakeReject" ($fk.ok -eq $false) "error=$($fk.error)"

# T10: Sysinfo
$si = & $c -sk "$base/brain/sysinfo" -X POST -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d '{}' -m 15 2>$null | ConvertFrom-Json
Test "T10 Sysinfo" ($si.ok -eq $true) "triggered"

Write-Host "`n===== 听 · 连通性测试 =====" -ForegroundColor Cyan

# T11: Local health
$lh = & $c -s "http://127.0.0.1:3002/health" -m 5 2>$null | ConvertFrom-Json
Test "T11 LocalHealth" ($lh.status -eq "ok") "uptime=$([math]::Round($lh.uptime))s"

# T12: FRP tunnel (public -> local)
$fh = & $c -sk "https://aiotvr.xyz/api/health" -m 10 2>$null | ConvertFrom-Json
Test "T12 AliyunHealth" ($fh.status -eq "ok") "frp_tunnels=$($fh.frp_tunnels)"

# T13: 401 without auth
$na = & $c -sk "$base/brain/agents" -m 10 -o NUL -w "%{http_code}" 2>$null
Test "T13 NoAuth401" ($na -eq "401") "http_code=$na"

Write-Host "`n===== 触 · 前端功能测试 =====" -ForegroundColor Cyan

# T14: Page features (10 multi-device checks)
$page = & $c -sk "$base/" -H "Cookie: dao_token=$tok" -m 10 2>$null
$feats = @("dev-grid","dev-card","dev-badge","devicesSection","devGrid","renderDeviceCards","runWindsurfSetup","sDevices","allAgents","wsConfig")
$fCount = ($feats | Where-Object { $page -match $_ }).Count
Test "T14 PageFeatures" ($fCount -eq 10) "$fCount/10 features"

# T15: Page length (should be substantial)
Test "T15 PageSize" ($page.Length -gt 10000) "length=$($page.Length)"

# T16: Agent script available
$as = & $c -sk "$base/agent.ps1?key=fcd862bdd55b0b97" -m 10 -o NUL -w "%{http_code}" 2>$null
Test "T16 AgentScript" ($as -eq "200") "http_code=$as"

Write-Host "`n===== 嗅 · 安全测试 =====" -ForegroundColor Cyan

# T17: Bad password
$bp = & $c -sk "$base/login" -X POST -H "Content-Type: application/json" -d '{"password":"wrong"}' -m 10 2>$null | ConvertFrom-Json
Test "T17 BadPassword" ($bp.ok -ne $true) "rejected=$($bp.error)"

# T18: Bad agent key
$bk = & $c -sk "$base/agent.ps1?key=badkey" -m 10 -o NUL -w "%{http_code}" 2>$null
Test "T18 BadAgentKey" ($bk -eq "403") "http_code=$bk"

Write-Host "`n===== 味 · 系统质量测试 =====" -ForegroundColor Cyan

# T19: Memory usage reasonable
Test "T19 MemoryOK" ($lh.memory.rss -lt 200) "rss=$($lh.memory.rss)MB"

# T20: Token count bounded
Test "T20 TokensBound" ($lh.memory.tokens -lt 1000) "tokens=$($lh.memory.tokens)"

# T21: wsConfig field present
Test "T21 WsConfig" ($al.agents[0].wsConfig -ne $null) "wsConfig=$($al.agents[0].wsConfig)"

# T22: Agent data complete
$a0 = $al.agents[0]
$complete = $a0.hostname -and $a0.user -and $a0.os -and ($a0.isAdmin -ne $null)
Test "T22 AgentData" $complete "host=$($a0.hostname) user=$($a0.user)"

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "RESULT: $pass PASS / $fail FAIL / $($pass+$fail) TOTAL" -ForegroundColor $(if($fail -eq 0){'Green'}else{'Yellow'})

# Save results
try { $results | ConvertTo-Json -Depth 2 | Set-Content (Join-Path $OutDir '_test_results.json') -Encoding UTF8; Write-Host 'Results saved' } catch { Write-Host "Save failed: $_" }
