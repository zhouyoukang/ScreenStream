# 校园书市PWA一键部署脚本
# 用法: .\deploy-bookshop.ps1
# 功能: build → scp → 替换 → 验证

$ErrorActionPreference = 'Stop'
$ProjectDir = "E:\道\二手书\bookshop-pwa"
$RemoteDir = "/www/wwwroot/bookshop"
$TmpDir = "/tmp/bookshop-deploy-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

Write-Host "`n=== 校园书市 PWA 部署 ===" -ForegroundColor Green

# Step 1: Build
Write-Host "`n[1/4] 构建生产包..." -ForegroundColor Cyan
Push-Location $ProjectDir
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "构建失败" }
Pop-Location
Write-Host "  ✓ 构建完成" -ForegroundColor Green

# Step 2: Upload
Write-Host "`n[2/4] 上传到阿里云..." -ForegroundColor Cyan
scp -r "$ProjectDir\dist" "aliyun:$TmpDir"
if ($LASTEXITCODE -ne 0) { throw "上传失败" }
Write-Host "  ✓ 上传完成" -ForegroundColor Green

# Step 3: Replace
Write-Host "`n[3/4] 替换线上文件..." -ForegroundColor Cyan
ssh aliyun "sudo rm -rf $RemoteDir/* && sudo cp -r $TmpDir/* $RemoteDir/ && sudo chmod -R 755 $RemoteDir"
if ($LASTEXITCODE -ne 0) { throw "替换失败" }
Write-Host "  ✓ 替换完成" -ForegroundColor Green

# Step 4: Verify
Write-Host "`n[4/4] 验证部署..." -ForegroundColor Cyan
$status = curl.exe -s -o NUL -w "%{http_code}" "https://aiotvr.xyz/book/"
$api = curl.exe -s -o NUL -w "%{http_code}" "https://aiotvr.xyz/api/sanxian/status"
Write-Host "  前端: $status | API: $api"
if ($status -eq "200" -and $api -eq "200") {
    Write-Host "`n=== 部署成功! ===" -ForegroundColor Green
    Write-Host "  https://aiotvr.xyz/book/`n" -ForegroundColor White
} else {
    Write-Host "`n=== 部署异常，请检查 ===" -ForegroundColor Yellow
}

# Cleanup
ssh aliyun "rm -rf $TmpDir" 2>$null
