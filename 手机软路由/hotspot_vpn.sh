#!/system/bin/sh
# Transparent VPN Hotspot - OPPO Reno4 SE
# Requires: Root (Magisk), V2rayNG running with tun0
# Usage: su -c 'sh /sdcard/Download/hotspot_vpn.sh [start|stop|status]'
#
# This script routes all hotspot (ap0/swlan0) traffic through VPN tun0
# so connected devices get VPN automatically without proxy config.

ACTION="${1:-status}"
TUN="tun0"
# OPPO hotspot interfaces (try both)
AP_IFACES="ap0 swlan0 wlan1"

log() { echo "[hotspot_vpn] $1"; }

get_ap_iface() {
    for iface in $AP_IFACES; do
        if ip link show "$iface" 2>/dev/null | grep -q "UP"; then
            echo "$iface"
            return 0
        fi
    done
    echo ""
    return 1
}

do_status() {
    log "=== Status ==="
    # VPN tunnel
    if ip addr show $TUN 2>/dev/null | grep -q "inet"; then
        TUN_IP=$(ip addr show $TUN | grep 'inet ' | awk '{print $2}')
        log "VPN tun0: UP ($TUN_IP)"
    else
        log "VPN tun0: DOWN (start V2rayNG first!)"
    fi

    # Hotspot interface
    AP=$(get_ap_iface)
    if [ -n "$AP" ]; then
        AP_IP=$(ip addr show "$AP" | grep 'inet ' | awk '{print $2}')
        log "Hotspot $AP: UP ($AP_IP)"
    else
        log "Hotspot: DOWN (enable hotspot in settings)"
    fi

    # IP forwarding
    FWD=$(cat /proc/sys/net/ipv4/ip_forward)
    log "IP forward: $FWD"

    # iptables rules
    RULES=$(iptables -t nat -L POSTROUTING -n 2>/dev/null | grep -c "$TUN")
    log "NAT rules for tun0: $RULES"

    # Connected clients
    if [ -f /proc/net/arp ]; then
        CLIENTS=$(grep -v "00:00:00:00:00:00" /proc/net/arp | grep -c "$AP" 2>/dev/null || echo 0)
        log "Connected clients: $CLIENTS"
    fi
}

do_start() {
    log "=== Starting Transparent VPN Hotspot ==="

    # Check VPN
    if ! ip addr show $TUN 2>/dev/null | grep -q "inet"; then
        log "ERROR: VPN tun0 not found. Start V2rayNG first!"
        return 1
    fi

    # Check hotspot
    AP=$(get_ap_iface)
    if [ -z "$AP" ]; then
        log "WARNING: Hotspot not active. Enable it in Settings -> Personal Hotspot"
        log "Will configure anyway, rules activate when hotspot starts."
        AP="ap0"
    fi

    # Enable IP forwarding
    echo 1 > /proc/sys/net/ipv4/ip_forward
    log "IP forwarding enabled"

    # Clear old rules
    iptables -t nat -D POSTROUTING -o $TUN -j MASQUERADE 2>/dev/null
    iptables -D FORWARD -i $AP -o $TUN -j ACCEPT 2>/dev/null
    iptables -D FORWARD -i $TUN -o $AP -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null

    # Add NAT masquerade for VPN tunnel
    iptables -t nat -A POSTROUTING -o $TUN -j MASQUERADE
    log "NAT MASQUERADE on $TUN"

    # Forward hotspot traffic to VPN
    iptables -A FORWARD -i $AP -o $TUN -j ACCEPT
    iptables -A FORWARD -i $TUN -o $AP -m state --state RELATED,ESTABLISHED -j ACCEPT
    log "FORWARD: $AP -> $TUN"

    # Also handle swlan0 if different
    for iface in $AP_IFACES; do
        if [ "$iface" != "$AP" ]; then
            iptables -D FORWARD -i $iface -o $TUN -j ACCEPT 2>/dev/null
            iptables -D FORWARD -i $TUN -o $iface -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null
            iptables -A FORWARD -i $iface -o $TUN -j ACCEPT
            iptables -A FORWARD -i $TUN -o $iface -m state --state RELATED,ESTABLISHED -j ACCEPT
        fi
    done

    log "=== Transparent VPN Hotspot ACTIVE ==="
    log "All hotspot clients now route through VPN automatically"
    do_status
}

do_stop() {
    log "=== Stopping Transparent VPN Hotspot ==="

    # Remove rules
    iptables -t nat -D POSTROUTING -o $TUN -j MASQUERADE 2>/dev/null
    for iface in $AP_IFACES; do
        iptables -D FORWARD -i $iface -o $TUN -j ACCEPT 2>/dev/null
        iptables -D FORWARD -i $TUN -o $iface -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null
    done

    # Disable IP forwarding
    echo 0 > /proc/sys/net/ipv4/ip_forward
    log "IP forwarding disabled"

    log "=== Transparent VPN Hotspot STOPPED ==="
    log "Hotspot clients now use direct internet (no VPN)"
}

case "$ACTION" in
    start)  do_start ;;
    stop)   do_stop ;;
    status) do_status ;;
    *)      log "Usage: $0 [start|stop|status]" ;;
esac
