#!/bin/bash
# ScreenStream WebRTC Relay 一键部署脚本
# 用法: ssh aliyun 'bash -s' < 阿里云服务器/deploy-relay.sh
#
# ⚠️ 注意：Nginx注入部分已过时（2026-02-27）
# 主站Nginx已全量重写（含/cast/、/app/反代），Step 3的注入逻辑不再需要。
# Step 1-2（Node启动）和 Step 4（systemd）仍然有效。
#
# 功能:
# 1. 启动信令服务器 (node server.js on :9100)
# 2. [过时] 在现有Nginx 443配置中添加 /cast/ + /app/ 反代
# 3. 验证HTTPS可达

set -e
echo "==========================================="
echo "  WebRTC Relay Server 部署"
echo "==========================================="

APP_DIR="/www/dk_project/screenstream-relay"

# ─── Step 1: 检查文件 ───
echo "=== Step 1: 检查文件 ==="
if [ ! -f "$APP_DIR/server.js" ]; then
    echo "错误: $APP_DIR/server.js 不存在，请先SCP传输文件"
    exit 1
fi
if [ ! -d "$APP_DIR/node_modules" ]; then
    echo "安装依赖..."
    cd "$APP_DIR" && npm install --production 2>&1 | tail -3
fi
echo "文件检查通过 ✅"

# ─── Step 2: 启动/重启 Node 服务 ───
echo "=== Step 2: 启动信令服务器 ==="

# 杀掉旧进程
pkill -f "node $APP_DIR/server.js" 2>/dev/null || true
sleep 1

# 启动新进程 (nohup + 日志)
cd "$APP_DIR"
PORT=9100 nohup node server.js >> /tmp/ss-relay.log 2>&1 &
RELAY_PID=$!
sleep 2

# 验证启动
if kill -0 $RELAY_PID 2>/dev/null; then
    echo "信令服务器已启动 PID=$RELAY_PID ✅"
    tail -2 /tmp/ss-relay.log
else
    echo "错误: 服务器启动失败"
    cat /tmp/ss-relay.log | tail -10
    exit 1
fi

# 本地验证
PING_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9100/app/ping --connect-timeout 3)
if [ "$PING_CODE" = "204" ]; then
    echo "API /app/ping 返回 204 ✅"
else
    echo "警告: /app/ping 返回 $PING_CODE"
fi

# ─── Step 3: 配置 Nginx ───
echo "=== Step 3: 配置Nginx反代 ==="

# 找主站配置
MAIN_CONF=""
for f in /www/server/panel/vhost/nginx/aiotvr.xyz.conf /etc/nginx/conf.d/aiotvr.conf /etc/nginx/sites-enabled/default; do
    if [ -f "$f" ]; then
        MAIN_CONF="$f"
        break
    fi
done

if [ -z "$MAIN_CONF" ]; then
    echo "警告: 未找到主站Nginx配置，跳过Nginx配置"
    echo "请手动添加反代规则"
else
    echo "主站配置: $MAIN_CONF"

    # 检查是否已配置
    if grep -q 'ss_relay_backend' "$MAIN_CONF"; then
        echo "relay反代已存在，跳过 ✅"
    else
        echo "添加relay反代配置..."
        cp "$MAIN_CONF" "${MAIN_CONF}.bak_relay_$(date +%Y%m%d)"

        # 创建upstream文件
        UPSTREAM_CONF="/etc/nginx/conf.d/ss-relay-upstream.conf"
        # 宝塔环境
        if [ -d "/www/server/nginx/conf/vhost" ]; then
            UPSTREAM_CONF="/www/server/nginx/conf/vhost/ss-relay-upstream.conf"
        fi

        cat > "$UPSTREAM_CONF" << 'EOF'
# ScreenStream WebRTC Relay 上游
upstream ss_relay_backend {
    server 127.0.0.1:9100;
    keepalive 4;
}

# WebSocket upgrade map (if not already defined)
map $http_upgrade $ss_connection_upgrade {
    default upgrade;
    ''      close;
}
EOF
        echo "Upstream配置: $UPSTREAM_CONF"

        # 用python在主站443 server块最后一个}前插入location
        python3 << 'PYEOF'
import re, sys

conf_path = None
for f in ['/www/server/panel/vhost/nginx/aiotvr.xyz.conf', '/etc/nginx/conf.d/aiotvr.conf', '/etc/nginx/sites-enabled/default']:
    try:
        with open(f, 'r') as fh:
            content = fh.read()
        conf_path = f
        break
    except FileNotFoundError:
        continue

