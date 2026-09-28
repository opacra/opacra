#!/usr/bin/env bash
# Provision an Ubuntu 24.04 VPS as a Tacita seed node.
#   scp tacita-linux-x64.tar.gz seed-node-setup.sh tacitad.service tacita.conf root@VPS:
#   ssh root@VPS 'bash seed-node-setup.sh tacita-linux-x64.tar.gz'
# Needs: 2+ vCPU, 4 GB RAM, 50+ GB SSD. Opens TCP 29960 (P2P) and SSH.
set -euo pipefail
TARBALL=${1:?usage: seed-node-setup.sh <tacita release tarball>}

. /etc/os-release
if [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "The release binaries are built for Ubuntu 24.04. On other systems build from source (README.md)." >&2
  exit 1
fi
apt-get update -qq
apt-get install -y -qq chrony ufw libboost-chrono1.83.0t64 libboost-filesystem1.83.0 libboost-program-options1.83.0 libboost-serialization1.83.0 libboost-thread1.83.0 libhidapi-libusb0 libreadline8t64 libsodium23 libssl3t64 libunbound8 libusb-1.0-0 libzmq5

# accurate clock matters: blocks more than 10 minutes in the future are rejected
systemctl enable --now chrony

id tacita >/dev/null 2>&1 || useradd --system --home /var/lib/tacita --shell /usr/sbin/nologin tacita
mkdir -p /opt/tacita /etc/tacita /var/lib/tacita
tar -xzf "$TARBALL" -C /opt/tacita --strip-components=1
cp -n tacita.conf /etc/tacita/tacita.conf
chown -R tacita:tacita /var/lib/tacita
cp tacitad.service /etc/systemd/system/tacitad.service
systemctl daemon-reload
systemctl enable --now tacitad

ufw allow OpenSSH
ufw allow 29960/tcp comment 'Tacita P2P'
ufw --force enable

sleep 5
/opt/tacita/tacitad --rpc-bind-port 29961 status || true
echo "Seed node running. Logs: journalctl -u tacitad -f  |  /var/lib/tacita/tacita.log"
