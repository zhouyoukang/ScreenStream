# 部署WebXR应用到Quest (通过aiotvr.xyz公网或本地)
# 用法: .\deploy-quest.ps1 -ProjectDir "../webxr/hello-vr" [-Remote]

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectDir,
    [switch]$Remote
)

Write-Host "=== 部署WebXR到Quest ===" -ForegroundColor Cyan

# 验证项目目录
if (-not (Test-Path $ProjectDir)) {
    Write-Host "[FAIL] 项目目录不存在: $ProjectDir" -ForegroundColor Red
    exit 1
}

if ($Remote) {
    # 远程部署到aiotvr.xyz
    Write-Host "部署到 aiotvr.xyz/quest/ ..." -ForegroundColor Yellow
    $remotePath = "/var/www/quest/$(Split-Path $ProjectDir -Leaf)"
    ssh aliyun "mkdir -p $remotePath"
    scp -r "$ProjectDir/*" "aliyun:$remotePath/"
    $url = "https://aiotvr.xyz/quest/$(Split-Path $ProjectDir -Leaf)/"
    Write-Host "[OK] 已部署: $url" -ForegroundColor Green
    Write-Host "在Quest浏览器中访问上述URL" -ForegroundColor White
} else {
    # 本地HTTPS服务
    $certDir = Join-Path $PSScriptRoot ".." "certs"
    $cert = Join-Path $certDir "cert.pem"
    $key = Join-Path $certDir "key.pem"

    if (-not (Test-Path $cert)) {
        Write-Host "[FAIL] 证书不存在，请先运行 setup.ps1" -ForegroundColor Red
        exit 1
    }

    Write-Host "启动本地HTTPS服务器..." -ForegroundColor Yellow
    Write-Host "Quest浏览器访问: https://<你的IP>:8443" -ForegroundColor White
    npx serve $ProjectDir --ssl-cert $cert --ssl-key $key -l 8443
}
