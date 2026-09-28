# Running a Tacita node

## Hardware

| Role | CPU | RAM | Disk |
|---|---|---|---|
| Home node / wallet | 2 cores | 2 GB (4 GB if mining) | 20 GB SSD at launch, grows over time |
| Seed / public node | 2–4 vCPU | 4 GB | 80 GB SSD |

Blocks arrive every 30 seconds, so the chain grows about 4× faster per day than Monero's
at the same transaction volume. Pruning (`--prune-blockchain`) cuts storage by ~2/3
for home nodes; seed nodes should keep the full chain.

## Ports

| Port | Purpose | Expose publicly? |
|---|---|---|
| 29960/tcp | P2P | Yes, on seed/public nodes |
| 29961/tcp | RPC (unrestricted) | **No**, localhost only |
| 29962/tcp | ZMQ RPC | No |
| (choose) e.g. 29969/tcp | Restricted RPC for light wallets | Optional |

## Quick setup on Ubuntu 24.04 (VPS)

```bash
scp tacita-linux-x64.tar.gz contrib/launch/{seed-node-setup.sh,tacitad.service,tacita.conf} root@VPS:
ssh root@VPS 'bash seed-node-setup.sh tacita-linux-x64.tar.gz'
```

This installs the runtime libraries, `chrony` for clock sync, a `tacita` system user,
the binaries in `/opt/tacita`, config in `/etc/tacita/tacita.conf`, data in
`/var/lib/tacita`, the systemd unit and a firewall rule for 29960.

```bash
systemctl status tacitad
journalctl -u tacitad -f
/opt/tacita/tacitad status        # height, sync state, peers
/opt/tacita/tacitad print_cn      # connections
```

## Keep the clock right

Nodes reject blocks timestamped more than 3 minutes in their future (Monero allows 2
hours). A node whose clock is badly off will reject valid blocks and fall out of sync.
Run NTP (`chrony` or `systemd-timesyncd`).

## Public node for wallets

```
rpc-restricted-bind-ip=0.0.0.0
rpc-restricted-bind-port=29969
confirm-external-bind=1
```

Restricted RPC hides admin calls (mining, peer bans, shutdown). Put it behind a
reverse proxy with TLS if you publish it as `node.yourcoin.org`.

## Tor / I2P

Everything in `docs/ANONYMITY_NETWORKS.md` applies; replace `monerod` with `tacitad` and
port 18083 with a port of your choice (for example 29963). Onion seed addresses go in
`src/coin_network.h`.

## Upgrades

Network upgrades are announced with a block height. Replace the binaries before that
height and restart the service. The database format is Monero's LMDB format, so no
resync is needed between releases unless the release notes say so.