if not conf_path:
    print("错误: 无法读取Nginx配置")
    sys.exit(1)

location_block = """
    # ── WebRTC Relay 信令服务器 ──
    # Web客户端
    location /cast/ {
        proxy_pass http://ss_relay_backend/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Socket.IO 信令通道 (Android app + Web client)
    location /app/socket {
        proxy_pass http://ss_relay_backend/app/socket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $ss_connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
    }

    # Nonce + Ping API
    location /app/ {
        proxy_pass http://ss_relay_backend/app/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Relay status API
    location /api/relay-status {
        proxy_pass http://ss_relay_backend/api/status;
        proxy_set_header Host $host;
    }
"""

# Find the last } in the 443 server block
last_brace = content.rfind('}')
if last_brace > 0:
    content = content[:last_brace] + location_block + '\n' + content[last_brace:]
    with open(conf_path, 'w') as fh:
        fh.write(content)
    print(f"Location块已插入: {conf_path}")
else:
    print("错误: 未找到server块结束位置")
    sys.exit(1)
PYEOF
    fi

    # 验证并重载
    echo "验证Nginx配置..."
    nginx -t 2>&1
    if [ $? -eq 0 ]; then
        if [ -f "/etc/init.d/nginx" ]; then
            /etc/init.d/nginx reload
        else
            systemctl reload nginx 2>/dev/null || nginx -s reload
        fi
        echo "Nginx已重载 ✅"
    else
        echo "错误: Nginx配置有误"
        # 回滚
        cp "${MAIN_CONF}.bak_relay_$(date +%Y%m%d)" "$MAIN_CONF" 2>/dev/null
        nginx -s reload 2>/dev/null
        echo "已回滚Nginx配置"
        exit 1
    fi
fi

# ─── Step 4: 创建开机自启 ───
echo "=== Step 4: 开机自启 ==="

# 用简单的rc.local方式 (兼容宝塔环境)
STARTUP_CMD="cd $APP_DIR && PORT=9100 nohup node server.js >> /tmp/ss-relay.log 2>&1 &"

if [ -f /etc/rc.local ]; then
    if ! grep -q 'ss-relay' /etc/rc.local; then
        sed -i "/^exit 0/i # ScreenStream Relay\n$STARTUP_CMD" /etc/rc.local 2>/dev/null || \
        echo "$STARTUP_CMD" >> /etc/rc.local
        echo "已添加到 /etc/rc.local"
    else
        echo "rc.local中已存在，跳过"
    fi
else
    # 创建systemd service作为备选
    cat > /etc/systemd/system/ss-relay.service << EOF
[Unit]
Description=ScreenStream WebRTC Relay
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=PORT=9100
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable ss-relay
    echo "systemd服务已创建并启用"
fi

# ─── Step 5: 验证 ───
echo ""
echo "==========================================="
echo "  部署完成！验证中..."
echo "==========================================="

# 验证本地
echo ""
echo "本地验证:"
echo "  /app/ping:  $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9100/app/ping --connect-timeout 3)"
echo "  /app/nonce: $(curl -s http://127.0.0.1:9100/app/nonce --connect-timeout 3 | head -c 16)..."
echo "  /api/status: $(curl -s http://127.0.0.1:9100/api/status --connect-timeout 3)"

# 验证HTTPS (如果Nginx已配置)
echo ""
echo "HTTPS验证 (通过Nginx):"
echo "  /app/ping:  $(curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/app/ping --connect-timeout 3 2>/dev/null || echo 'N/A')"
echo "  /cast/:     $(curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/cast/ --connect-timeout 3 2>/dev/null || echo 'N/A')"

echo ""
echo "📱 公网访问地址:"
echo "  Web客户端:    https://aiotvr.xyz/cast/"
echo "  快捷加入:     https://aiotvr.xyz/cast/?id=12345678"
echo "  Relay状态:    https://aiotvr.xyz/api/relay-status"
echo "  信令Socket:   wss://aiotvr.xyz/app/socket"
echo ""
echo "📱 Android BuildConfig:"
echo '  SIGNALING_SERVER = "https://aiotvr.xyz"'
echo '  CLOUD_PROJECT_NUMBER = "0"'
echo ""
echo "  PID: $(pgrep -f 'node server.js' || echo 'N/A')"
echo "  日志: tail -f /tmp/ss-relay.log"
echo "==========================================="
