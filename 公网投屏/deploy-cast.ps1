<# 
.SYNOPSIS
    部署公网投屏观看页到 aiotvr.xyz
.DESCRIPTION
    1. 上传 cast/index.html 到服务器
    2. 配置 Nginx /cast/ 路由
    3. 验证部署
#>

param(
    [switch]$NginxOnly,
    [switch]$Verify
)

$ErrorActionPreference = 'Stop'
$SSH = 'aliyun'
$REMOTE_DIR = '/opt/screenstream-cast'
$LOCAL_CAST = Join-Path $PSScriptRoot 'cast'

Write-Host "`n=== 公网投屏 — 部署观看页 ===" -ForegroundColor Cyan

if ($Verify) {
    Write-Host "`n[验证] 检查部署状态..." -ForegroundColor Yellow
    $status = curl.exe -sk -o NUL -w '%{http_code}' 'https://aiotvr.xyz/cast/' 2>$null
    if ($status -eq '200') {
        Write-Host "[OK] https://aiotvr.xyz/cast/ → HTTP $status" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] https://aiotvr.xyz/cast/ → HTTP $status" -ForegroundColor Red
    }
    
    $relayStatus = curl.exe -sk 'https://aiotvr.xyz/relay/api/status' 2>$null | ConvertFrom-Json
    if ($relayStatus.ok) {
        Write-Host "[OK] Relay server: rooms=$($relayStatus.rooms) uptime=$([math]::Round($relayStatus.uptime/3600,1))h" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Relay server not responding" -ForegroundColor Red
    }
    exit
}

# Step 1: Upload files
if (-not $NginxOnly) {
    Write-Host "`n[1/3] 上传观看页..." -ForegroundColor Yellow
    ssh $SSH "mkdir -p $REMOTE_DIR"
    scp -q "$LOCAL_CAST/index.html" "${SSH}:${REMOTE_DIR}/index.html"
    Write-Host "  → $REMOTE_DIR/index.html" -ForegroundColor Green
}

# Step 2: Nginx config
Write-Host "`n[2/3] 配置Nginx..." -ForegroundColor Yellow

$nginxSnippet = @'
    # /cast/ — 公网投屏观看页 (静态HTML)
    location /cast/ {
        alias /opt/screenstream-cast/;
        index index.html;
        add_header Cache-Control "no-store";
        add_header Access-Control-Allow-Origin "*";
    }
'@

# Check if /cast/ already configured
$hasRoute = ssh $SSH "grep -c '/cast/' /www/server/panel/vhost/nginx/aiotvr.xyz.conf 2>/dev/null || echo 0"
if ([int]$hasRoute -eq 0) {
    Write-Host "  Adding /cast/ location to Nginx config..." -ForegroundColor Yellow
    # Insert before the last closing brace
    ssh $SSH @"
sed -i '/^}/i \
    # /cast/ — 公网投屏观看页 (静态HTML)\
    location /cast/ {\
        alias /opt/screenstream-cast/;\
        index index.html;\
        add_header Cache-Control "no-store";\
        add_header Access-Control-Allow-Origin "*";\
    }' /www/server/panel/vhost/nginx/aiotvr.xyz.conf
"@
    ssh $SSH '/etc/init.d/nginx reload'
    Write-Host "  → Nginx reloaded" -ForegroundColor Green
} else {
    Write-Host "  → /cast/ route already configured" -ForegroundColor Green
}

# Step 3: Verify
Write-Host "`n[3/3] 验证..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
$status = curl.exe -sk -o NUL -w '%{http_code}' 'https://aiotvr.xyz/cast/' 2>$null
if ($status -eq '200') {
    Write-Host "`n✅ 部署成功！" -ForegroundColor Green
    Write-Host "  观看页: https://aiotvr.xyz/cast/" -ForegroundColor Cyan
    Write-Host "  使用: https://aiotvr.xyz/cast/?room=XXXXXX&token=screenstream_2026" -ForegroundColor Cyan
} else {
    Write-Host "`n⚠️ HTTP $status — 请检查Nginx配置" -ForegroundColor Yellow
}
