# Running an Opacra node

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

Testnet uses 29970 / 29971 / 29972 and stagenet 29980 / 29981 / 29982 for the same three services.

## Quick setup on Ubuntu 24.04 (VPS)

```bash
scp dist/opacra-v<version>-linux-x64.tar.gz contrib/launch/{seed-node-setup.sh,opacrad.service,opacra.conf} root@VPS:
ssh root@VPS 'bash seed-node-setup.sh opacra-v<version>-linux-x64.tar.gz'           # mainnet
ssh root@VPS 'bash seed-node-setup.sh opacra-v<version>-linux-x64.tar.gz testnet'   # public testnet
```

This installs the runtime libraries, `chrony` for clock sync, an `opacra` system user,
the binaries in `/opt/opacra`, config in `/etc/opacra/opacra.conf`, data in
`/var/lib/opacra` and the systemd unit. If `ufw` is already active it opens the P2P port
(29960 mainnet, 29970 testnet); it never turns a firewall on by itself, so it is safe on
a server that also runs a website.

```bash
systemctl status opacrad
journalctl -u opacrad -f
/opt/opacra/opacrad status        # height, sync state, peers
/opt/opacra/opacrad print_cn      # connections
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

Everything in `docs/ANONYMITY_NETWORKS.md` applies; replace `monerod` with `opacrad` and
port 18083 with a port of your choice (for example 29965; 29963 is the ZMQ publisher
in the example config). Onion seed addresses go in
`src/coin_network.h`.

## Join the public testnet

From v0.1.1 the testnet seed node is built in, so this is enough on any computer:

```
./opacrad --testnet
```

The node finds the seed (169.58.62.247:29970) by itself and syncs. Earlier versions need
`--add-priority-node 169.58.62.247:29970`. Testnet coins have no value. Watch the chain at
https://explorer.opacra.org.

## Upgrades

On a seed node installed with `seed-node-setup.sh`, upgrading is running the script again
with the new package; it keeps `/etc/opacra/opacra.conf` and the chain, and restarts the node.


Network upgrades are announced with a block height. Replace the binaries before that
height and restart the service. The database format is Monero's LMDB format, so no
resync is needed between releases unless the release notes say so.
