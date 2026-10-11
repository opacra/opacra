#!/usr/bin/env bash
# Phone alerts for an Opacra seed node (push notifications through the free ntfy app).
#   scp contrib/launch/{opacra-alert,install-alerts.sh,opacra-alert.service,opacra-alert.timer} root@SEED:
#   ssh root@SEED 'bash install-alerts.sh testnet'            # first seed: makes a new alert topic
#   ssh root@SEED 'bash install-alerts.sh testnet TOPIC'      # more seeds: same topic, one phone feed
# Safe to run again (e.g. after editing /etc/opacra/alert.conf or to upgrade the script).
# Restarts opacrad once, so that it starts calling the alert script.
set -euo pipefail
NETWORK=${1:-mainnet}
TOPIC=${2:-}
case "$NETWORK" in
  mainnet)  RPC=29961; EXPLORER="" ;;
  testnet)  RPC=29971; EXPLORER="https://explorer.opacra.org" ;;
  stagenet) RPC=29981; EXPLORER="" ;;
  *) echo "network must be mainnet, testnet or stagenet" >&2; exit 1 ;;
esac
if [ -n "$TOPIC" ] && ! [[ "$TOPIC" =~ ^[A-Za-z0-9_-]{8,64}$ ]]; then
  echo "the topic must be 8-64 letters, digits, - or _" >&2; exit 1
fi
cd "$(dirname "$0")"
for f in opacra-alert opacra-alert.service opacra-alert.timer; do
  [ -f "$f" ] || { echo "missing $f: copy it next to install-alerts.sh" >&2; exit 1; }
done
[ -f /etc/opacra/opacra.conf ] || { echo "/etc/opacra/opacra.conf not found: run seed-node-setup.sh first" >&2; exit 1; }
command -v python3 >/dev/null || { apt-get update -qq && apt-get install -y -qq python3; }

install -m 755 opacra-alert /usr/local/bin/opacra-alert
install -d -o opacra -g opacra -m 750 /var/lib/opacra/alert

CONF=/etc/opacra/alert.conf
if [ ! -e "$CONF" ]; then
  [ -n "$TOPIC" ] || TOPIC="opacra-$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  cat > "$CONF" <<EOF
# Opacra seed alerts (read by /usr/local/bin/opacra-alert). Anyone who knows the topic can
# read these alerts or send fake ones, so share it only with people who run seeds.
NETWORK=$NETWORK
NTFY_TOPIC=$TOPIC
RPC=127.0.0.1:$RPC
EXPLORER=$EXPLORER
# NAME=seed1                 # shown in each alert (default: this server's hostname)
# REORG_ALERT_DEPTH=11       # alert when a reorganisation replaces this many blocks or more
# RATE_PERSIST_MINUTES=30    # alert when the block rate stays unusual for this long
# STALL_MINUTES=20           # alert when no new block arrives for this long
# DOWN_MINUTES=10            # alert when the node's RPC does not answer for this long
# NO_PEERS_MINUTES=15        # alert when no peers are connected for this long
# RATE_COOLDOWN_MINUTES=60   # at most one block-rate alert of each kind per this time
EOF
elif [ -n "$TOPIC" ]; then
  sed -i "s/^NTFY_TOPIC=.*/NTFY_TOPIC=$TOPIC/" "$CONF"
fi
chown root:opacra "$CONF"
chmod 640 "$CONF"

# let opacrad call the script (one line each, replaced if already there)
NODECONF=/etc/opacra/opacra.conf
sed -i '/^reorg-notify=/d; /^block-rate-notify=/d; /^# Phone alerts (install-alerts.sh)$/d' "$NODECONF"
[ -z "$(tail -c1 "$NODECONF")" ] || echo >> "$NODECONF"
cat >> "$NODECONF" <<'EOF'
# Phone alerts (install-alerts.sh)
reorg-notify=/usr/local/bin/opacra-alert reorg %s %h %n %d
block-rate-notify=/usr/local/bin/opacra-alert block-rate %t %b %e
EOF

cp opacra-alert.service opacra-alert.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now opacra-alert.timer >/dev/null
systemctl restart opacrad
sleep 8
systemctl is-active --quiet opacrad || { echo "opacrad did not restart: journalctl -u opacrad -n 30" >&2; exit 1; }

TOPIC=$(sed -n 's/^NTFY_TOPIC=//p' "$CONF")
echo
echo "Alerts installed for $NETWORK. Your alert topic:"
echo
echo "    $TOPIC"
echo
echo "On your phone: install the free app \"ntfy\" (Play Store or App Store), tap +,"
echo "type the topic above exactly, leave the server as ntfy.sh, and tap Subscribe."
echo "Then send a test from this server:   opacra-alert test"
echo "What the watchdog sees right now:    opacra-alert status"
