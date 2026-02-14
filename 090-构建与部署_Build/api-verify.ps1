<#
.SYNOPSIS
    ScreenStream API 自动验证脚本
.DESCRIPTION
    自动探测端口 → 验证全部 API 端点 → 输出报告
    可独立运行，也被 dev-deploy.ps1 调用
.USAGE
    .\api-verify.ps1                  # 自动探测端口
    .\api-verify.ps1 -Port 8086       # 指定端口
#>
param(
    [int]$Port = 0
)

$ADB = "$PSScriptRoot\android-sdk\platform-tools\adb.exe"

function Ok($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }
function Log($msg) { Write-Host " [..] $msg" -ForegroundColor Cyan }

# 1. 自动探测端口
if ($Port -eq 0) {
    Log "自动探测 ScreenStream API 端口..."
    $ssOutput = & $ADB shell "ss -tlnp 2>/dev/null" 2>$null
    $candidates = @()
    foreach ($line in $ssOutput) {
        if ($line -match '\*:(\d+)\s' -and [int]$Matches[1] -ge 8080 -and [int]$Matches[1] -le 8099) {
            $candidates += [int]$Matches[1]
        }
    }
    foreach ($p in ($candidates | Sort-Object -Unique)) {
        & $ADB forward tcp:$p tcp:$p 2>&1 | Out-Null
        $r = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${p}/status" 2>$null
        if ($r -like '*inputEnabled*') {
            $Port = $p
            break
        }
    }
    if ($Port -eq 0) {
        Fail "未找到 ScreenStream API 端口。请确保手机已投屏。"
        exit 1
    }
}
Ok "API 端口: $Port"

# 2. 全量验证
$pass = 0; $fail = 0; $total = 0

function Test($method, $ep, $body, $check) {
    $script:total++
    try {
        if ($method -eq "GET") {
            $r = curl.exe -s --connect-timeout 3 "http://127.0.0.1:${Port}${ep}" 2>$null
        }
        else {
            if ($body) {
                $r = curl.exe -s --connect-timeout 3 -X POST "http://127.0.0.1:${Port}${ep}" -H "Content-Type: application/json" -d $body 2>$null
            }
            else {
                $r = curl.exe -s --connect-timeout 3 -X POST "http://127.0.0.1:${Port}${ep}" 2>$null
            }
        }
        if ($r -and $r.Length -gt 1) {
            if ($check -and $r -notlike "*$check*") {
                $script:fail++; Fail "$method $ep (unexpected: $($r.Substring(0, [Math]::Min($r.Length, 80))))"
            }
            else {
                $script:pass++; Ok "$method $ep"
            }
        }
        else {
            $script:fail++; Fail "$method $ep (empty response)"
        }
    }
    catch {
        $script:fail++; Fail "$method $ep (exception)"
    }
}

Write-Host ""
Write-Host "============ ScreenStream API Verify ============" -ForegroundColor Yellow
Write-Host ""

Log "--- 基础控制 ---"
Test "GET" "/status" $null "inputEnabled"
Test "GET" "/deviceinfo" $null "model"
Test "POST" "/home"
Start-Sleep -Milliseconds 500
Test "POST" "/back"

Log "--- 系统控制 ---"
Test "POST" "/volume/up"
Start-Sleep -Milliseconds 200
Test "POST" "/volume/down"
Test "POST" "/notifications"
Start-Sleep -Milliseconds 500
Test "POST" "/back"

Log "--- 远程协助 ---"
Test "GET" "/clipboard"
Test "GET" "/apps" $null "packageName"
Test "POST" "/wake"

Log "--- AI Brain ---"
Test "GET" "/viewtree?depth=3" $null "cls"
Test "GET" "/windowinfo" $null "package"
Test "POST" "/dismiss"
Test "POST" "/findclick" '{"text":"__nonexistent_test__"}' "ok"

Log "--- 宏系统 ---"
Test "GET" "/macro/list"
Test "GET" "/macro/running"
# 创建 → 运行 → 日志 → 删除
$cr = curl.exe -s --connect-timeout 3 -X POST "http://127.0.0.1:${Port}/macro/create" -H "Content-Type: application/json" -d '{"name":"_verify_","actions":[{"type":"wait","ms":100}]}' 2>$null
if ($cr -like '*"id"*') {
    $id = ($cr | ConvertFrom-Json).id
    Ok "POST /macro/create (id=$id)"
    $pass++; $total++
    Test "POST" "/macro/run/$id"
    Start-Sleep -Seconds 1
    Test "GET" "/macro/log/$id" $null "result"
    Test "POST" "/macro/delete/$id" $null "ok"
}
else {
    Fail "POST /macro/create"
    $fail++; $total++
}

# 内联执行
Test "POST" "/macro/run-inline" '{"actions":[{"type":"wait","ms":50}],"loop":1}'

Log "--- S33 文件管理 ---"
Test "GET" "/files/storage" $null "storagePath"
Test "GET" "/files/list" $null '"ok"'
Test "GET" "/files/list?sort=modified&hidden=true" $null '"ok"'
Test "GET" "/files/info?path=/sdcard/Download" $null '"ok"'
Test "GET" "/files/search?path=/sdcard&q=Download&max=3" $null '"ok"'
# CRUD sequence: mkdir → upload → read → download → rename → delete
Test "POST" "/files/mkdir" '{"path":"/sdcard/Download/_api_verify_tmp"}'
$b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("verify"))
Test "POST" "/files/upload" "{`"path`":`"/sdcard/Download/_api_verify_tmp/v.txt`",`"data`":`"$b64`"}"
Test "GET" "/files/read?path=/sdcard/Download/_api_verify_tmp/v.txt" $null "verify"
Test "GET" "/files/download?path=/sdcard/Download/_api_verify_tmp/v.txt" $null '"data"'
Test "POST" "/files/rename" '{"path":"/sdcard/Download/_api_verify_tmp/v.txt","newName":"v2.txt"}'
Test "POST" "/files/copy" '{"src":"/sdcard/Download/_api_verify_tmp/v2.txt","dest":"/sdcard/Download/_api_verify_tmp"}'
Test "POST" "/files/move" '{"src":"/sdcard/Download/_api_verify_tmp/v2.txt","dest":"/sdcard/Download"}'
Test "POST" "/files/delete" '{"path":"/sdcard/Download/_api_verify_tmp"}'
Test "POST" "/files/delete" '{"path":"/sdcard/Download/v2.txt"}'

Log "--- Platform Layer (APP调度) ---"
Test "GET" "/screen/text" $null '"ok"'
Test "GET" "/notifications/read" $null '"ok"'
Test "GET" "/wait?text=ScreenStream&timeout=3000" $null '"ok"'
Test "POST" "/intent" '{"action":"android.intent.action.VIEW","data":"https://www.baidu.com"}' '"ok"'

Write-Host ""
Write-Host "=================================================" -ForegroundColor Yellow
$color = if ($fail -eq 0) { "Green" } else { "Yellow" }
Write-Host "  结果: $pass/$total 通过, $fail 失败" -ForegroundColor $color
Write-Host "  端口: $Port" -ForegroundColor White
Write-Host "  投屏: http://127.0.0.1:${Port}/" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Yellow
