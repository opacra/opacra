#!/usr/bin/env bash
# Provision an Ubuntu 24.04 server as an Opacra seed node.
#   scp opacra-v<version>-linux-x64.tar.gz seed-node-setup.sh instance-names.sh opacrad.service opacra.conf root@VPS:
#   ssh -t root@VPS 'bash seed-node-setup.sh opacra-v<version>-linux-x64.tar.gz [mainnet|testnet|stagenet] [-]'
# If install-alerts.sh and its files (opacra-alert, opacra-alert.service, opacra-alert.timer)
# are copied too, phone alerts are set up as well. To share one alert feed with your other
# seeds, give "-" as the third argument and paste their topic when asked (a server that
# already has alerts for another network reuses its topic by itself).
# Needs: 2+ vCPU, 4 GB RAM, 50+ GB SSD.
# Opens the network's P2P port (mainnet 29960, testnet 29970, stagenet 29980) if ufw is active.
# One server can run several networks: run this once per network. Testnet is the service
# "opacrad"; mainnet is "opacrad-mainnet", with its own config, data folder, log and alerts
# (instance-names.sh).
# --no-start (anywhere in the arguments): install and configure, but leave the node and its
# alerts stopped. For launch-day staging, when nothing may run before the launch minute.
set -euo pipefail
NO_START=0; ARGS=()
for arg in "$@"; do if [ "$arg" = --no-start ]; then NO_START=1; else ARGS+=("$arg"); fi; done
set -- "${ARGS[@]}"
TARBALL=${1:?usage: seed-node-setup.sh <opacra release tarball> [mainnet|testnet|stagenet]}
NETWORK=${2:-mainnet}
ALERT_TOPIC=${3:-}

case "$NETWORK" in
  mainnet)  P2P=29960; RPC=29961; ZMQ=29962; NETFLAG="" ;;
  testnet)  P2P=29970; RPC=29971; ZMQ=29972; NETFLAG="testnet=1" ;;
  stagenet) P2P=29980; RPC=29981; ZMQ=29982; NETFLAG="stagenet=1" ;;
  *) echo "network must be mainnet, testnet or stagenet" >&2; exit 1 ;;
esac
cd "$(dirname "$0")"
. ./instance-names.sh

