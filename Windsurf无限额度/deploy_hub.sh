#!/bin/bash
# Windsurf 授权中枢 — 阿里云一键部署
# 用法: ssh aliyun 'bash -s' < deploy_hub.sh
# 或:   scp deploy_hub.sh aliyun:/tmp/ && ssh aliyun bash /tmp/deploy_hub.sh

set -e

HUB_DIR="/opt/windsurf-hub"
HUB_PORT=18800
SERVICE_NAME="windsurf-hub"

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║  Windsurf 授权中枢 — 阿里云部署              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# 1. 创建目录
echo "[1/5] 创建目录..."
mkdir -p "$HUB_DIR/static"
echo "  OK: $HUB_DIR"

# 2. 复制文件 (如果本地有)
echo "[2/5] 检查文件..."
if [ -f "$HUB_DIR/auth_hub.py" ]; then
    echo "  OK: auth_hub.py 已存在"
else
    echo "  WARN: 请先上传 auth_hub.py 到 $HUB_DIR/"
    echo "  命令: scp auth_hub.py aliyun:$HUB_DIR/"
fi

# 3. 创建 systemd 服务
echo "[3/5] 创建 systemd 服务..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Windsurf Authorization Hub
After=network.target frps.service
Wants=frps.service

[Service]
Type=simple
WorkingDirectory=$HUB_DIR
ExecStart=/usr/bin/python3 $HUB_DIR/auth_hub.py
Restart=always
RestartSec=5
Environment=HUB_PORT=$HUB_PORT

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
echo "  OK: ${SERVICE_NAME}.service 已创建并启用"

# 4. Nginx 配置
echo "[4/5] 配置 Nginx..."
NGINX_CONF="/etc/nginx/sites-available/default"
if grep -q "location /hub/" "$NGINX_CONF" 2>/dev/null; then
    echo "  SKIP: /hub/ 路由已存在"
else
    # 在最后一个 } 之前插入 location 块
    # 使用 sed 在 server 块末尾之前插入
    if grep -q "server {" "$NGINX_CONF"; then
        # 备份
        cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%Y%m%d)"
        # 在文件倒数第二个 } 前插入
        sed -i '/^}/i \
    # Windsurf 授权中枢\
    location /hub/ {\
        proxy_pass http://127.0.0.1:18800/hub/;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
    }' "$NGINX_CONF"
        nginx -t && nginx -s reload
        echo "  OK: Nginx /hub/ 路由已添加"
    else
        echo "  WARN: 无法自动配置 Nginx，请手动添加:"
        echo "    location /hub/ { proxy_pass http://127.0.0.1:18800/hub/; }"
    fi
fi

# 5. 启动服务
echo "[5/5] 启动服务..."
systemctl restart ${SERVICE_NAME}
sleep 2

if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "  OK: 服务已启动"
    # 测试
    RESP=$(curl -s http://127.0.0.1:${HUB_PORT}/api/health 2>/dev/null || echo '{"error":"failed"}')
    echo "  Health: $RESP" | head -c 200
    echo ""
else
    echo "  FAIL: 服务启动失败"
    journalctl -u ${SERVICE_NAME} --no-pager -n 10
fi

echo ""
echo "  ════════════════════════════════════════════════"
echo "  部署完成!"
echo "  面板: https://aiotvr.xyz/hub/"
echo "  API:  https://aiotvr.xyz/hub/api/health"
echo "  ════════════════════════════════════════════════"
echo ""
