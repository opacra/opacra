# Running a mining pool for Opacra

Opacra works with [jtgrassie/monero-pool](https://github.com/jtgrassie/monero-pool)
(commit `db16e73`) built against the Opacra source tree, plus one small patch,
`opacra-monero-pool.patch`. Tested end to end on a private chain under mainnet rules on
18 Oct 2026: shares, blocks found, unlock and payouts (see "Tested" below).

## Why the patch

5% of every block's new coins goes to the development fund, as a second output of the
coinbase. A block header's `reward` is the **whole** coinbase, miner and fund together; the
pool's wallet only receives the miner's part. Unpatched, monero-pool pays miners from the
header reward and so promises about 5% more than it ever receives, until its wallet runs dry.

The patch reads `expected_reward` from `get_block_template` (exactly what the pool's wallet
gets for that block), stores it when a block is submitted, and pays out from that.

Nothing else changes: the pool uses `get_block_template` and `reserved_offset`, so the node
builds the coinbase with the fund output itself, and share checks use Opacra's RandomOPCA
because the pool links the RandomX library from the Opacra build.

## Build (Ubuntu 24.04)

```bash
# 1. Build Opacra first (README.md), e.g. into build/portable
sudo apt-get install -y liblmdb-dev libevent-dev libjson-c-dev uuid-dev xxd
git clone https://github.com/jtgrassie/monero-pool.git && cd monero-pool
git checkout db16e73
git apply /path/to/opacra/contrib/pool/opacra-monero-pool.patch
export MONERO_ROOT=/path/to/opacra MONERO_BUILD_ROOT=/path/to/opacra/build/portable
make release
```

The pool binary is `build/release/monero-pool`.

## Configure

Start from the pool's own `pool.conf` and change:

| Setting | Value |
|---|---|
| `rpc-port` | the node's RPC port: 29961 mainnet, 29971 testnet |
| `wallet-rpc-port` | your `opacra-wallet-rpc` port |
| `pool-wallet` | the pool wallet's address (mainnet starts `Pa`) |
| `pool-start-diff` | start low, e.g. 1000; the pool retargets each miner |
| `block-notified` | **1**, together with the node option below |

**New blocks must reach the pool at once.** Opacra blocks come every 30 seconds, but by
default the pool only checks for a new block every 45 seconds (`template-timeout`). In the
test that meant miners kept working on blocks that were already out of date, and the pool
found the same height up to four times. Start the node with

```
--block-notify '/usr/bin/pkill -USR1 -x monero-pool'
```

and set `block-notified = 1`: the node then signals the pool the moment a block arrives, and
the pool fetches a fresh template straight away (one block per height in the test).

Run the node with `--enforce-dns-checkpointing` like the seeds, so the pool never builds on
a chain the emergency checkpoints have ruled out.

## Miners

Stock XMRig can't mine Opacra. Miners use the Opacra build of XMRig (opacra.org) with the
algorithm set explicitly, because the pool doesn't send one:

```
xmrig -a rx/opca -o POOL:4242 -u <their Opacra address> -p x
```

## Tested

18 Oct 2026, private chain under mainnet rules, one node (`--offline`), opacra-wallet-rpc,
the patched pool and Opacra XMRig (2 threads):

(results recorded below once the run completes)
