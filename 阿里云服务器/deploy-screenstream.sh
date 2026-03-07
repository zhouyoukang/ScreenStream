#!/bin/bash
# ScreenStream 公网投屏部署脚本 — 在阿里云ECS上执行
#
# ⚠️ 注意：Nginx配置部分已过时（2026-02-27）
# 主站Nginx配置已全量重写（含/screen/和/input/反代），
# 本脚本的Nginx注入逻辑不再需要执行。
# 保留本脚本仅供参考FRP端口和htpasswd配置。
#
# 用法：ssh aliyun 'bash -s' < deploy-screenstream.sh
#
# 功能（原始）：
# 1. 配置Nginx反向代理（TLS + WebSocket + Basic Auth）
# 2. 开放FRP端口（18086投屏 + 18084反控）
# 3. 验证部署

set -e

echo "============================================"
echo "  ScreenStream 公网投屏部署"
echo "  服务器: $(hostname) / $(curl -s ifconfig.me 2>/dev/null || echo '60.205.171.100')"
echo "============================================"

# ====================== Step 1: 创建Basic Auth密码文件 ======================
echo "=== Step 1: 创建认证文件 ==="

# 默认用户名screen，密码stream2026（可通过参数覆盖）
SCREEN_USER="${SCREEN_USER:-screen}"
SCREEN_PASS="${SCREEN_PASS:-stream2026}"

# 安装htpasswd工具（如果没有）
if ! command -v htpasswd &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq apache2-utils
fi

# 创建密码文件
htpasswd -bc /etc/nginx/.htpasswd_screen "$SCREEN_USER" "$SCREEN_PASS" 2>/dev/null
echo "认证用户: $SCREEN_USER (密码已设置)"

# ====================== Step 2: Nginx配置 ======================
echo "=== Step 2: 配置Nginx ==="

# 检查SSL证书
SSL_CERT="/etc/letsencrypt/live/aiotvr.xyz/fullchain.pem"
SSL_KEY="/etc/letsencrypt/live/aiotvr.xyz/privkey.pem"

if [ ! -f "$SSL_CERT" ]; then
    # 尝试宝塔路径
    SSL_CERT="/www/server/panel/vhost/cert/aiotvr.xyz/fullchain.pem"
    SSL_KEY="/www/server/panel/vhost/cert/aiotvr.xyz/privkey.pem"
fi

if [ ! -f "$SSL_CERT" ]; then
    echo "警告：未找到SSL证书，将使用HTTP（不安全！）"
    USE_SSL=false
else
    echo "SSL证书: $SSL_CERT"
    USE_SSL=true
fi

# 写入Nginx配置
NGINX_CONF="/etc/nginx/conf.d/screenstream.conf"

# 检查宝塔Nginx路径
if [ -d "/www/server/nginx/conf" ]; then
    NGINX_CONF="/www/server/nginx/conf/vhost/screenstream.conf"
    mkdir -p "$(dirname "$NGINX_CONF")"
fi

cat > "$NGINX_CONF" << 'NGINX_EOF'
# ScreenStream 公网投屏反向代理
# 路径: /screen/ → FRP隧道 → 笔记本ADB → 手机ScreenStream
#
# 访问地址:
#   投屏画面: https://aiotvr.xyz/screen/
#   API状态:  https://aiotvr.xyz/screen/status
#   触控WS:   wss://aiotvr.xyz/screen/ws/touch

# 上游定义：FRP隧道端口
upstream screenstream_backend {
    server 127.0.0.1:18086;
    keepalive 8;
}

upstream screenstream_input {
    server 127.0.0.1:18084;
    keepalive 4;
}

# 在现有server块中添加location（如果已有443 server块）
# 如果没有，需要单独的server块

