#!/usr/bin/env bash
# Air-gap enforcement for the SovereignAI Workbench.
#
# Stops host OS services that reach the internet, then blocks outbound
# traffic at the firewall except to the local inference node.
#
#   ./airgap.sh on     enforce
#   ./airgap.sh off    restore normal operation
#   ./airgap.sh status show current state

set -uo pipefail
ZONE=$(firewall-cmd --get-default-zone 2>/dev/null || echo public)

enable_airgap() {
    echo "[1/4] stopping outbound host services"
    for svc in chronyd systemd-timesyncd rhsmcertd packagekit; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            systemctl stop "$svc" && echo "      stopped $svc"
        fi
    done

    echo "[2/4] blocking outbound NTP and DNS"
    firewall-cmd --direct --add-rule ipv4 filter OUTPUT 0 \
        -p udp --dport 123 -j REJECT 2>/dev/null
    firewall-cmd --direct --add-rule ipv4 filter OUTPUT 1 \
        -p udp --dport 53 -j REJECT 2>/dev/null
    firewall-cmd --direct --add-rule ipv4 filter OUTPUT 2 \
        -p tcp --dport 53 -j REJECT 2>/dev/null

    echo "[3/4] permitting the local inference node only"
    firewall-cmd --direct --add-rule ipv4 filter OUTPUT 3 \
        -d 10.0.2.2 -p tcp --dport 11434 -j ACCEPT 2>/dev/null
    firewall-cmd --direct --add-rule ipv4 filter OUTPUT 4 \
        -d 192.168.59.1 -p tcp --dport 11434 -j ACCEPT 2>/dev/null

    echo "[4/4] rejecting all other public destinations"
    for net in 0.0.0.0/5 8.0.0.0/7 11.0.0.0/8 128.0.0.0/3; do
        firewall-cmd --direct --add-rule ipv4 filter OUTPUT 10 \
            -d "$net" -j REJECT 2>/dev/null
    done
    echo
    echo "AIR-GAP ENFORCED"
}

disable_airgap() {
    echo "removing air-gap rules"
    firewall-cmd --direct --remove-rules ipv4 filter OUTPUT 2>/dev/null
    for svc in chronyd rhsmcertd; do
        systemctl start "$svc" 2>/dev/null && echo "      started $svc"
    done
    echo "NORMAL OPERATION RESTORED"
}

show_status() {
    echo "=== firewall direct rules ==="
    firewall-cmd --direct --get-all-rules 2>/dev/null || echo "(none)"
    echo
    echo "=== outbound services ==="
    for svc in chronyd rhsmcertd packagekit; do
        printf "  %-20s %s\n" "$svc" \
            "$(systemctl is-active "$svc" 2>/dev/null || echo inactive)"
    done
    echo
    echo "=== reachability test (expect failures when enforced) ==="
    timeout 4 getent hosts ollama.com >/dev/null 2>&1 \
        && echo "  DNS  ollama.com   RESOLVED  <-- leak" \
        || echo "  DNS  ollama.com   blocked"
    timeout 4 bash -c "</dev/tcp/8.8.8.8/53" 2>/dev/null \
        && echo "  TCP  8.8.8.8:53   REACHABLE <-- leak" \
        || echo "  TCP  8.8.8.8:53   blocked"
    timeout 4 bash -c "</dev/tcp/10.0.2.2/11434" 2>/dev/null \
        && echo "  TCP  inference    reachable (correct)" \
        || echo "  TCP  inference    UNREACHABLE <-- workbench will fail"
}

case "${1:-status}" in
    on)     enable_airgap; echo; show_status ;;
    off)    disable_airgap ;;
    status) show_status ;;
    *)      echo "usage: $0 {on|off|status}"; exit 1 ;;
esac
