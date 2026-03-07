#!/bin/bash
# 微信公众号 Nginx 反代部署
#
# ⚠️ 注意：Nginx注入部分已过时（2026-02-27）
# 主站Nginx已全量重写（含/wx反代），本脚本的注入逻辑不再需要。
# 保留仅供参考。
#
# 用法: ssh aliyun 'bash -s' < 阿里云服务器/deploy-wechat-nginx.sh

set -e
echo "=== 微信公众号 Nginx 反代部署 ==="

MAIN_CONF=""
for f in /www/server/panel/vhost/nginx/aiotvr.xyz.conf /etc/nginx/conf.d/aiotvr.conf; do
    if [ -f "$f" ]; then
        MAIN_CONF="$f"
        break
    fi
done

if [ -z "$MAIN_CONF" ]; then
    echo "错误: 未找到主站Nginx配置"
    exit 1
fi

echo "主站配置: $MAIN_CONF"

# 检查是否已配置
if grep -q 'location /wx' "$MAIN_CONF"; then
    echo "/wx 反代已存在，跳过 ✅"
else
    echo "添加 /wx 反代配置..."
    cp "$MAIN_CONF" "${MAIN_CONF}.bak_wx_$(date +%Y%m%d)"

    # 在最后一个 } 之前插入 location 块
    python3 << 'PYEOF'
import sys

conf_path = None
for f in ['/www/server/panel/vhost/nginx/aiotvr.xyz.conf', '/etc/nginx/conf.d/aiotvr.conf']:
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
    # ── 微信公众号消息接口 (FRP穿透到笔记本Gateway:8900) ──
    location /wx {
        proxy_pass http://127.0.0.1:18900/wx;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 10s;
        proxy_connect_timeout 5s;
    }

    # 微信管理API
    location /wx/ {
        proxy_pass http://127.0.0.1:18900/wx/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
"""

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
    echo "错误: Nginx配置有误，回滚..."
    BACKUP=$(ls -t ${MAIN_CONF}.bak_wx_* 2>/dev/null | head -1)
    if [ -n "$BACKUP" ]; then
        cp "$BACKUP" "$MAIN_CONF"
        nginx -s reload 2>/dev/null
        echo "已回滚"
    fi
    exit 1
fi

# 验证
echo ""
echo "=== 验证 ==="
echo "  /wx (GET): $(curl -sk -o /dev/null -w '%{http_code}' http://127.0.0.1:18900/wx/status --connect-timeout 3 2>/dev/null || echo 'FRP未连接')"
echo ""
echo "部署完成 ✅"
echo "公网URL: https://aiotvr.xyz/wx"
echo ""
echo "微信后台填写:"
echo "  URL:   https://aiotvr.xyz/wx"
echo "  Token: smarthome2026"
