#!/usr/bin/env bash
# Phone alerts for an Opacra seed node (push notifications through the free ntfy app).
#   scp contrib/launch/{opacra-alert,install-alerts.sh,opacra-alert.service,opacra-alert.timer} root@SEED:
#   ssh root@SEED 'bash install-alerts.sh testnet'            # first seed: makes a new alert topic
#   ssh -t root@SEED 'bash install-alerts.sh testnet -'       # more seeds: asks for the topic (same feed)
# The topic is the alert feed's only secret, so it isn't typed on the command line (where `ps`
# and shell history would keep it): "-" asks for it, or set OPACRA_ALERT_TOPIC. A server that
# already has alerts for another network reuses that topic by itself.
# Safe to run again (e.g. after editing /etc/opacra/alert.conf or to upgrade the script).
# Restarts the node once, so that it starts calling the alert script. Each network on the
# server has its own alert config and watchdog (instance-names.sh): testnet uses
# /etc/opacra/alert.conf and opacra-alert; mainnet /etc/opacra/alert-mainnet.conf, the
# watchdog opacra-alert-mainnet, and the command `opacra-alert-mainnet status`.
set -euo pipefail
NETWORK=${1:-mainnet}
TOPIC=${2:-${OPACRA_ALERT_TOPIC:-}}
if [ "$TOPIC" = "-" ]; then
  read -r -s -p "Alert topic (paste it, then Enter): " TOPIC; echo >&2
elif [ -n "${2:-}" ]; then
  echo "Note: a topic typed on the command line stays in shell history; next time use -" >&2
fi
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
. ./instance-names.sh
for f in opacra-alert opacra-alert.service opacra-alert.timer; do
  [ -f "$f" ] || { echo "missing $f: copy it next to install-alerts.sh" >&2; exit 1; }
done
[ -f "$NODECONF" ] || { echo "$NODECONF not found: run seed-node-setup.sh for $NETWORK first" >&2; exit 1; }
command -v python3 >/dev/null || { apt-get update -qq && apt-get install -y -qq python3; }

install -m 755 opacra-alert /usr/local/bin/opacra-alert
install -d -o opacra -g opacra -m 750 "$STATEDIR"

CONF="$ALERTCONF"
if [ ! -e "$CONF" ]; then
  # another network on this server already has alerts: reuse its topic, one feed on the phone
  # (|| true: on a server with no alerts yet the pattern matches nothing and sed fails, which
  # under set -e -o pipefail ended the script silently; found by the 24 Oct staging test)
  [ -n "$TOPIC" ] || TOPIC=$(sed -n 's/^NTFY_TOPIC=//p' /etc/opacra/alert*.conf 2>/dev/null | head -1 || true)
  [ -n "$TOPIC" ] || TOPIC="opacra-$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  cat > "$CONF" <<EOF
# Opacra seed alerts (read by /usr/local/bin/opacra-alert). Anyone who knows the topic can
# read these alerts or send fake ones, so share it only with people who run seeds.
NETWORK=$NETWORK
NTFY_TOPIC=$TOPIC
RPC=127.0.0.1:$RPC
EXPLORER=$EXPLORER
LOG_FILE=$LOGFILE
STATE_DIR=$STATEDIR
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
sed -i '/^reorg-notify=/d; /^block-rate-notify=/d; /^# Phone alerts (install-alerts.sh)$/d' "$NODECONF"
[ -z "$(tail -c1 "$NODECONF")" ] || echo >> "$NODECONF"
cat >> "$NODECONF" <<'EOF'
# Phone alerts (install-alerts.sh)
reorg-notify=/usr/local/bin/opacra-alert reorg %s %h %n %d
block-rate-notify=/usr/local/bin/opacra-alert block-rate %t %b %e
EOF

# this network's watchdog, reading this network's alert config
sed -e "s|^\[Service\]|[Service]\nEnvironment=OPACRA_ALERT_CONF=$CONF|; s|opacrad.service|$SERVICE.service|; s|^Description=.*|Description=Opacra $NETWORK alert watchdog|" \
    opacra-alert.service > "/etc/systemd/system/$ALERTUNIT.service"
sed -e "s|^Description=.*|Description=Opacra $NETWORK alert watchdog, every 5 minutes|" \
    opacra-alert.timer > "/etc/systemd/system/$ALERTUNIT.timer"
if [ -n "$SUFFIX" ]; then
  # a short command for this network: opacra-alert-mainnet status | test
  printf '#!/bin/sh\nOPACRA_ALERT_CONF=%s exec /usr/local/bin/opacra-alert "$@"\n' "$CONF" > "/usr/local/bin/$ALERTUNIT"
  chmod 755 "/usr/local/bin/$ALERTUNIT"
fi
systemctl daemon-reload
if [ "${OPACRA_NO_START:-0}" = 1 ]; then
  # staging (seed-node-setup.sh --no-start): enabled for boot, but nothing runs until started
  systemctl enable "$ALERTUNIT.timer" >/dev/null
  systemctl stop "$ALERTUNIT.timer" 2>/dev/null || true
else
  systemctl enable --now "$ALERTUNIT.timer" >/dev/null
  systemctl restart "$SERVICE"
  sleep 8
  systemctl is-active --quiet "$SERVICE" || { echo "$SERVICE did not restart: journalctl -u $SERVICE -n 30" >&2; exit 1; }
fi

TOPIC=$(sed -n 's/^NTFY_TOPIC=//p' "$CONF")
echo
echo "Alerts installed for $NETWORK. Your alert topic:"
echo
echo "    $TOPIC"
echo
echo "On your phone: install the free app \"ntfy\" (Play Store or App Store), tap +,"
echo "type the topic above exactly, leave the server as ntfy.sh, and tap Subscribe."
echo "Then send a test from this server:   $ALERTUNIT test"
echo "What the watchdog sees right now:    $ALERTUNIT status"