. /etc/os-release
if [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "The release binaries are built for Ubuntu 24.04. On other systems build from source (README.md)." >&2
  exit 1
fi
apt-get update -qq
apt-get install -y -qq chrony ufw libboost-chrono1.83.0t64 libboost-filesystem1.83.0 libboost-program-options1.83.0 libboost-serialization1.83.0 libboost-thread1.83.0 libhidapi-libusb0 libreadline8t64 libsodium23 libssl3t64 libunbound8 libusb-1.0-0 libzmq5

# accurate clock matters: blocks more than 3 minutes ahead of this clock are not accepted yet
systemctl enable --now chrony

id opacra >/dev/null 2>&1 || useradd --system --home /var/lib/opacra --shell /usr/sbin/nologin opacra
mkdir -p /opt/opacra /etc/opacra /var/lib/opacra "$DATADIR"
case "$TARBALL" in /*) ;; *) TARBALL="$OLDPWD/$TARBALL" ;; esac
# check the package against the release checksums when a checksum file is next to it
# (SHA256SUMS.txt from the package step, or the signed SHA256SUMS-v<version>.asc from the
# site; verify the signature on your PC first: docs/VERIFYING.md)
PKG="$(basename "$TARBALL")"
have=$(sha256sum "$TARBALL" | awk '{print $1}')
want=""
for f in "$(dirname "$TARBALL")"/SHA256SUMS*; do
  [ -f "$f" ] || continue
  want=$(awk -v f="$PKG" '{n=$2; sub(/^\*/, "", n); sub(/^\.\//, "", n)} n == f {print $1; exit}' "$f")
  [ -n "$want" ] && { SUMS="$f"; break; }
done
if [ -n "$want" ]; then
  if [ "$want" != "$have" ]; then
    echo "$PKG does not match $SUMS: not installing." >&2
    exit 1
  fi
  echo "Package checksum matches $SUMS"
else
  echo "Package SHA256: $have  (no checksum file for it next to it: compare by hand)"
fi
# all networks share one copy of the programs; a running node keeps its old copy until restarted.
# The programs belong to root whatever the archive says, so the node's account can't change
# them.
tar --no-same-owner -xzf "$TARBALL" -C /opt/opacra --strip-components=1
chown -R root:root /opt/opacra
chmod -R go-w /opt/opacra

if [ ! -e "$NODECONF" ]; then
  # the example config is for mainnet; switch ports, folders and network
  sed -e "s/29960/$P2P/g; s/29961/$RPC/g; s/29962/$ZMQ/g; s/29963/$((ZMQ + 1))/g; s/29969/$((P2P + 9))/g" \
      -e "s|^data-dir=.*|data-dir=$DATADIR|; s|^log-file=.*|log-file=$LOGFILE|" opacra.conf > "$NODECONF"
  if [ -n "$NETFLAG" ]; then
    printf '\n# network\n%s\n' "$NETFLAG" >> "$NODECONF"
  fi
else
  echo "$NODECONF already exists; keeping your settings" >&2
  # one setting is raised on existing seeds too: the old default of 128 incoming connections
  if grep -q "^in-peers=128$" "$NODECONF"; then
    sed -i "s/^in-peers=128$/in-peers=1000/" "$NODECONF"
    echo "Raised in-peers from 128 to 1000 in $NODECONF" >&2
  fi
fi
chown -R opacra:opacra /var/lib/opacra
# the service: the shipped unit, pointed at this network's config; the alert script it calls
# on reorganisations reads this network's alert config
sed -e "s|/etc/opacra/opacra.conf|$NODECONF|; s|^Description=.*|Description=Opacra $NETWORK node ($SERVICE)|" \
    -e "s|^\[Service\]|[Service]\nEnvironment=OPACRA_ALERT_CONF=$ALERTCONF|" \
    opacrad.service > "/etc/systemd/system/$SERVICE.service"
# reliable DNS for the emergency checkpoints: the node's built-in list of public DNS servers
# is old (lessons learned, 12 Oct 2026); kept if it already exists
mkdir -p "/etc/systemd/system/$SERVICE.service.d"
if [ ! -e "/etc/systemd/system/$SERVICE.service.d/dns.conf" ]; then
  printf '[Service]\nEnvironment=DNS_PUBLIC=tcp://1.1.1.1\n' > "/etc/systemd/system/$SERVICE.service.d/dns.conf"
fi
systemctl daemon-reload
systemctl enable "$SERVICE"
# restart (not just start) so that re-running this script with a new package upgrades the node
if [ "$NO_START" = 1 ]; then
  systemctl stop "$SERVICE" 2>/dev/null || true
else
  systemctl restart "$SERVICE"
  sleep 5
fi

# Firewall: only add the rule. Enabling ufw here could cut off other services on a
# shared server (websites, databases), so that is left to the administrator.
if grep -q "Status: active" <(ufw status); then
  ufw allow "$P2P"/tcp comment "Opacra $NETWORK P2P"
else
  echo "ufw is not active. If this server has a firewall, open TCP $P2P for Opacra P2P." >&2
fi

if [ "$NO_START" = 1 ]; then
  echo "Opacra $NETWORK seed node installed as $SERVICE, NOT started (--no-start)."
  echo "Start it at the launch minute:  systemctl start $SERVICE $ALERTUNIT.timer"
else
  sleep 5
  /opt/opacra/opacrad --rpc-bind-port "$RPC" status || true
  echo "Opacra $NETWORK seed node running as $SERVICE. Logs: journalctl -u $SERVICE -f  |  $LOGFILE"
fi
for other in $(systemctl list-units --type=service --all --no-legend 'opacrad*' 2>/dev/null | awk '{print $1}' | sed 's/\.service$//'); do
  [ "$other" = "$SERVICE" ] || echo "Also on this server: $other. It runs the previous programs until: systemctl restart $other" >&2
done
if [ -f install-alerts.sh ]; then
  OPACRA_NO_START="$NO_START" OPACRA_ALERT_TOPIC="${OPACRA_ALERT_TOPIC:-}" bash install-alerts.sh "$NETWORK" ${ALERT_TOPIC:+"$ALERT_TOPIC"}
else
  echo "Phone alerts are not set up: copy install-alerts.sh and its files here and run it (docs/ALERTS.md)." >&2
fi
