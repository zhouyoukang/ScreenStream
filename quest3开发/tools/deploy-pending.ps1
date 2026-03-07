# Quest3 WebXR 全量部署 (14 demos + 管理页 + 静态资源)
# 更新于 2026-03-06

Write-Host "=== Quest3 WebXR 待部署 ===" -ForegroundColor Cyan

# 0. 检查SSH
Write-Host "`n[0/10] 测试SSH..." -ForegroundColor Yellow
ssh -o ConnectTimeout=10 aliyun "echo SSH_OK"
if ($LASTEXITCODE -ne 0) { Write-Host "SSH仍不可用，等待恢复" -ForegroundColor Red; return }

# 1. 创建目录
Write-Host "`n[1/16] 创建远程目录..." -ForegroundColor Yellow
ssh aliyun "mkdir -p /var/www/quest/shared-space /var/www/quest/smart-home /opt/quest-shared-space"

# 2. 部署 Shared Space
Write-Host "`n[2/16] 部署 shared-space..." -ForegroundColor Yellow
scp "$PSScriptRoot\..\webxr\shared-space\index.html" aliyun:/var/www/quest/shared-space/
scp "$PSScriptRoot\..\webxr\shared-space\server.js" aliyun:/opt/quest-shared-space/server.js
ssh aliyun "cd /opt/quest-shared-space && npm init -y 2>/dev/null; npm install ws 2>/dev/null"

# 3. 部署 Smart Home MR
Write-Host "`n[3/16] 部署 smart-home..." -ForegroundColor Yellow
scp "$PSScriptRoot\..\webxr\smart-home\index.html" aliyun:/var/www/quest/smart-home/

# 4. 部署 4个新Demo (Three.js)
Write-Host "`n[4/16] 部署 ar-placement..." -ForegroundColor Yellow
ssh aliyun "mkdir -p /var/www/quest/ar-placement /var/www/quest/hand-physics /var/www/quest/controller-shooter /var/www/quest/spatial-audio"
scp "$PSScriptRoot\..\webxr\ar-placement\index.html" aliyun:/var/www/quest/ar-placement/

Write-Host "`n[5/16] 部署 hand-physics..." -ForegroundColor Yellow
scp "$PSScriptRoot\..\webxr\hand-physics\index.html" aliyun:/var/www/quest/hand-physics/

Write-Host "`n[6/16] 部署 controller-shooter..." -ForegroundColor Yellow
scp "$PSScriptRoot\..\webxr\controller-shooter\index.html" aliyun:/var/www/quest/controller-shooter/

Write-Host "`n[7/16] 部署 spatial-audio..." -ForegroundColor Yellow
scp "$PSScriptRoot\..\webxr\spatial-audio\index.html" aliyun:/var/www/quest/spatial-audio/

# 8. 部署 gaussian-splat + vr-painter
Write-Host "`n[8/16] 部署 gaussian-splat..." -ForegroundColor Yellow
ssh aliyun "mkdir -p /var/www/quest/gaussian-splat /var/www/quest/vr-painter"
scp "$PSScriptRoot\..\webxr\gaussian-splat\index.html" aliyun:/var/www/quest/gaussian-splat/

Write-Host "`n[9/16] 部署 vr-painter..." -ForegroundColor Yellow
scp "$PSScriptRoot\..\webxr\vr-painter\index.html" aliyun:/var/www/quest/vr-painter/

# 10. 部署 libs + fonts (A-Frame demos依赖)
Write-Host "`n[10/16] 部署 libs + fonts..." -ForegroundColor Yellow
ssh aliyun "mkdir -p /var/www/quest/libs /var/www/quest/fonts"
scp "$PSScriptRoot\..\webxr\libs\aframe.min.js" aliyun:/var/www/quest/libs/
scp "$PSScriptRoot\..\webxr\libs\aframe-gaussian-splatting.js" aliyun:/var/www/quest/libs/
scp "$PSScriptRoot\..\webxr\fonts\mozillavr.fnt" aliyun:/var/www/quest/fonts/
scp "$PSScriptRoot\..\webxr\fonts\mozillavr.png" aliyun:/var/www/quest/fonts/

# 11. 部署 devops + simulator + iwe.min.js
Write-Host "`n[11/16] 部署 devops + simulator..." -ForegroundColor Yellow
scp "$PSScriptRoot\..\webxr\devops.html" aliyun:/var/www/quest/
scp "$PSScriptRoot\..\webxr\simulator.html" aliyun:/var/www/quest/
scp "$PSScriptRoot\..\webxr\iwe.min.js" aliyun:/var/www/quest/
scp "$PSScriptRoot\..\webxr\favicon.ico" aliyun:/var/www/quest/

# 12. 更新 portal 首页
Write-Host "`n[12/16] 更新 portal..." -ForegroundColor Yellow
scp "$PSScriptRoot\..\webxr\index.html" aliyun:/var/www/quest/

# 13. 配置服务端 (手动)
Write-Host "`n[13/16] 服务端配置 (需手动添加):" -ForegroundColor Red
Write-Host @"

Nginx (/etc/nginx/sites-available/default):
    location /quest-ws/ {
        proxy_pass http://127.0.0.1:9200/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade `$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host `$host;
        proxy_read_timeout 86400;
    }

Systemd (/etc/systemd/system/quest-ws.service):
[Unit]
Description=Quest Shared Space WebSocket
After=network.target
[Service]
Type=simple
WorkingDirectory=/opt/quest-shared-space
ExecStart=/usr/bin/node server.js
Restart=always
Environment=PORT=9200
[Install]
WantedBy=multi-user.target

然后: sudo nginx -t && sudo systemctl reload nginx
      sudo systemctl enable --now quest-ws
"@

# 14. 验证
Write-Host "`n[14/16] 验证..." -ForegroundColor Cyan
@(
    "https://aiotvr.xyz/quest/",
    "https://aiotvr.xyz/quest/shared-space/",
    "https://aiotvr.xyz/quest/smart-home/",
    "https://aiotvr.xyz/quest/ar-placement/",
    "https://aiotvr.xyz/quest/hand-physics/",
    "https://aiotvr.xyz/quest/controller-shooter/",
    "https://aiotvr.xyz/quest/spatial-audio/",
    "https://aiotvr.xyz/quest/gaussian-splat/",
    "https://aiotvr.xyz/quest/vr-painter/",
    "https://aiotvr.xyz/quest/devops.html",
    "https://aiotvr.xyz/quest/simulator.html"
) | ForEach-Object {
    $code = curl.exe -sk -o NUL -w "%{http_code}" $_ -m 10
    Write-Host "$code $_"
}

Write-Host "`n[15/16] 验证libs/fonts..." -ForegroundColor Cyan
@(
    "https://aiotvr.xyz/quest/libs/aframe.min.js",
    "https://aiotvr.xyz/quest/libs/aframe-gaussian-splatting.js",
    "https://aiotvr.xyz/quest/fonts/mozillavr.fnt"
) | ForEach-Object {
    $code = curl.exe -sk -o NUL -w "%{http_code}" $_ -m 10
    Write-Host "$code $_"
}

Write-Host "`n[16/16] 完成!" -ForegroundColor Green
Write-Host "所有14个demo + 管理页 + 静态资源已部署" -ForegroundColor Cyan
