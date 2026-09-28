# Mining Tacita

Tacita uses **RandomX**, the same CPU-oriented proof of work as Monero. Any modern
desktop or laptop CPU can mine. GPUs are inefficient and there are no ASICs.

- Block time: 30 seconds. Block reward: 2.384186 TCA at launch, ramping up linearly
  from zero over the first 7 days (20,160 blocks).
- Mined coins unlock after 60 blocks (about 30 minutes).
- RandomX needs ~2.3 GB of RAM per miner process for full speed ("fast mode").

## 1. Solo mining with the node (simplest)

```bash
./tacitad --start-mining Ta<your address> --mining-threads 4
# or, on a running node:
./tacitad start_mining Ta<your address> 4
./tacitad mining_status
./tacitad stop_mining
```

The first block template takes about a minute while the RandomX dataset is built.

## 2. XMRig (fastest)

XMRig supports RandomX (`rx/0`) and can mine directly against a node ("daemon mode")
or a pool.

Solo, against your own node (RPC on 29961):

```bash
./xmrig -o 127.0.0.1:29961 --daemon -a rx/0 -u Ta<your address> --coin monero
```

`--coin monero` tells XMRig the block format; Tacita uses the same format and algorithm.

Pool:

```bash
./xmrig -o pool.example:3333 -a rx/0 -u Ta<your address> -p worker1 -k
```

Tuning: enable huge pages (`sudo sysctl -w vm.nr_hugepages=1280`), run as root once so
XMRig can enable MSR mods, and use one thread per physical core with 2 MB of L3 cache.

## 3. Running a pool

A pool at launch is the single most important thing for miners. Options:

- **jtgrassie/monero-pool** – C, small, supports RandomX and PPLNS. Build it against this
  source tree (it links Monero's libraries); set the address prefix (27806) and
  block time (30) in its config.
- **CryptoNote Node.js pools** (nodejs-pool, cryptonote-nodejs-pool forks) – web UI
  included; configure coin units (10^12), address prefix and `coinDifficultyTarget: 30`.

Pool requirements: `tacitad` with `--rpc-bind-ip 127.0.0.1`, a `tacita-wallet-rpc` for
payouts, Redis or LMDB depending on the pool, and a payment threshold that respects
the 60-block unlock.

## 4. Why a 7-day slow start

Most new coins are mined out by a few insiders in the first hours, before anyone else
knows the chain exists. Tacita's block reward starts near zero and rises linearly for
20,160 blocks: the first day pays about 7% of a normal day, and the whole first week
pays half of a normal week. Mining early buys no advantage, and there is no reason to
rush on launch day.
