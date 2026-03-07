#!/bin/bash
# 亲情远程 — 信令服务器部署脚本
# 部署正确的亲情远程信令到:9101, 更新nginx /signal/ 指向

set -e

echo "=== 1. Install dependencies ==="
cd /opt/family-remote-signaling
npm install --production 2>&1 | tail -3

echo "=== 2. Kill old family-signaling if any ==="
# Kill any process on port 9101
fuser -k 9101/tcp 2>/dev/null || true
sleep 1

echo "=== 3. Start family-remote signaling on :9101 ==="
PORT=9101 nohup node server.js > /var/log/family-signaling.log 2>&1 &
echo "PID=$!"
sleep 2

echo "=== 4. Verify signaling server ==="
curl -s -m 3 http://127.0.0.1:9101/api/status || echo "FAILED: signaling not responding"

echo "=== 5. Update nginx /signal/ → :9101 ==="
NGINX_CONF="/etc/nginx/sites-enabled/default"
if grep -q 'location /signal/' "$NGINX_CONF"; then
  # Backup
  cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%s)"
  # Fix: port 9801 (non-existent!) → 9101 (new family-remote signaling)
  # Also remove trailing slash to preserve WebSocket path
  sed -i '/location \/signal\//,/}/ s|proxy_pass http://127.0.0.1:9801/;|proxy_pass http://127.0.0.1:9101;|' "$NGINX_CONF"
  sed -i '/location \/signal\//,/}/ s|proxy_pass http://127.0.0.1:9801;|proxy_pass http://127.0.0.1:9101;|' "$NGINX_CONF"
  echo "Updated nginx /signal/ → :9101 (was :9801 - non-existent!)"
  grep -A 3 'location /signal/' "$NGINX_CONF"
else
  echo "WARNING: /signal/ location not found in nginx config"
fi

echo "=== 6. Deploy latest viewer ==="
cp /tmp/viewer-index.html /opt/screenstream-cast/index.html
echo "Viewer deployed"

echo "=== 7. Reload nginx ==="
nginx -t && nginx -s reload
echo "Nginx reloaded"

echo "=== 8. Final verification ==="
sleep 1
echo "Signaling API:"
curl -s -m 3 http://127.0.0.1:9101/api/status
echo ""
echo "Relay API:"
curl -s -m 3 http://127.0.0.1:9800/api/status
echo ""
echo "Health ping:"
curl -s -m 3 http://127.0.0.1:9101/app/ping -w "HTTP %{http_code}" -o /dev/null
echo ""

echo "=== DONE ==="
