# Tacita technical specification

Base: Monero v0.18.5.1 (tag `v0.18.5.1`, commit `4f92268`). Everything not listed here
behaves exactly as in Monero v0.18.5.1: transaction format, RingCT/CLSAG signatures,
Bulletproofs+, view tags, stealth addresses, subaddresses, multisig, Dandelion++,
Tor/I2P support, LMDB storage, pruning, RPC APIs (method names unchanged).

## 1. Chain parameters

| Parameter | Value | Where |
|---|---|---|
| Block target | 30 s (all block versions) | `DIFFICULTY_TARGET_V1/V2`, `src/cryptonote_config.h` |
| Blocks per day / year | 2,880 / 1,051,920 | |
| Proof of work | RandomX (`rx/0`), seed epoch 2048 blocks, lag 64 | unchanged |
| Difficulty algorithm | LWMA-1, N = 60 (30 min) | `src/cryptonote_basic/difficulty.cpp` |
| Startup difficulty | block 1: 1; blocks 2–12: 10,000 (`DIFFICULTY_STARTUP_GUESS`); LWMA from block 13 with the blocks available | |
| Future time limit | 600 s (Monero: 7,200 s) | `CRYPTONOTE_BLOCK_FUTURE_TIME_LIMIT` |
| Median-time-past window | 11 blocks (Monero: 60) | `BLOCKCHAIN_TIMESTAMP_CHECK_WINDOW` |
| Coinbase maturity | 60 blocks (~30 min) | `CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW` |
| Spendable age | 10 blocks (~5 min) | `CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE` |
| Ring size | 16 (enforced exactly) | v16 rules |
| Consensus version | v1 at genesis only, v16 from block 1 | `src/hardforks/hardforks.cpp` |
| Block weight / fees | Monero dynamic block weight and 2021 fee scaling | unchanged |
| Decimals | 12 | unchanged |

## 2. Emission

```
base_reward(generated) = max( (MONEY_SUPPLY - generated) >> 22 , TAIL_EMISSION_REWARD )
reward(height)         = base_reward * height / 20160      for 1 <= height < 20160   (slow start)
                       = base_reward                        otherwise
MONEY_SUPPLY           = 10,000,000 TCA  (10^19 atomic units)
TAIL_EMISSION_REWARD   = 0.05 TCA
```

The Monero block-size penalty is then applied as usual, and fees are added.
`generated` counts the coins actually created (slow start included) and is capped at
`MONEY_SUPPLY`; after the cap is reached the tail reward continues unchanged.

| After | Emitted (main curve) | Share of 10M |
|---|---|---|
| 1 year | 2,199,478 TCA | 22.0% |
| 2 years | 3,929,789 TCA | 39.3% |
| 3 years | 5,276,283 TCA | 52.8% |
| 4 years | 6,324,097 TCA | 63.2% |
| 5 years | 7,139,486 TCA | 71.4% |
| 10 years | 9,183,710 TCA | 91.8% |
| 15 years | 9,767,059 TCA | 97.7% |

- Initial full reward: 2.384185791015 TCA per block (~6,866 TCA per day).
- Half-life of the remaining main supply: 2.76 years.
- Tail emission starts at height ≈16,219,000 (~15.4 years): 0.05 TCA per block,
  ~52,596 TCA a year, which is ~0.5% a year at that point and falling.
- Slow start: during the first 20,160 blocks (7 days) rewards rise linearly from 0,
  so launch-day miners cannot capture a large share before others join. About 24,000
  TCA is emitted in that week instead of ~48,000 (the rest stays in the curve).
- Genesis output: 2.384185791015 TCA to a random key whose secret was discarded. It is
  a pre-RingCT output with a unique amount, so no valid 16-member ring can reference
  it: unspendable by construction.
- **No premine, no developer fee, no ICO.**

The table is produced by `contrib/sim/tacita_params.py` (bit-exact integer model).

## 3. Difficulty: LWMA-1

For the next block, take the last N+1 blocks (genesis excluded), with N = 60:

```
L = Σ_{i=1..N} i · min(6T, t_i − t_{i−1})      out-of-order timestamps count as 1 s
L = max(L, N²T/20)
D_next = (C_N − C_0) · T · (N+1) · 99 / (200 · L)        C = cumulative difficulty
```

Integer arithmetic only (256-bit intermediates). Recent blocks carry the most weight,
so the algorithm follows hash-rate changes within about N blocks while staying stable
(steady-state difficulty noise ~13%). Simulated on 20 random runs with a 10× hash-rate
spike for 200 blocks: difficulty reached 80% of the new level after ~63 blocks and mean
block time over the whole run stayed at 31.5 s. See `contrib/sim/`.

Why not Monero's algorithm: its 720-block window with a 15-block lag takes about a
day to react at 2-minute blocks, which invites profit-switching and rented hash power
on a small chain. LWMA is the most widely deployed replacement in CryptoNote chains.

## 4. Network identity

