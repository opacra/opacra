#!/usr/bin/env bash
# Provision an Ubuntu 24.04 server as an Opacra seed node.
#   scp opacra-v<version>-linux-x64.tar.gz seed-node-setup.sh opacrad.service opacra.conf root@VPS:
#   ssh root@VPS 'bash seed-node-setup.sh opacra-v<version>-linux-x64.tar.gz [mainnet|testnet|stagenet]'
# Needs: 2+ vCPU, 4 GB RAM, 50+ GB SSD.
# Opens the network's P2P port (mainnet 29960, testnet 29970, stagenet 29980) if ufw is active.
set -euo pipefail
TARBALL=${1:?usage: seed-node-setup.sh <opacra release tarball> [mainnet|testnet|stagenet]}
NETWORK=${2:-mainnet}

case "$NETWORK" in
  mainnet)  P2P=29960; RPC=29961; ZMQ=29962; NETFLAG="" ;;
  testnet)  P2P=29970; RPC=29971; ZMQ=29972; NETFLAG="testnet=1" ;;
  stagenet) P2P=29980; RPC=29981; ZMQ=29982; NETFLAG="stagenet=1" ;;
  *) echo "network must be mainnet, testnet or stagenet" >&2; exit 1 ;;
esac

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
mkdir -p /opt/opacra /etc/opacra /var/lib/opacra
tar -xzf "$TARBALL" -C /opt/opacra --strip-components=1

if [ ! -e /etc/opacra/opacra.conf ]; then
  # the example config is for mainnet; switch ports and network for testnet/stagenet
  sed -e "s/29960/$P2P/g; s/29961/$RPC/g; s/29962/$ZMQ/g; s/29963/$((ZMQ + 1))/g; s/29969/$((P2P + 9))/g" opacra.conf > /etc/opacra/opacra.conf
  if [ -n "$NETFLAG" ]; then
    printf '\n# network\n%s\n' "$NETFLAG" >> /etc/opacra/opacra.conf
  fi
else
  echo "/etc/opacra/opacra.conf already exists; leaving it unchanged" >&2
fi
chown -R opacra:opacra /var/lib/opacra
cp opacrad.service /etc/systemd/system/opacrad.service
systemctl daemon-reload
systemctl enable --now opacrad

# Firewall: only add the rule. Enabling ufw here could cut off other services on a
# shared server (websites, databases), so that is left to the administrator.
if grep -q "Status: active" <(ufw status); then
  ufw allow "$P2P"/tcp comment "Opacra $NETWORK P2P"
else
  echo "ufw is not active. If this server has a firewall, open TCP $P2P for Opacra P2P." >&2
fi

sleep 5
/opt/opacra/opacrad --rpc-bind-port "$RPC" status || true
echo "Opacra $NETWORK seed node running. Logs: journalctl -u opacrad -f  |  /var/lib/opacra/opacra.log"
