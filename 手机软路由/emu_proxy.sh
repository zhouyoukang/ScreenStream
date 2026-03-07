#!/system/bin/sh
# LDPlayer Emulator Proxy Helper
# Requires: Root (su), V2rayNG running with tun0
# Usage: su -c 'sh /sdcard/Download/emu_proxy.sh [start|stop|status]'
#
# LDPlayer cannot create WiFi hotspot (no AP hardware in VirtualBox).
# Instead, V2rayNG allow-lan exposes SOCKS5 on all interfaces.
# This script adds iptables REDIRECT for transparent proxy (optional).
#
# Architecture:
#   LDPlayer wlan0 (192.168.31.x, bridged to PC LAN)
#     └─► V2rayNG tun0 (VPN tunnel)
#         └─► SOCKS5 :::10808 (allow-lan, any LAN device can use)
#
# For transparent proxy (redirect all VM traffic through VPN):
#   iptables -t nat -A OUTPUT -p tcp ! -d 192.168.31.0/24 -j REDIRECT --to-port 10808

ACTION="${1:-status}"
TUN="tun0"
SOCKS_PORT=10808
LAN_SUBNET="192.168.31.0/24"

log() { echo "[emu_proxy] $1"; }

do_status() {
    log "=== LDPlayer Proxy Status ==="

    # VPN tunnel
    if ip addr show $TUN 2>/dev/null | grep -q "inet"; then
        TUN_IP=$(ip addr show $TUN | grep 'inet ' | awk '{print $2}')
        log "VPN tun0: UP ($TUN_IP)"
    else
        log "VPN tun0: DOWN (start V2rayNG first!)"
    fi

    # wlan0 IP
    WLAN_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}')
    log "wlan0: $WLAN_IP"

    # SOCKS5 port
    if netstat -tlnp 2>/dev/null | grep -q ":::$SOCKS_PORT"; then
        log "SOCKS5: :::$SOCKS_PORT (allow-lan OK)"
    elif netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:$SOCKS_PORT"; then
        log "SOCKS5: 127.0.0.1:$SOCKS_PORT (localhost only! Enable allow-lan)"
    else
        log "SOCKS5: NOT listening"
    fi

    # IP forwarding
    FWD=$(cat /proc/sys/net/ipv4/ip_forward)
    log "IP forward: $FWD"

    # iptables redirect rules
    RULES=$(iptables -t nat -L OUTPUT -n 2>/dev/null | grep -c "REDIRECT")
    log "Redirect rules: $RULES"

    # Root check
    ID=$(id -u)
    log "UID: $ID ($([ $ID -eq 0 ] && echo 'root' || echo 'not root'))"
}

do_start() {
    log "=== Enabling Transparent Redirect ==="

    # Check VPN
    if ! ip addr show $TUN 2>/dev/null | grep -q "inet"; then
        log "ERROR: VPN tun0 not found. Start V2rayNG first!"
        return 1
    fi

    # Enable IP forwarding
    echo 1 > /proc/sys/net/ipv4/ip_forward
    log "IP forwarding enabled"

    # Clear old redirect rules
    iptables -t nat -D OUTPUT -p tcp ! -d $LAN_SUBNET -j REDIRECT --to-port $SOCKS_PORT 2>/dev/null

    # Add redirect: all outbound TCP (except LAN) → SOCKS5
    iptables -t nat -A OUTPUT -p tcp ! -d $LAN_SUBNET -j REDIRECT --to-port $SOCKS_PORT
    log "Redirect: TCP ! $LAN_SUBNET → :$SOCKS_PORT"

    log "=== Transparent Redirect ACTIVE ==="
    do_status
}

do_stop() {
    log "=== Disabling Transparent Redirect ==="

    iptables -t nat -D OUTPUT -p tcp ! -d $LAN_SUBNET -j REDIRECT --to-port $SOCKS_PORT 2>/dev/null
    echo 0 > /proc/sys/net/ipv4/ip_forward
    log "Redirect rules removed, IP forwarding disabled"

    log "=== Transparent Redirect STOPPED ==="
}

case "$ACTION" in
    start)  do_start ;;
    stop)   do_stop ;;
    status) do_status ;;
    *)      log "Usage: $0 [start|stop|status]" ;;
esac
