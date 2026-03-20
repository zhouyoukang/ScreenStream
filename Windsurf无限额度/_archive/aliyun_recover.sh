#!/bin/bash
# ========================================
# 阿里云服务全量恢复脚本 v3.0
# 用法: ssh aliyun 'bash -s' < aliyun_recover.sh
# 或:   scp aliyun_recover.sh aliyun:/tmp/ && ssh aliyun bash /tmp/aliyun_recover.sh
# ========================================

set -e
echo "╔══════════════════════════════════════╗"
echo "║  阿里云服务恢复 v3.0                 ║"
echo "║  frps + auth_hub + nginx             ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ==================== 1. frps ====================
echo "=== [1/5] 检查/恢复 frps ==="
FRP_DIR="/opt/frp"
FRPS_BIN="$FRP_DIR/frps"
FRPS_CONF="$FRP_DIR/frps.toml"

if [ ! -f "$FRPS_BIN" ]; then
    echo "[INSTALL] 下载 frps..."
    mkdir -p "$FRP_DIR"
    cd /tmp
    FRP_VER="0.61.1"
    wget -q "https://github.com/fatedier/frp/releases/download/v${FRP_VER}/frp_${FRP_VER}_linux_amd64.tar.gz" -O frp.tar.gz || {
        echo "[WARN] GitHub下载失败，尝试镜像..."
        wget -q "https://mirror.ghproxy.com/https://github.com/fatedier/frp/releases/download/v${FRP_VER}/frp_${FRP_VER}_linux_amd64.tar.gz" -O frp.tar.gz
    }
    tar xzf frp.tar.gz
    cp "frp_${FRP_VER}_linux_amd64/frps" "$FRPS_BIN"
    chmod +x "$FRPS_BIN"
    rm -rf frp.tar.gz "frp_${FRP_VER}_linux_amd64"
    echo "[OK] frps 已安装"
fi

# frps配置
if [ ! -f "$FRPS_CONF" ]; then
    cat > "$FRPS_CONF" << 'FRPS_EOF'
bindPort = 7000
auth.method = "token"
auth.token = "NKLQyCrSavf1MmYOGtkFzbh0"

# Dashboard
webServer.addr = "127.0.0.1"
webServer.port = 7500
webServer.user = "admin"
webServer.password = "frp_admin_2026"

# 日志
log.to = "/var/log/frps.log"
log.level = "info"
log.maxDays = 7

# 允许的端口范围
allowPorts = [
  { start = 13000, end = 13999 },
  { start = 18000, end = 19999 }
]
FRPS_EOF
    echo "[OK] frps.toml 已创建"
fi

# frps systemd service
cat > /etc/systemd/system/frps.service << 'SVC_EOF'
[Unit]
Description=FRP Server
After=network.target

[Service]
Type=simple
ExecStart=/opt/frp/frps -c /opt/frp/frps.toml
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
SVC_EOF

systemctl daemon-reload
systemctl enable frps
systemctl restart frps
sleep 2
if systemctl is-active frps > /dev/null 2>&1; then
    echo "[OK] frps 运行中"
else
    echo "[FAIL] frps 启动失败"
    journalctl -u frps --no-pager -n 5
fi

# ==================== 2. auth_hub ====================
echo ""
echo "=== [2/5] 检查/恢复 auth_hub ==="
HUB_DIR="/opt/windsurf-hub"
mkdir -p "$HUB_DIR" "$HUB_DIR/static"

# 如果本地有新版本，会通过scp上传
if [ -f "$HUB_DIR/auth_hub_v3.py" ]; then
    HUB_SCRIPT="$HUB_DIR/auth_hub_v3.py"
elif [ -f "$HUB_DIR/auth_hub.py" ]; then
    HUB_SCRIPT="$HUB_DIR/auth_hub.py"
else
    echo "[WARN] auth_hub脚本不存在，请先上传: scp auth_hub_v3.py aliyun:$HUB_DIR/"
    HUB_SCRIPT=""
