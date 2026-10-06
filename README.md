# Opacra (OPCA)

**Private by default. Auditable by choice. Spendable in five minutes.**

Opacra is a proof-of-work privacy cryptocurrency with its own blockchain. It is a
fork of [Monero](https://github.com/monero-project/monero) v0.18.5.1. It is a
native coin with its own network, genesis block and consensus rules, not a token
on another chain (no ERC-20, no smart-contract host).

> The name comes from *opaque*: transactions cannot be seen through. Website:
> [opacra.org](https://opacra.org). Ticker: OPCA.

Copyright (c) 2026 The Opacra Project. Portions Copyright (c) 2014-2022 The Monero Project
and (c) 2012-2013 The Cryptonote developers. BSD-3-Clause, see [LICENSE](LICENSE).

---

## At a glance

| | Opacra | Monero (reference) |
|---|---|---|
| Chain | Own blockchain, own genesis, own P2P network | – |
| Privacy | Stealth addresses, RingCT, CLSAG ring signatures (16 members), Bulletproofs+, view tags, Dandelion++ | same |
| Proof of work | RandomX (CPU-friendly, ASIC-resistant) | same |
| **Block time** | **30 seconds** | 120 seconds |
| **Spendable after** | **10 blocks, about 5 minutes** | 10 blocks, about 20 minutes |
| Coinbase maturity | 60 blocks, about 30 minutes | 60 blocks, about 2 hours |
| Difficulty algorithm | LWMA-1 (N = 60, reacts within ~60 blocks) | 720-block sorted window |
| Main emission | **10,000,000 OPCA**, smooth curve (half emitted in ~2.8 years) | ~18.1M XMR |
| Tail emission | 0.05 OPCA per block forever (~52,600 OPCA a year, ~0.5% and falling) | 0.6 XMR per block |
| Launch | No premine, no ICO, 7-day reward ramp ("slow start") | fair launch |
| Development fund | **5% of every block's subsidy**, forever, to a published address with a public view key (fees go to miners) | none |
| Initial block reward | 2.384186 OPCA (full reward from block 20,160) | – |
| Decimals | 12 (1 OPCA = 10¹² picoop) | 12 |
| Addresses | `Pa…` standard, `Ps…` subaddress, `Pi…` integrated | `4…`, `8…`, `4…` |
| Ports (mainnet) | P2P 29960, RPC 29961, ZMQ 29962 | 18080, 18081, 18082 |
| Data directory | `~/.opacra` | `~/.bitmonero` |

Selective disclosure is built in and tested: **view keys** (read-only audit
wallets), **payment proofs** (`get_tx_proof`, bound to a message such as an invoice
number), **tx keys** and **reserve proofs** (prove a balance without showing
history). These features are the basis of the "auditable by choice" positioning in
the concept document.

Full parameter list and every change from Monero: [docs/OPACRA_SPEC.md](docs/OPACRA_SPEC.md).

## Status

- **Consensus changes are new code.** The LWMA difficulty, the per-block emission,
  the slow start and the version-16-from-block-1 start have been exercised on a
  private multi-node network ([test report](docs/TEST_REPORT.md)), but they have **not
  been independently audited**. Run a public testnet for several weeks and get a
  review before mainnet.
- The chain identity in this tree (network IDs, genesis blocks, fork timestamp) is a
  **development identity**. Regenerate it on launch day ([docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md)).
- No seed nodes are configured yet. Add yours in `src/coin_network.h`.

## Building

Ubuntu 24.04 / Debian 12:

```bash
sudo apt update && sudo apt install -y build-essential cmake pkg-config git \
  libssl-dev libzmq3-dev libunbound-dev libsodium-dev libunwind8-dev liblzma-dev \
  libreadline-dev libexpat1-dev libpgm-dev libhidapi-dev libusb-1.0-0-dev \
  libprotobuf-dev protobuf-compiler libudev-dev libboost-all-dev ccache

git submodule update --init --recursive
mkdir -p build/release && cd build/release
cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF -DUSE_DEVICE_TREZOR=OFF ../..
make -j"$(nproc)" daemon simplewallet wallet_rpc_server
ls bin/   # opacrad  opacra-wallet-cli  opacra-wallet-rpc

# The default build is tuned for *this* CPU (-march=native) and may crash with
# "Illegal instruction" on other machines. For binaries you will copy elsewhere
# (servers, releases), add -DARCH=x86-64 to the cmake line.

# consensus regression tests for the rules Opacra changed (emission, slow start, LWMA, forks)
make opacra_consensus_tests && ./bin/opacra_consensus_tests
```

Or with Docker: `docker build -t opacra -f contrib/launch/Dockerfile .`

Linux release packages are built with `contrib/launch/package_release.sh` from a
portable (`-DARCH=x86-64`) build. Monero's reproducible build descriptors in
`contrib/gitian` still build Monero and must be ported before mainnet; see
[docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md#6-release-binaries).

## Quick start

```bash
# 1. run a node (mainnet)
./opacrad --detach

# 2. create a wallet
./opacra-wallet-cli --generate-new-wallet mywallet

# 3. mine to your wallet (daemon console, or: ./opacrad --start-mining <address> --mining-threads 4)
./opacrad start_mining Pa... 4
```

A complete private network on one machine (3 nodes, mainnet rules), plus an end-to-end
test that mines, sends private transactions, checks proofs, forces a reorg and replays
every block against an independent Python model of the consensus rules:

```bash
contrib/testnet/localnet.sh start
contrib/testnet/functional_test.py        # ~1-2 hours on 2 CPU cores
```

## Documentation

| Document | What it covers |
|---|---|
| [docs/OPACRA_SPEC.md](docs/OPACRA_SPEC.md) | Parameters, emission schedule, difficulty algorithm, every change from Monero |
| [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md) | Step-by-step mainnet launch: identity, seed nodes, releases, explorer, pool |
| [docs/MINING.md](docs/MINING.md) | Solo mining, XMRig, running a pool |
| [docs/RUNNING_A_NODE.md](docs/RUNNING_A_NODE.md) | VPS seed node setup, systemd, firewall, config file |
| [docs/TEST_REPORT.md](docs/TEST_REPORT.md) | Results of the private-network functional test |
| [docs/VERIFYING.md](docs/VERIFYING.md) | Checking a download's signature; release key fingerprint D861 7219 6FEC AAB6 84F5  B3FD CB65 D212 D0B1 162B |
| [docs/README.monero-upstream.md](docs/README.monero-upstream.md) | Upstream Monero README (build details, Tor/I2P, pruning) |

## Renaming the coin

All user-visible naming comes from string literals, binary names and a handful of
config values, so renaming is mechanical:

```bash
python3 contrib/coin-identity/rebrand.py --from Opacra --to NewName --ticker-from OPCA --ticker-to NEW
python3 contrib/coin-identity/coinid.py prefix Nw     # pick new address prefixes
python3 contrib/coin-identity/coinid.py network-id    # new network IDs
python3 contrib/coin-identity/coinid.py genesis --reward 2384185791015 --message "..."
```

Then update `COIN_NAME`, `COIN_TICKER`, `CRYPTONOTE_NAME`, prefixes, network IDs and
genesis transactions in `src/cryptonote_config.h`.

## Credits

Opacra builds entirely on the work of the Monero Project and the Monero Research Lab,
and on the CryptoNote reference implementation. The LWMA difficulty algorithm is by
Zawy12 (MIT License). Keep the upstream copyright notices when redistributing.
