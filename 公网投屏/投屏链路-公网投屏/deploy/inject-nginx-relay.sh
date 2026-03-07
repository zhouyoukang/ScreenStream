#!/bin/bash
set -e
CONF="/www/server/panel/vhost/nginx/aiotvr.xyz.conf"

echo "=== Nginx Relay注入 ==="

# 1. Backup
cp "$CONF" "${CONF}.bak_relay"
echo "Backed up"

# 2. Inject location blocks (no upstream, direct proxy_pass)
python3 -c "
import sys
with open('$CONF','r') as f: c=f.read()
if '/cast/' in c:
    print('Already configured, skip'); sys.exit(0)
loc='''
    # -- WebRTC Relay (direct proxy) --
    location /cast/ {
        proxy_pass http://127.0.0.1:9100/;
        proxy_http_version 1.1;
        proxy_set_header Host \\\$host;
        proxy_set_header X-Real-IP \\\$remote_addr;
        proxy_set_header X-Forwarded-For \\\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\\$scheme;
    }
    location /app/socket {
        proxy_pass http://127.0.0.1:9100/app/socket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \\\$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host \\\$host;
        proxy_set_header X-Real-IP \\\$remote_addr;
        proxy_set_header X-Forwarded-For \\\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\\$scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
    }
    location /app/ {
        proxy_pass http://127.0.0.1:9100/app/;
        proxy_set_header Host \\\$host;
        proxy_set_header X-Real-IP \\\$remote_addr;
    }
'''
i=c.rfind('}')
if i>0:
    c=c[:i]+loc+c[i:]
    with open('$CONF','w') as f: f.write(c)
    print('Injected OK')
else:
    print('ERROR: no closing brace'); sys.exit(1)
"

# 3. Test and reload
nginx -t 2>&1
/etc/init.d/nginx reload 2>/dev/null || systemctl reload nginx 2>/dev/null || nginx -s reload
echo "Nginx reloaded"

# 4. Verify
sleep 1
echo "ping: $(curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/app/ping -m 3)"
echo "cast: $(curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/cast/ -m 3)"
echo "=== DONE ==="