fi

if [ -n "$HUB_SCRIPT" ]; then
    cat > /etc/systemd/system/windsurf-hub.service << SVC2_EOF
[Unit]
Description=Windsurf Auth Hub
After=network.target frps.service

[Service]
Type=simple
WorkingDirectory=$HUB_DIR
ExecStart=/usr/bin/python3 $HUB_SCRIPT
Restart=always
RestartSec=5
Environment=HUB_PORT=18800

[Install]
WantedBy=multi-user.target
SVC2_EOF

    systemctl daemon-reload
    systemctl enable windsurf-hub
    systemctl restart windsurf-hub
    sleep 2
    if systemctl is-active windsurf-hub > /dev/null 2>&1; then
        echo "[OK] windsurf-hub 运行中 (port 18800)"
    else
        echo "[FAIL] windsurf-hub 启动失败"
        journalctl -u windsurf-hub --no-pager -n 5
    fi
fi

# ==================== 3. Nginx ====================
echo ""
echo "=== [3/5] 配置 Nginx ==="

# 检查nginx是否安装
if ! command -v nginx &> /dev/null; then
    echo "[INSTALL] 安装 nginx..."
    apt-get update -qq && apt-get install -y -qq nginx
fi

# Nginx配置 - 反代auth_hub + 静态文件
cat > /etc/nginx/sites-available/windsurf-hub << 'NGX_EOF'
server {
    listen 80;
    server_name aiotvr.xyz;

    # auth_hub dashboard & API
    location /hub/ {
        proxy_pass http://127.0.0.1:18800/hub/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 30s;
    }

    # 部署包分发
    location /agent/ {
        alias /opt/windsurf-hub/static/;
        autoindex off;
        add_header Access-Control-Allow-Origin *;
    }

    # 健康检查
    location /health {
        return 200 '{"status":"ok","server":"aiotvr.xyz"}';
        add_header Content-Type application/json;
    }

    location / {
        return 301 /hub/;
    }
}
NGX_EOF

ln -sf /etc/nginx/sites-available/windsurf-hub /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null

nginx -t 2>/dev/null && {
    systemctl reload nginx
    echo "[OK] Nginx 配置已更新"
} || {
    echo "[FAIL] Nginx 配置语法错误"
    nginx -t
}

# ==================== 4. 防火墙 ====================
echo ""
echo "=== [4/5] 防火墙规则 ==="
# 确保关键端口开放
for port in 22 80 443 7000 18443 18800; do
    iptables -C INPUT -p tcp --dport $port -j ACCEPT 2>/dev/null || {
        iptables -I INPUT -p tcp --dport $port -j ACCEPT
        echo "[OK] 开放端口 $port"
    }
done

# ==================== 5. 验证 ====================
echo ""
echo "=== [5/5] 服务状态验证 ==="
echo ""

check_port() {
    local port=$1 name=$2
    if ss -tlnp | grep -q ":${port} " 2>/dev/null; then
        echo "  [OK] $name (:$port)"
    else
        echo "  [FAIL] $name (:$port) 未监听"
    fi
}

check_port 7000 "frps (FRP Server)"
check_port 18800 "auth_hub (管理中枢)"
check_port 80 "nginx (HTTP)"

# 等待FRP客户端连接
echo ""
echo "  等待台式机frpc连接..."
sleep 3
if ss -tlnp | grep -q ":18443 " 2>/dev/null; then
    echo "  [OK] FRP隧道 (:18443) 已建立"
else
    echo "  [WAIT] FRP隧道 (:18443) 等待台式机frpc连接"
    echo "         台式机执行: frpc.exe -c frpc.toml"
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  恢复完成！                           ║"
echo "║  面板: http://aiotvr.xyz/hub/        ║"
echo "║  FRP: 等待台式机frpc连接              ║"
echo "╚══════════════════════════════════════╝"
