#!/usr/bin/env python3
"""Patch server-watchdog.sh: fix frp_status_for() false positives.

Root cause: frps binds tunnel ports on the server. TCP connect always succeeds
even when the backend service behind the tunnel is dead. The frps API reports
"online" = frpc client registered, NOT backend reachable.

Fix: For HTTP-capable tunnel services, add curl probe after API check.
For non-HTTP services (RDP, agent), trust the API status.
"""

WATCHDOG = "/opt/watchdog/server-watchdog.sh"

with open(WATCHDOG, "r") as f:
    content = f.read()

# The current function (already patched with TCP verify, which doesn't work)
# Find it by looking for the function boundaries
FUNC_START = "frp_status_for() {"
FUNC_END_MARKER = "\n}\n"

idx_start = content.index(FUNC_START)
# Find the closing brace of this function
idx_after_start = idx_start + len(FUNC_START)
idx_end = content.index(FUNC_END_MARKER, idx_after_start) + len(FUNC_END_MARKER)

old_func = content[idx_start:idx_end]
print(f"Found function ({len(old_func)} chars):")
print(old_func[:200] + "...")

# New function: HTTP probe for known HTTP services, API-only for non-HTTP
new_func = '''frp_status_for() {
    local port=$1
    local status
    status=$(echo "$FRP_API_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$port','missing'))" 2>/dev/null)
    if [ "$status" = "online" ]; then
        # API says frpc registered this tunnel. But backend might be dead.
        # frps binds the port, so TCP connect always succeeds - useless for verification.
        # Use HTTP probe for HTTP-capable services to verify end-to-end.
        case "$port" in
            18088|13002|18900|18084)
                # HTTP services: bookshop, agent_web, gateway, input
                local code
                code=$(curl -sk -o /dev/null -w '%{http_code}' --connect-timeout 2 --max-time 3 "http://127.0.0.1:$port/" 2>/dev/null)
                if [ "$code" != "000" ]; then
                    echo "open"
                else
                    echo "closed"
                fi
                ;;
            18443)
                # HTTPS service: windsurf proxy
                local code
                code=$(curl -sk -o /dev/null -w '%{http_code}' --connect-timeout 2 --max-time 3 "https://127.0.0.1:$port/" 2>/dev/null)
                if [ "$code" != "000" ]; then
                    echo "open"
                else
                    echo "closed"
                fi
                ;;
            *)
                # Non-HTTP services (RDP:13389, agent:19903, etc.)
                # Trust frps API status - if frpc registered, assume service is up
                echo "open"
                ;;
        esac
    elif [ "$status" = "missing" ]; then
        # Port not registered in frps at all
        echo "closed"
    else
        echo "closed"
    fi
}
'''

content = content[:idx_start] + new_func + content[idx_end:]

with open(WATCHDOG, "w") as f:
    f.write(content)

print("SUCCESS: frp_status_for() patched with HTTP probe verification")
print("  HTTP-probed ports: 18088(bookshop) 13002(agent_web) 18900(gateway) 18084(input)")
print("  HTTPS-probed ports: 18443(windsurf)")
print("  API-trusted ports: 13389(rdp) 19903(agent) and others")
