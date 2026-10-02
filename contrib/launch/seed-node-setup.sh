#!/usr/bin/env bash
# Provision an Ubuntu 24.04 VPS as a Opacra seed node.
#   scp opacra-linux-x64.tar.gz seed-node-setup.sh opacrad.service opacra.conf root@VPS:
#   ssh root@VPS 'bash seed-node-setup.sh opacra-linux-x64.tar.gz'
# Needs: 2+ vCPU, 4 GB RAM, 50+ GB SSD. Opens TCP 29960 (P2P) and SSH.
set -euo pipefail
TARBALL=${1:?usage: seed-node-setup.sh <opacra release tarball>}

. /etc/os-release
if [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "The release binaries are built for Ubuntu 24.04. On other systems build from source (README.md)." >&2
  exit 1
fi
apt-get update -qq
apt-get install -y -qq chrony ufw libboost-chrono1.83.0t64 libboost-filesystem1.83.0 libboost-program-options1.83.0 libboost-serialization1.83.0 libboost-thread1.83.0 libhidapi-libusb0 libreadline8t64 libsodium23 libssl3t64 libunbound8 libusb-1.0-0 libzmq5

# accurate clock matters: blocks more than 3 minutes in the future are rejected
systemctl enable --now chrony

id opacra >/dev/null 2>&1 || useradd --system --home /var/lib/opacra --shell /usr/sbin/nologin opacra
mkdir -p /opt/opacra /etc/opacra /var/lib/opacra
tar -xzf "$TARBALL" -C /opt/opacra --strip-components=1
cp -n opacra.conf /etc/opacra/opacra.conf
chown -R opacra:opacra /var/lib/opacra
cp opacrad.service /etc/systemd/system/opacrad.service
systemctl daemon-reload
systemctl enable --now opacrad

ufw allow OpenSSH
ufw allow 29960/tcp comment 'Opacra P2P'
ufw --force enable

sleep 5
/opt/opacra/opacrad --rpc-bind-port 29961 status || true
echo "Seed node running. Logs: journalctl -u opacrad -f  |  /var/lib/opacra/opacra.log"