server {
    listen 8443 ssl http2;
    # 注意：如果8443已被HA占用，改用其他端口如8444
    # 或者直接在现有的443 server块中添加以下location

    server_name aiotvr.xyz;

NGINX_EOF

# 根据SSL可用性调整
if [ "$USE_SSL" = true ]; then
    cat >> "$NGINX_CONF" << NGINX_SSL_EOF
    ssl_certificate $SSL_CERT;
    ssl_certificate_key $SSL_KEY;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
NGINX_SSL_EOF
fi

cat >> "$NGINX_CONF" << 'NGINX_LOCATIONS_EOF'

    # ── 投屏主页面（含视频流+前端+API） ──
    location /screen/ {
        # Basic Auth认证
        auth_basic "ScreenStream";
        auth_basic_user_file /etc/nginx/.htpasswd_screen;

        # 反向代理到FRP隧道
        proxy_pass http://screenstream_backend/;
        proxy_http_version 1.1;

        # WebSocket支持（投屏流+触控）
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 标准代理头
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置（投屏长连接）
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_connect_timeout 10s;

        # 禁用缓冲（实时流）
        proxy_buffering off;
        proxy_cache off;

        # 大文件上传支持
        client_max_body_size 50m;
    }

    # ── 投屏WebSocket专用路径 ──
    location /screen/stream/ {
        auth_basic "ScreenStream";
        auth_basic_user_file /etc/nginx/.htpasswd_screen;

        proxy_pass http://screenstream_backend/stream/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
    }

    # ── 反向控制API（独立端口，同样需要认证） ──
    location /input/ {
        auth_basic "ScreenStream Input";
        auth_basic_user_file /etc/nginx/.htpasswd_screen;

        proxy_pass http://screenstream_input/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }

    # ── 健康检查（无需认证） ──
    location /screen/health {
        proxy_pass http://screenstream_backend/status;
        proxy_connect_timeout 5s;
        proxy_read_timeout 5s;
    }
}
NGINX_LOCATIONS_EOF

echo "Nginx配置已写入: $NGINX_CONF"

# ====================== Step 3: 检查端口冲突 ======================
echo "=== Step 3: 检查端口 ==="

# 检查8443是否已被HA占用
if ss -tlnp | grep -q ':8443 '; then
    echo "警告：端口8443已被占用（可能是HA反代）"
    echo "方案A：修改screenstream.conf使用8444端口"
    echo "方案B：将location块合并到现有的443 server配置中"
    echo ""
    echo "采用方案B：将location添加到主站443配置..."

    # 找到现有的443配置文件
    MAIN_CONF=""
    for f in /www/server/panel/vhost/nginx/aiotvr.xyz.conf /etc/nginx/conf.d/aiotvr.conf /etc/nginx/sites-enabled/default; do
        if [ -f "$f" ]; then
            MAIN_CONF="$f"
            break
        fi
    done

    if [ -n "$MAIN_CONF" ]; then
        echo "找到主站配置: $MAIN_CONF"

        # 检查是否已添加过screenstream配置
        if grep -q 'screenstream_backend' "$MAIN_CONF"; then
            echo "screenstream配置已存在于主站配置中，跳过"
        else
            echo "将screenstream upstream和location添加到主站配置..."
            # 备份
            cp "$MAIN_CONF" "${MAIN_CONF}.bak_screenstream"

            # 在http块开头添加upstream（在server块之前）
            # 创建一个单独的upstream文件
            cat > /etc/nginx/conf.d/screenstream-upstream.conf << 'UPSTREAM_EOF'
# ScreenStream上游定义
upstream screenstream_backend {
    server 127.0.0.1:18086;
    keepalive 8;
}
upstream screenstream_input {
    server 127.0.0.1:18084;
    keepalive 4;
}
UPSTREAM_EOF

            # 在主站443 server块的最后一个}之前插入location
            # 使用sed在最后一个}之前插入
            LOCATION_BLOCK='
    # ── ScreenStream 公网投屏 ──
    location /screen/ {
        auth_basic "ScreenStream";
        auth_basic_user_file /etc/nginx/.htpasswd_screen;
        proxy_pass http://screenstream_backend/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_connect_timeout 10s;
        proxy_buffering off;
        proxy_cache off;
        client_max_body_size 50m;
    }
    location /input/ {
        auth_basic "ScreenStream Input";
        auth_basic_user_file /etc/nginx/.htpasswd_screen;
        proxy_pass http://screenstream_input/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }
    location /screen/health {
        proxy_pass http://screenstream_backend/status;
        proxy_connect_timeout 5s;
        proxy_read_timeout 5s;
    }'

            # 用python安全插入（避免sed转义问题）
            python3 -c "
import re
with open('$MAIN_CONF', 'r') as f:
    content = f.read()
# 在443 server块的最后一个}之前插入
# 找到最后一个}
last_brace = content.rfind('}')
if last_brace > 0:
    content = content[:last_brace] + '''$LOCATION_BLOCK
''' + content[last_brace:]
    with open('$MAIN_CONF', 'w') as f:
        f.write(content)
    print('Location块已插入到主站配置')
else:
    print('错误：未找到server块结束位置')
"
            # 删除独立的screenstream.conf（已合并到主站）
            rm -f "$NGINX_CONF"
            echo "独立配置已删除，改为合并到主站配置"
        fi
    else
        echo "未找到主站Nginx配置，保留独立配置文件"
        echo "请手动将端口改为8444或合并到现有配置"
    fi
fi

# ====================== Step 4: 验证并重载Nginx ======================
echo "=== Step 4: 验证Nginx配置 ==="

nginx -t 2>&1
if [ $? -eq 0 ]; then
    echo "Nginx配置验证通过"
    # 宝塔环境用 /etc/init.d/nginx reload，标准环境用 systemctl
    if [ -f "/etc/init.d/nginx" ]; then
        /etc/init.d/nginx reload
    else
        systemctl reload nginx 2>/dev/null || nginx -s reload
    fi
    echo "Nginx已重载"
else
    echo "错误：Nginx配置有误，请手动检查"
    exit 1
fi

# ====================== Step 5: 检查FRP服务端 ======================
echo "=== Step 5: 检查FRP ==="

if systemctl is-active frps &>/dev/null; then
    echo "frps 运行中 ✅"
else
    echo "frps 未运行，尝试启动..."
    systemctl start frps
fi

# 检查FRP端口
echo "已监听端口:"
ss -tlnp | grep -E '(7000|18086|18084|19903|13389)' || echo "（FRP端口由frps动态分配，客户端连接后才会监听）"

# ====================== Step 6: 防火墙/安全组提醒 ======================
echo ""
echo "============================================"
echo "  部署完成！"
echo "============================================"
echo ""
echo "⚠️  请确保阿里云安全组已开放以下端口："
echo "    - 18086/TCP  (ScreenStream投屏)"
echo "    - 18084/TCP  (ScreenStream反控)"
echo "    注意：如果使用Nginx反代(443)，则不需要直接开放18086/18084"
echo ""
echo "📱 访问地址（Nginx反代，需要认证）："
echo "    投屏: https://aiotvr.xyz/screen/"
echo "    API:  https://aiotvr.xyz/screen/status"
echo "    认证: 用户名=$SCREEN_USER"
echo ""
echo "📱 直连地址（FRP直通，无加密）："
echo "    投屏: http://60.205.171.100:18086/"
echo "    反控: http://60.205.171.100:18084/status"
echo ""
echo "🔧 前置条件（在笔记本上执行）："
echo "    1. 手机USB连接 + adb forward tcp:8086 tcp:8081"
echo "    2. 手机上ScreenStream APP已启动投屏"
echo "    3. frpc已重启（加载新的screenstream隧道配置）"
echo ""
echo "============================================"
