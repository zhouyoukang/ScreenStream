#!/bin/bash
# ============================================================
# Aliyun Server Watchdog + Dynamic Health Endpoint
# Cron: * * * * * /opt/watchdog/server-watchdog.sh
#
# 1. Check all services, generate /api/health JSON
# 2. Auto-restart crashed services (self-healing)
# 3. Write status to /www/wwwroot/aiotvr.xyz/health.json
# ============================================================

HEALTH_FILE="/www/wwwroot/aiotvr.xyz/health.json"
LOG_FILE="/var/log/watchdog.log"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Service checks ---

check_systemd() {
    systemctl is-active "$1" >/dev/null 2>&1 && echo "active" || echo "inactive"
}

check_port() {
    ss -tlnp | grep -q ":$1 " && echo "open" || echo "closed"
}

check_frp_tunnel() {
    # FRP tunnels: ss shows port bound by frps, but client may be disconnected
    # Do actual TCP connect to verify end-to-end reachability
    if ! ss -tlnp | grep -q ":$1 "; then
        echo "closed"
        return
    fi
    # Port is bound, verify actual connectivity (2s timeout)
    if timeout 2 bash -c "echo > /dev/tcp/127.0.0.1/$1" 2>/dev/null; then
        echo "open"
    else
        echo "closed"
    fi
}

check_http() {
    local code
    code=$(curl -sk -o /dev/null -w '%{http_code}' "$1" --connect-timeout 3 2>/dev/null)
    echo "$code"
}

check_docker() {
    docker inspect -f '{{.State.Status}}' "$1" 2>/dev/null || echo "none"
}

# --- Collect status ---

FRPS_STATUS=$(check_systemd frps)
RELAY_STATUS=$(check_systemd ss-relay)
NGINX_PID=$(pgrep -c nginx 2>/dev/null || echo 0)
HA_STATUS=$(check_docker homeassistant_haa7-homeassistant_haA7-1)

PORT_7000=$(check_port 7000)
PORT_9100=$(check_port 9100)
PORT_8123=$(check_port 8123)
PORT_443=$(check_port 443)

HTTP_MAIN=$(check_http "https://127.0.0.1/" )
HTTP_RELAY=$(check_http "http://127.0.0.1:9100/app/ping")
HTTP_HA=$(check_http "http://127.0.0.1:8123/")

# FRP tunnel status via frps dashboard API (authoritative source)
# Fallback to ss-based check if API unavailable
FRP_API_JSON=$(python3 /opt/watchdog/frp_status.py --json 2>/dev/null || echo "{}")

frp_status_for() {
    local port=$1
    local status
    status=$(echo "$FRP_API_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$port','missing'))" 2>/dev/null)
    if [ "$status" = "online" ]; then
        echo "open"
    elif [ "$status" = "missing" ]; then
        # Port not registered in frps at all
        echo "closed"
    else
        echo "closed"
    fi
}

FRP_AGENT=$(frp_status_for 19903)
FRP_RDP=$(frp_status_for 13389)
FRP_SS=$(frp_status_for 18086)
FRP_INPUT=$(frp_status_for 18084)
FRP_GW=$(frp_status_for 18900)
FRP_BOOK=$(frp_status_for 18088)
FRP_WINDSURF=$(frp_status_for 18443)
FRP_AGENT_WEB=$(frp_status_for 13002)
# GhostShell (18000) removed - project archived to 管理/00-归档/old-agent-scripts/

# System resources
DISK_FREE=$(df -h / | awk 'NR==2{print $4}')
DISK_PERCENT=$(df / | awk 'NR==2{print $5}')
MEM_USED=$(free -m | awk '/^Mem:/{print $3}')
MEM_TOTAL=$(free -m | awk '/^Mem:/{print $2}')
MEM_PERCENT=$((MEM_USED * 100 / MEM_TOTAL))
UPTIME_SEC=$(cat /proc/uptime | awk '{print int($1)}')
LOAD=$(cat /proc/loadavg | awk '{print $1}')

