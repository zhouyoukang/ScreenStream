<#
.SYNOPSIS
    S33 远程文件管理器 API 验证脚本
.DESCRIPTION
    验证 12 个 /files/* 端点全部可用
    运行前提：ScreenStream 已启动投屏，端口已转发
#>

param(
    [int]$Port = 8086
)

$base = "http://127.0.0.1:$Port"
$pass = 0; $fail = 0; $total = 0

function Test-Api {
    param([string]$Method, [string]$Url, [string]$Body, [string]$Name, [string]$Expect = '"ok"')
    $script:total++
    try {
        if ($Method -eq 'GET') {
            $r = curl.exe -s --connect-timeout 5 $Url 2>$null
        } else {
            $r = curl.exe -s --connect-timeout 5 -X POST -H 'Content-Type: application/json' -d $Body $Url 2>$null
        }
        if ($r -match $Expect) {
            Write-Host "  [OK] $Name" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "  [FAIL] $Name" -ForegroundColor Red
            Write-Host "    Response: $($r.Substring(0, [Math]::Min(200, $r.Length)))" -ForegroundColor DarkGray
            $script:fail++
        }
    } catch {
        Write-Host "  [ERR] $Name : $($_.Exception.Message)" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "`n========== S33 Remote File Manager API Verify ==========" -ForegroundColor Cyan
Write-Host "Target: $base`n"

# 1. Storage info
Write-Host "--- GET Endpoints ---" -ForegroundColor Yellow
Test-Api -Method GET -Url "$base/files/storage" -Name "GET /files/storage" -Expect '"storagePath"'

# 2. List files
Test-Api -Method GET -Url "$base/files/list" -Name "GET /files/list (root)"

# 3. List with params
Test-Api -Method GET -Url "$base/files/list?sort=modified&hidden=true" -Name "GET /files/list (sort+hidden)"

# 4. File info
Test-Api -Method GET -Url "$base/files/info?path=/sdcard/Download" -Name "GET /files/info"

# 5. Search
Test-Api -Method GET -Url "$base/files/search?path=/sdcard&q=Download&max=5" -Name "GET /files/search"

# 6. Read text (try a common file)
Test-Api -Method GET -Url "$base/files/read?path=/sdcard/Download/.nomedia" -Name "GET /files/read (text)" -Expect '"ok"'

Write-Host "`n--- POST Endpoints (CRUD sequence) ---" -ForegroundColor Yellow

# 7. Create directory
Test-Api -Method POST -Url "$base/files/mkdir" -Body '{"path":"/sdcard/Download/_s33_test_dir"}' -Name "POST /files/mkdir"

# 8. Upload file
$testData = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("Hello S33 File Manager!"))
Test-Api -Method POST -Url "$base/files/upload" -Body "{`"path`":`"/sdcard/Download/_s33_test_dir/test.txt`",`"data`":`"$testData`"}" -Name "POST /files/upload"

# 9. Read uploaded file
Test-Api -Method GET -Url "$base/files/read?path=/sdcard/Download/_s33_test_dir/test.txt" -Name "GET /files/read (uploaded)" -Expect 'Hello S33'

# 10. Download uploaded file
Test-Api -Method GET -Url "$base/files/download?path=/sdcard/Download/_s33_test_dir/test.txt" -Name "GET /files/download" -Expect '"data"'

# 11. Rename
Test-Api -Method POST -Url "$base/files/rename" -Body '{"path":"/sdcard/Download/_s33_test_dir/test.txt","newName":"test_renamed.txt"}' -Name "POST /files/rename"

# 12. Copy
Test-Api -Method POST -Url "$base/files/copy" -Body '{"src":"/sdcard/Download/_s33_test_dir/test_renamed.txt","dest":"/sdcard/Download/_s33_test_dir"}' -Name "POST /files/copy"

# 13. Move
Test-Api -Method POST -Url "$base/files/move" -Body '{"src":"/sdcard/Download/_s33_test_dir/test_renamed.txt","dest":"/sdcard/Download"}' -Name "POST /files/move"

# 14. Delete (cleanup)
Test-Api -Method POST -Url "$base/files/delete" -Body '{"path":"/sdcard/Download/_s33_test_dir"}' -Name "POST /files/delete (dir)"
Test-Api -Method POST -Url "$base/files/delete" -Body '{"path":"/sdcard/Download/test_renamed.txt"}' -Name "POST /files/delete (file)"

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
if ($fail -eq 0) {
    Write-Host "  RESULT: $pass/$total ALL PASSED" -ForegroundColor Green
} else {
    Write-Host "  RESULT: $pass/$total passed, $fail FAILED" -ForegroundColor Red
}
Write-Host "========================================`n" -ForegroundColor Cyan