| | Mainnet | Testnet | Stagenet |
|---|---|---|---|
| Address prefix (standard / integrated / subaddress) | 27806 `Ta` / 22047 `Ti` / 19744 `Ts` | 8479 `Te` / 11935 `Tf` / 15263 `Tg` | 28440 `Sa` / 22809 `Si` / 20378 `Ss` |
| Address length | 98 / 109 / 98 characters | 97 / 108 / 97 | 98 / 109 / 98 |
| P2P / RPC / ZMQ ports | 29960 / 29961 / 29962 | 39960 / 39961 / 39962 | 49960 / 49961 / 49962 |
| Network ID | `FCD0813C-0294-017F-8820-08C3B60914C6` | `F780A78B-DEFE-BC2C-0B69-F012EDE8F26D` | `6037C3AD-7B93-090A-133C-99C7E739171B` |
| Genesis message | "Tacita mainnet genesis \| 2026-09-28 \| Private by default, auditable by choice." | "Tacita testnet genesis \| 2026-09-28" | "Tacita stagenet genesis \| 2026-09-28" |

Message-signing domain: `TacitaMessageSignature` (signatures cannot be replayed on Monero).
Data directory `~/.tacita`, config file `tacita.conf`, log `tacita.log`.

These values are the **development identity**. Generate fresh network IDs and genesis
transactions on launch day (`contrib/coin-identity/coinid.py`).

## 5. Changes from Monero v0.18.5.1

Consensus:

1. `src/cryptonote_config.h`: block time, emission constants, slow start, LWMA window
   and startup constants, future time limit, median window, identity (prefixes,
   ports, network IDs, genesis transactions), data directory name, signing domain.
2. `src/cryptonote_basic/difficulty.cpp`: `next_difficulty()` replaced by LWMA-1;
   `next_difficulty_64()` kept as a wrapper for API compatibility.
3. `src/cryptonote_basic/cryptonote_basic_impl.cpp/.h`: `get_block_reward()` uses a
   per-block emission factor and fixed tail (Monero's per-minute scaling truncates to
   zero below 60 s blocks); new `apply_slow_start()` and `get_block_reward_at_height()`.
4. `src/cryptonote_core/cryptonote_tx_utils.cpp`: coinbase construction uses
   `get_block_reward_at_height()`.
5. `src/cryptonote_core/blockchain.cpp/.h`: coinbase validation uses
   `get_block_reward_at_height()` (height passed in); block templates pass the height to
   the transaction pool.
6. `src/cryptonote_core/tx_pool.cpp/.h`: template filling uses the height-aware reward, so
   the expected reward reported to miners and pools is exact during slow start.
7. `src/hardforks/hardforks.cpp`: compact fork tables `{1 @ 0, 16 @ 1}` for all networks.
8. `src/blocks/checkpoints.dat`: emptied (Monero fast-sync hashes removed);
   `src/checkpoints/checkpoints.cpp`: Monero checkpoints removed.

Network and wallet:

9. `src/coin_network.h` (new): seed nodes, DNS seeds, Tor/I2P seeds, DNS checkpoint,
   update and blocklist domains, download URLs, DNSSEC probe host. All empty or
   placeholders; nothing points at Monero infrastructure.
10. `src/p2p/net_node.h/.inl`, `src/checkpoints/checkpoints.cpp`, `src/common/updates.cpp`,
    `src/common/dns_utils.cpp`: read the lists above.
11. `src/wallet/wallet2.cpp`: hard-fork checks look versions up by value (the table
    skips versions 2–15); height estimate without Monero's rollback offsets; "recent
    output" window computed from the block time.
12. `src/simplewallet/simplewallet.cpp/.h`: `donate` uses `TACITA_DONATION_ADDR`
    (empty = disabled) instead of the Monero donation address.

Branding (no behaviour change): string literals and binary names via
`contrib/coin-identity/rebrand.py` (`tacitad`, `tacita-wallet-cli`, `tacita-wallet-rpc`,
units tacita/millitac/microtac/nanotac/picotac, `tacita:` payment URIs, file magic
strings for unsigned/signed transaction sets and exports). Environment variables keep
their `MONERO_*` names (e.g. `MONERO_RANDOMX_FULL_MEM`).

Not built / not maintained in this fork: the Monero unit tests under `tests/` (they
assert Monero's parameters), hardware-wallet support (Ledger/Trezor firmware only
knows Monero's network), the GUI (separate repository).

## 6. Security notes

- **51% attacks** are the main risk of any young PoW chain, and RandomX hash power
  can be rented. Mitigations: fair wide mining distribution from day one, hard-coded
  checkpoints in every release, DNS checkpoints once DNSSEC domains exist, and
  exchanges requiring deep confirmations (e.g. 120 blocks, one hour) at first.
  Longer-term: merge mining with Monero, as Tari does, removes most of this risk.
- **Anonymity set.** Privacy of ring signatures grows with the number of outputs on
  chain; a new chain starts with few. Wallets need at least ~100 blocks of coinbase
  outputs before 16-member rings can be formed, and early transactions are weaker than
  later ones. Encourage use (and churn) early; consider FCMP++ when Monero ships it.
- **FCMP++.** Monero's next upgrade replaces 16-member rings with full-chain membership
  proofs (code on Monero's `release-v0.19` branch; not activated on Monero mainnet as of
  July 2026). Tacita can adopt it with a network upgrade (append `{17, height, 0, time}`)
  once it is released and audited.