# SSL expiry
SSL_EXPIRY="unknown"
SSL_DAYS=-1
if [ -f /etc/letsencrypt/live/aiotvr.xyz/fullchain.pem ]; then
    SSL_EXPIRY=$(openssl x509 -enddate -noout -in /etc/letsencrypt/live/aiotvr.xyz/fullchain.pem 2>/dev/null | cut -d= -f2)
    SSL_EPOCH=$(date -d "$SSL_EXPIRY" +%s 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    if [ "$SSL_EPOCH" -gt 0 ]; then
        SSL_DAYS=$(( (SSL_EPOCH - NOW_EPOCH) / 86400 ))
    fi
fi

# --- Self-healing ---

HEALED=""

if [ "$FRPS_STATUS" = "inactive" ]; then
    systemctl start frps 2>/dev/null
    HEALED="${HEALED}frps,"
    echo "[$TIMESTAMP] HEAL: restarted frps" >> "$LOG_FILE"
fi

if [ "$RELAY_STATUS" = "inactive" ]; then
    systemctl start ss-relay 2>/dev/null
    HEALED="${HEALED}ss-relay,"
    echo "[$TIMESTAMP] HEAL: restarted ss-relay" >> "$LOG_FILE"
fi

if [ "$NGINX_PID" -eq 0 ]; then
    if [ -f "/etc/init.d/nginx" ]; then
        /etc/init.d/nginx start 2>/dev/null
    else
        systemctl start nginx 2>/dev/null
    fi
    HEALED="${HEALED}nginx,"
    echo "[$TIMESTAMP] HEAL: restarted nginx" >> "$LOG_FILE"
fi

if [ "$HA_STATUS" != "running" ] && [ "$HA_STATUS" != "none" ]; then
    docker start homeassistant_haa7-homeassistant_haA7-1 2>/dev/null
    HEALED="${HEALED}ha-docker,"
    echo "[$TIMESTAMP] HEAL: restarted ha-docker" >> "$LOG_FILE"
fi

# Remove trailing comma
HEALED="${HEALED%,}"

# --- Count tunnels ---
TUNNEL_COUNT=0
for p in $FRP_AGENT $FRP_RDP $FRP_SS $FRP_INPUT $FRP_GW $FRP_BOOK $FRP_WINDSURF $FRP_AGENT_WEB; do
    [ "$p" = "open" ] && TUNNEL_COUNT=$((TUNNEL_COUNT + 1))
done

# --- Determine overall status ---
OVERALL="ok"
ISSUES=""
[ "$FRPS_STATUS" != "active" ] && OVERALL="degraded" && ISSUES="${ISSUES}frps-down,"
[ "$RELAY_STATUS" != "active" ] && OVERALL="degraded" && ISSUES="${ISSUES}relay-down,"
[ "$NGINX_PID" -eq 0 ] && OVERALL="critical" && ISSUES="${ISSUES}nginx-down,"
[ "$SSL_DAYS" -lt 14 ] && [ "$SSL_DAYS" -ge 0 ] && OVERALL="warning" && ISSUES="${ISSUES}ssl-expiring,"
[ "$MEM_PERCENT" -gt 90 ] && ISSUES="${ISSUES}mem-high,"
ISSUES="${ISSUES%,}"

# --- Generate JSON ---
cat > "$HEALTH_FILE" << JSONEOF
{
  "server": "aiotvr.xyz",
  "ip": "60.205.171.100",
  "status": "$OVERALL",
  "timestamp": "$TIMESTAMP",
  "issues": "$([ -n "$ISSUES" ] && echo "$ISSUES" || echo "none")",
  "healed": "$([ -n "$HEALED" ] && echo "$HEALED" || echo "none")",
  "services": {
    "frps": "$FRPS_STATUS",
    "ss_relay": "$RELAY_STATUS",
    "nginx": $([ "$NGINX_PID" -gt 0 ] && echo '"active"' || echo '"inactive"'),
    "ha_docker": "$HA_STATUS"
  },
  "ports": {
    "443_https": "$PORT_443",
    "7000_frp": "$PORT_7000",
    "9100_relay": "$PORT_9100",
    "8123_ha": "$PORT_8123"
  },
  "frp_tunnels": {
    "count": $TUNNEL_COUNT,
    "agent_19903": "$FRP_AGENT",
    "rdp_13389": "$FRP_RDP",
    "ss_18086": "$FRP_SS",
    "input_18084": "$FRP_INPUT",
    "gateway_18900": "$FRP_GW",
    "bookshop_18088": "$FRP_BOOK",
    "windsurf_18443": "$FRP_WINDSURF",
    "agent_web_13002": "$FRP_AGENT_WEB"
  },
  "http_checks": {
    "main_443": "$HTTP_MAIN",
    "relay_9100": "$HTTP_RELAY",
    "ha_8123": "$HTTP_HA"
  },
  "ssl": {
    "expiry": "$SSL_EXPIRY",
    "days_remaining": $SSL_DAYS
  },
  "system": {
    "uptime_sec": $UPTIME_SEC,
    "load": "$LOAD",
    "mem_used_mb": $MEM_USED,
    "mem_total_mb": $MEM_TOTAL,
    "mem_percent": $MEM_PERCENT,
    "disk_free": "$DISK_FREE",
    "disk_percent": "$DISK_PERCENT"
  }
}
JSONEOF

# Rotate log (keep last 1000 lines)
if [ -f "$LOG_FILE" ] && [ $(wc -l < "$LOG_FILE") -gt 1000 ]; then
    tail -500 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi
