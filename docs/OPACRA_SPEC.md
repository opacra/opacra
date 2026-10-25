# Opacra technical specification

Base: Monero v0.18.5.1 (tag `v0.18.5.1`, commit `4f92268`), with every later fix up to
Monero v0.18.5.4 applied (item 28). Everything not listed here behaves exactly as in Monero
v0.18.5.4: transaction format, RingCT/CLSAG signatures,
Bulletproofs+, view tags, stealth addresses, subaddresses, multisig, Dandelion++,
Tor/I2P support, LMDB storage, pruning, RPC APIs (method names unchanged).

## 1. Chain parameters

| Parameter | Value | Where |
|---|---|---|
| Block target | 30 s (all block versions) | `DIFFICULTY_TARGET_V1/V2`, `src/cryptonote_config.h` |
| Blocks per day / year | 2,880 / 1,051,920 | |
| Development fund | 5% of each block's subsidy from block 1, forever; fees go to miners | `OPACRA_DEV_FUND_PERCENT`, `DEV_FUND_ADDRESS` |
| Proof of work | RandomOPCA: RandomX with Opacra's own Argon2 salt `"RandomOPCA\x01"` (XMRig `rx/opca`); seed epoch 2048 blocks, lag 64 | `external/randomx/src/configuration.h` (Monero: `rx/0`, salt `"RandomX\x03"`) |
| Difficulty algorithm | LWMA-1, N = 60 (30 min) | `src/cryptonote_basic/difficulty.cpp` |
| Startup difficulty | blocks 1–12: 10,000 (`DIFFICULTY_STARTUP_GUESS`; the first public testnet's block 1 had difficulty 1); LWMA from block 13 with the blocks available | |
| Future time limit | 180 s (Monero: 7,200 s) | `CRYPTONOTE_BLOCK_FUTURE_TIME_LIMIT` |
| Median-time-past window | 11 blocks (Monero: 60) | `BLOCKCHAIN_TIMESTAMP_CHECK_WINDOW` |
| Launch time | every block after genesis is dated at or after it, so block 1 is accepted from 3 minutes before it | the height-1 entry of each table in `src/hardforks/hardforks.cpp`; `Blockchain::check_launch_time` |
| Coinbase maturity | 60 blocks (~30 min) | `CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW` |
| Spendable age | 10 blocks (~5 min) | `CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE` |
| Ring size | 16 (enforced exactly) | v16 rules |
| Consensus version | v1 at genesis only, v16 from block 1 | `src/hardforks/hardforks.cpp` |
| Block weight / fees | Monero's dynamic block weight and 2021 fee scaling, scaled to 30 s blocks so they match Monero per unit of time: 75 kB penalty-free zone (Monero 300 kB per 2 min), 400-block short-term and 400,000-block long-term medians (3.3 h and 139 days, as Monero). Max transaction weight 36.9 kB (half the zone). Default wallet fee: 1,300,000 atomic units per byte while blocks are not full (the daemon's lowest level, base reward × 3000 / 75,000²), about 0.0028 OPCA for a typical 2-input transaction (~2.2 kB), measured over 470 testnet payments on 4 Oct 2026. It falls as the block reward decays and as the long-term median block size grows | `CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5`, `CRYPTONOTE_REWARD_BLOCKS_WINDOW`, `CRYPTONOTE_LONG_TERM_BLOCK_WEIGHT_WINDOW_SIZE` |
| Decimals | 12 | unchanged |

## 2. Emission

```
base_reward(generated) = max( (MONEY_SUPPLY - generated) >> 22 , TAIL_EMISSION_REWARD )
reward(height)         = base_reward                        from block 1 (no slow start)
MONEY_SUPPLY           = 10,000,000 OPCA  (10^19 atomic units)
TAIL_EMISSION_REWARD   = 0.05 OPCA
```

The Monero block-size penalty is then applied as usual, and fees are added.
`generated` counts the coins actually created. It is not capped (item 14): once it reaches
`MONEY_SUPPLY` the formula gives only the tail reward, which continues unchanged.

| After | Emitted (main curve) | Share of 10M |
|---|---|---|
| 1 year | 2,218,201 OPCA | 22.2% |
| 2 years | 3,944,359 OPCA | 39.4% |
| 3 years | 5,287,621 OPCA | 52.9% |
| 4 years | 6,332,920 OPCA | 63.3% |
| 5 years | 7,146,352 OPCA | 71.5% |
| 10 years | 9,185,669 OPCA | 91.9% |
| 15 years | 9,767,618 OPCA | 97.7% |

- Genesis reward: 2.384185791015 OPCA (`MONEY_SUPPLY >> 22`). Block 1 pays the full curve,
  2.384185222581 OPCA (~6,870 OPCA per day at first; about 48,000 OPCA in the first week).
- Half-life of the remaining main supply: 2.76 years.
- Tail emission starts at height ≈16,219,000 (~15.4 years): 0.05 OPCA per block,
  ~52,596 OPCA a year, which is ~0.5% a year at that point and falling.
- No launch slow start (removed 18 Oct 2026 on outside advice): full rewards from block 1
  draw more hash power in the first week, when the chain is weakest. Testnet 2 (10-18 Oct 2026)
  ran a 20,160-block linear slow start; its history is valid only under the v0.2.4 code.
- Genesis output: 2.384185791015 OPCA. It is a pre-RingCT output with a unique amount, so
  no valid 16-member ring can reference it. From the mainnet genesis on, its key is a
  "nothing up my sleeve" point derived from the genesis message (`coinid.py`), so no one
  has ever held a key for it, even if a later upgrade made old outputs spendable. (The
  development genesis used a random key whose secret was discarded.)
- The daemon's running total of generated coins keeps counting past 10M (tail emission).
  Rewards switch to the tail at height ≈16,219,343, when the main-curve reward falls
  below 0.05 OPCA; the total itself reaches 10M at height ≈20,413,646 (~19.4 years).
  Miners and pools (`get_miner_data`, ZMQ `miner_data`) see the total clamped to 10M.
- **No premine, no ICO.**
- **Development fund: 5% of every block's subsidy** (newly created coins; transaction fees
  go entirely to the miner), from block 1 with no end date, including the tail (0.0025 OPCA
  a block). Paid as the last coinbase output (index n−1 of n outputs) to `DEV_FUND_ADDRESS`
  (A, B) with a per-block transaction key r_f = Hs("OpacraDevFund" ‖ height as 8-byte
  little-endian ‖ previous block's hash), R_f = r_f·G (the public testnet used
  Hs("OpacraDevFund" ‖ height) below block 30,000): the output key must be Hs(8·r_f·A ‖ n−1)·G + B with the
  matching view tag, and R_f must appear in the coinbase's extra field as a transaction
  public key (it is appended after the extra nonce, so the miner's key and pools'
  `reserved_offset` are laid out as in Monero). The coinbase's transaction public keys must
  be exactly [miner's key, R_f], both valid points. Blocks that don't follow this exactly
  are rejected. Because the key is fixed by the height and the previous block, no miner can
  choose, reuse or burn the fund's output, no two blocks share one, and nobody can plant a
  decoy output with the same key before the block exists (security audit, October 2026). The fund's secret view key is published
  (`DEV_FUND_VIEW_KEY`) so anyone can audit every payment it receives (its own spends are
  visible through their change outputs, which is intended); the miner's output keeps its
  random key and privacy. About 110,000 OPCA in year 1 and 500,000 OPCA from the main curve
  in total.

The table is produced by `contrib/sim/opacra_params.py` (bit-exact integer model).

## 3. Difficulty: LWMA-1

For the next block, take the last N+1 blocks (genesis excluded), with N = 60:

```
L = Σ_{i=1..N} i · min(6T, t_i − p_{i−1})      p_i = max(t_i, p_{i−1} + 1), p_0 = t_0
L = max(L, N²T/20)
D_next = (C_N − C_0) · T · (N+1) · 99 / (200 · L)        C = cumulative difficulty
```

Solve times are measured from the latest timestamp seen so far (`p`), so a block
dated earlier than its predecessor counts as 1 s and the next block is measured from
that adjusted time. Integer arithmetic only (256-bit intermediates). Recent blocks carry the most weight,
so the algorithm follows hash-rate changes within about N blocks while staying stable
(steady-state difficulty noise ~13%). Simulated on 20 random runs with a 10× hash-rate
spike for 200 blocks (3,000-block runs): difficulty reached 80% of the new level after
~61 blocks and the mean block time over the run was ~30.9 s. After a sudden 90% drop
in hash rate the first 60 blocks average ~106 s and difficulty is back within 10% after
~110–165 blocks (the 6T cap limits how fast it can fall). A miner who always uses the
maximum future timestamp raises difficulty a few percent and gains nothing.

Why not Monero's algorithm: its 720-block window with a 15-block lag takes about a
day to react at 2-minute blocks, which invites profit-switching and rented hash power
on a small chain. LWMA is the most widely deployed replacement in CryptoNote chains.

## 4. Network identity

| | Mainnet | Testnet | Stagenet |
|---|---|---|---|
| Address prefix (standard / integrated / subaddress) | 30598 `Pa` / 24839 `Pi` / 22408 `Ps` | 8479 `Te` / 11935 `Tf` / 15263 `Tg` | 28440 `Sa` / 22809 `Si` / 20378 `Ss` |
| Address length | 98 / 109 / 98 characters | 97 / 108 / 97 | 98 / 109 / 98 |
| P2P / RPC / ZMQ ports | 29960 / 29961 / 29962 | 29970 / 29971 / 29972 | 29980 / 29981 / 29982 |
| Network ID | `BC2D893E-96B8-F691-199F-373CE5BC4718` | testnet 3: set on its launch day by `make_genesis.py` | `0F57C4D1-D344-63D1-3D6F-FD9DD5F24042` |
| Genesis message | "Opacra mainnet genesis \| 2026-10-02 \| Private by default, auditable by choice." | "Opacra testnet 3 genesis \| <launch date> \| <headline>" (from `make_genesis.py`) | "Opacra stagenet genesis \| 2026-10-02" |

Message-signing domain: `OpacraMessageSignature` (signatures cannot be replayed on Monero).
Data directory `~/.opacra` (testnet: `~/.opacra/testnet3`), config file `opacra.conf`, log `opacra.log`.

Testnet 3 runs mainnet's exact rules: no slow start and no testnet exemptions; only its name,
network ID, ports, prefixes, genesis, fund address and checkpoint domain differ. Its genesis is
made with the launch-day procedure (`contrib/coin-identity/make_genesis.py apply` then
`verify`), which also rehearses mainnet's. It replaced testnet 2 (10-18 Oct 2026, RandomOPCA,
with a slow start), which replaced the first public testnet (4-10 Oct 2026, Monero's `rx/0`).

These values are the **development identity**. Generate fresh network IDs and genesis
transactions on launch day (`contrib/coin-identity/coinid.py`).

## 5. Changes from Monero v0.18.5.1

Consensus:

1. `src/cryptonote_config.h`: block time, emission constants, LWMA window
   and startup constants, future time limit, median window, identity (prefixes,
   ports, network IDs, genesis transactions), data directory name, signing domain.
2. `src/cryptonote_basic/difficulty.cpp`: `next_difficulty()` replaced by LWMA-1;
   `next_difficulty_64()` kept as a wrapper for API compatibility.
3. `src/cryptonote_basic/cryptonote_basic_impl.cpp/.h`: `get_block_reward()` uses a
   per-block emission factor and fixed tail (Monero's per-minute scaling truncates to
   zero below 60 s blocks); new `get_block_reward_at_height()` (one place for any height rule;
   today the reward does not depend on height).
4. `src/cryptonote_core/cryptonote_tx_utils.cpp`: coinbase construction uses
   `get_block_reward_at_height()`.
5. `src/cryptonote_core/blockchain.cpp/.h`: coinbase validation uses
   `get_block_reward_at_height()` (height passed in); block templates pass the height to
   the transaction pool.
6. `src/cryptonote_core/tx_pool.cpp/.h`: template filling uses the height-aware reward, so
   the expected reward reported to miners and pools is exact.
7. `src/hardforks/hardforks.cpp`: compact fork tables `{1 @ 0, 16 @ 1}` for all networks.
8. `src/blocks/checkpoints.dat`: emptied (Monero fast-sync hashes removed);
   `src/checkpoints/checkpoints.cpp`: Monero checkpoints removed.
9. `src/cryptonote_core/cryptonote_tx_utils.cpp`, `src/cryptonote_basic/cryptonote_format_utils.cpp`:
   Monero's hard-coded proof-of-work and block-id exceptions for its block 202612 removed
   (left in place they would let any block at Opacra height 202612 skip proof of work).
10. `src/cryptonote_core/blockchain.cpp` (`build_alt_chain`, `complete_timestamps_vector`,
    `handle_alternative_block`): side chains use exactly the main chain's median-time-past
    rule: the 11 previous blocks including genesis, and no check below height 11.
11. (Removed 18 Oct 2026: the slow start's block-size cap. Monero's size penalty applies from
    block 1.)
12. Side-chain difficulty floor (`difficulty.cpp` `alt_difficulty_acceptable`, used in
    `blockchain.cpp`): once the main chain is past 122 blocks (two LWMA windows, ~1 hour),
    a side-chain block at any height whose required difficulty is below 1/4 of the main
    chain's reference difficulty is refused. The reference is the lower of the next
    difficulty and the lowest main-chain difficulty of the last 720 blocks, so a node whose
    difficulty was inflated during an eclipse still accepts the honest chain. In the first
    hour the reference is capped at the startup guess (10,000). Block 1 costs the startup
    guess on every network, so no side block is free. Without checkpoints, a side chain forked from far back could
    claim hours of slow blocks and walk its difficulty down to almost nothing, then flood
    nodes with free blocks. A competing chain that could actually win never needs a much
    lower difficulty than ours, so honest reorgs of any depth still work. Side-chain
    blocks are also held to the 3-minute future time limit.
13. Future time limit handling (`blockchain.cpp`, `cryptonote_protocol_handler.inl`): a block
    with valid proof of work that is only ahead of this node's clock is rejected for now
    without penalising the peer (like Bitcoin's time-too-new), so a node with a slow clock
    cannot end up banning honest peers. The node remembers such blocks (up to 1,024) and
    refuses the same block again without rechecking its proof of work. The block is fetched again once the node's clock
    allows it (the next block arrives as an orphan and triggers a sync).
14. The generated-coins total is no longer capped at `MONEY_SUPPLY` (it now means the main
    curve, not 2^64−1); consensus is unchanged because rewards treat any total at or above
    10M as tail-only. Side-chain totals count only newly created coins, not fees.
15. Development fund (`cryptonote_basic_impl.cpp` `get_dev_fund_share` / `get_dev_fund_output`,
    `cryptonote_tx_utils.cpp` `construct_miner_tx`, `blockchain.cpp`
    `validate_miner_transaction`): from height 1 the coinbase's last output pays 5% of the
    subsidy to the fund with the per-block key R_f, appended to the extra field after the
    nonce (pools' `reserved_offset` still points at the extra nonce). The node refuses to
    start if the fund address is not a standard address or the published view key doesn't
    belong to it.
    `get_block_template` reports the miner's share as `expected_reward`; block headers'
    `reward` is the whole coinbase (miner + fund).

Network and wallet:

16. `src/coin_network.h` (new): seed nodes, DNS seeds, Tor/I2P seeds, DNS checkpoint,
   update and blocklist domains, download URLs, DNSSEC probe host. All empty or
   placeholders; nothing points at Monero infrastructure.
17. `src/p2p/net_node.h/.inl`, `src/checkpoints/checkpoints.cpp`, `src/common/updates.cpp`,
    `src/common/dns_utils.cpp`: read the lists above.
18. `src/wallet/wallet2.cpp`: hard-fork checks look versions up by value (the table
    skips versions 2–15); height estimate without Monero's rollback offsets; "recent
    output" window computed from the block time.
19. `src/simplewallet/simplewallet.cpp/.h`: `donate` uses `OPACRA_DONATION_ADDR`
    (empty = disabled) instead of the Monero donation address.
20. `src/cryptonote_core/cryptonote_core.cpp`: sync batch size no longer keyed to Monero's v4
    height; the block-rate monitor reads enough blocks for 30 s targets and computes its
    Poisson terms in log space (they overflowed to NaN above ~170 blocks). The weekly
    difficulty recheck covers the last 20,160 blocks instead of the whole chain.
21. Wallets: `ignore-outputs-above` defaults to 2^64−1 (Monero used `MONEY_SUPPLY`, which
    is no longer 2^64−1); OpenAlias records use `oa1:opca`.
22. `external/randomx` (now vendored instead of a git submodule): `RANDOMX_ARGON_SALT` is
    `"RandomOPCA\x01"`, as RandomX's documentation asks of every implementation. Every hash
    differs from Monero's `rx/0`, so Monero miners, pools and rental markets cannot mine
    Opacra unchanged (security audit item 1). Reference vector: key "test key 000", input
    "This is a test" → `460b9dbac09aa34bd64b275599f95195d2cd2eaf3dd6eb0b1e2631d9d3e7cafc`
    (Monero: `639183aa…`). XMRig needs `contrib/xmrig/opacra-xmrig.patch` (`rx/opca`).
    RandomX's own test program (`randomx-tests`) checks this vector (interpreter and JIT)
    and skips the upstream vectors, which only hold with Monero's salt; the MSVC assembler
    config (`src/asm/configuration.asm`) carries the same salt (19 Oct 2026).
    The vendored RandomX doesn't update itself: upstream fixes must be merged by hand.
23. DNS emergency checkpoints (v0.2.1, node policy, not consensus): `coin_network.h` lists
    `checkpoints.opacra.org`/`.com` (mainnet) and `testpoints.opacra.org`/`.com` (testnet);
    `core::update_checkpoints` reads them on every network that lists domains (Monero:
    mainnet only) every 5 minutes (Monero: hourly), passing the network type through
    `Blockchain::update_checkpoints`. The log says once when a new DNS checkpoint is read or
    enforced; "no two valid TXT records" is logged at level 1 instead of 0. Seeds enforce
    them (`enforce-dns-checkpointing=1`). Testnet 3's genesis checkpoint is written by
    `make_genesis.py verify --checkpoint`. Procedure: `docs/EMERGENCY_CHECKPOINTS.md`.
    v0.2.2: `core::on_idle` refreshes checkpoints on a timer (DNS reads on their own thread
    after start-up) and the call in the block-relay
    path (`handle_notify_new_fluffy_block`) is removed; `Blockchain::update_checkpoints` reads
    DNS without a lock, then changes `m_checkpoints` under the tx-pool and blockchain locks
    (Monero changed it unlocked); a DNS set with two hashes for one height is ignored whole;
    an enforcing node warns once when no checkpoint can be read. The testnet config-file and
    libwallet ringdb defaults use the testnet data folder (`testnet3` since 18 Oct 2026, item 26).
24. v0.2.4 (no consensus change): `src/common/dns_utils.cpp` trusts the root DNSSEC key
    KSK-2024 (`. IN DS 38696 8 2 683D…2B16`), which alone signs the root zone from 11 October
    2026; without it no DNSSEC record validated and DNS checkpoints could not be read (found
    by the testnet checkpoint drill, 12 Oct). The fallback resolvers, used over TCP when the
    system resolver cannot deliver DNSSEC-valid answers, are Quad9 and Cloudflare instead of
    Monero's list. `epee` `connection::add_ref` uses `weak_from_this().lock()` instead of
    catching `boost::bad_weak_ptr` from `shared_from_this()`, so closing connections no longer
    log a stack trace each (about 100 MB a day on the seed). Wallet: the "password needed"
    notice from background refresh is shown once, in plain words, until the next manual
    refresh. Testnet launchers mine with a quarter of the CPU threads by default
    (`MINE_THREADS` overrides it).

25. After v0.2.4 (node policy and launchers, no consensus change): home nodes report "no incoming
    connections" once, in plain words, instead of an hourly warning. A peer whose blocks a
    checkpoint refuses is blocked for 10 minutes (`OPACRA_CHECKPOINT_MISMATCH_BLOCK_SECONDS`)
    instead of 24 hours, and not scored, because after an emergency checkpoint honest nodes
    that followed an attacker relay its chain too. From the attack rehearsal
    (`docs/ATTACK_REHEARSAL.md`). The testnet launchers enforced DNS checkpoints from then
    until 23 Oct 2026; since v0.2.5 they only warn unless `ENFORCE_CHECKPOINTS=1`, and print
    at startup how to switch it on. Mainnet launches the same way; enforcement becomes the
    default in the first release after the two checkpoint domains move to separate
    registrars (see `docs/EMERGENCY_CHECKPOINTS.md`, "Who enforces").
26. 18 Oct 2026 (consensus): no launch slow start on any network; block 1 costs the startup
    difficulty on every network (testnet 2's exemption removed); testnet data folder
    `testnet3`; launch-day genesis procedure `contrib/coin-identity/make_genesis.py`.
27. 19 Oct 2026, from an independent review:
    - (consensus) launch-time rule: a block at height 1 or above whose timestamp is
      before the network's launch time (the time of the height-1 entry in its fork table) is
      invalid, on the main chain and on side chains (`Blockchain::check_launch_time`, called
      from `check_block_timestamp` and `handle_alternative_block`). Block templates are dated at
      or after it. With the 3-minute future time limit no node accepts block 1 earlier than
      3 minutes before the launch, and a chain mined in secret before the launch can't carry
      a week of earlier, honest-looking dates. It doesn't stop everything: someone holding the
      genesis early could still mine blocks dated just after the launch and bunch them up (so
      LWMA raises their difficulty), and release them once those dates are valid. So the main
      defence stays procedural: the genesis is made on launch day and kept private until
      mining opens, and the first checkpoint record follows within the hour. Regtest/fakechain
      has no launch time.
    - (node policy) a checkpoint rollback never goes below height 1, so genesis is
      never popped (a checkpoint at height 1 or 2 used to wrap the rollback height or crash);
      the checkpoint loop rereads the chain height after each rollback.
    - (node policy) the background checkpoint thread catches exceptions and logs
      them instead of aborting the daemon.
    Tests: `contrib/testnet/checkpoint_rollback_test.py`, `contrib/testnet/launch_time_test.py`.
28. 24 Oct 2026, from a second independent audit:
    - Monero v0.18.5.2 to v0.18.5.4: the 97 upstream commits since the fork were applied one by
      one (each keeps its upstream author and a "cherry picked from" line): P2P and parser
      hardening, mempool DoS ordering, restricted-RPC fixes, wallet checks against malicious
      daemons (including the reserve-proof key-image check), log injection fixes, OpenSSL 3.0.22
      and Unbound 1.26.1 for the Windows build. Not applied: upstream's own CI workflow and its
      release bumps (Monero's version, checkpoints and block-hash data). RandomX was moved to
      v1.2.3 in Opacra's vendored copy (CMake minimum and benchmark string only; salt unchanged).
      Where upstream touched code Opacra changed, Opacra's rules were kept: the launch-time rule
      stays in the main-chain timestamp check, a too-new block is still soft-rejected after its
      proof of work on both the main-chain and side-chain paths (upstream moved the future
      check into the shared function), the checkpoint refresh stays off the block-relay path,
      block templates keep the height parameter, and one copy of the KSK-2024 root key is kept
      (the retired KSK-2010 is removed).
    - (node policy) DNS checkpoints follow DNS: they are a set of their own that each
      successful read replaces, so a withdrawn or corrected record applies without a restart;
      when nothing can be read the last set stays; a DNS set contradicting a hard-coded or JSON
      checkpoint is ignored with a red log line instead of stopping the node
      (`checkpoints::set_dns_points`, `Blockchain::update_checkpoints`).
    - (wallet and RPC) development fund outputs are not used as decoys. `get_outs` marks each
      output that is the last output of a coinbase from block 1 (`dev_fund`, optional in the
      response, so older wallets and daemons are unaffected), and the wallet skips those when it
      picks ring members; it requests twice Monero's margin of candidates to make up for them.
      The fund's view key stays published: its spends are visible, so its outputs would be
      known-spent decoys in other people's rings.
    - Launch tools: seed setup has `--no-start` for staging; seeds accept 1000 incoming
      connections (was 128); `daily-checkpoint` requires `--network` and checks the nodes; the
      Windows launcher refuses an address file with more than one line.
    - (node policy) a checkpoint rollback keeps the blocks it removes. A node whose chain fails
      a checkpoint still rolls back to 2 blocks below it (never below genesis), but stores the
      removed blocks as a side chain (`Blockchain::rollback_keeping_blocks`) instead of
      deleting them as Monero does. After each checkpoint read the node switches to a stored
      side chain that is heavier than its main chain and passes every checkpoint now in force,
      with full validation (`Blockchain::switch_to_kept_chain`). So a wrong or forged record,
      even at block 1, costs no blocks once it is withdrawn or corrected. At startup such a
      heavier side chain is kept, and other side blocks are dropped as before
      (`Blockchain::drop_alt_blocks_keeping_heavier`). Test hook, never on mainnet:
      `OPACRA_TEST_DNS_CHECKPOINTS=<file>` reads the records from a file every 5 seconds.
      Test: `contrib/testnet/dns_withdraw_test.py`.
    - (node policy, 25 Oct 2026 review) DNS checkpoint sets carry a serial number, a
      `serial:N` TXT record beside the `height:hash` ones (older nodes skip it). An enforcing
      node remembers the highest serial it has seen (`dns_checkpoint_serial` in its data
      folder, so it survives restarts) and refuses a set with a lower serial, or without one
      once it has seen one, keeping its current checkpoints. DNSSEC proves a set was signed,
      not that it is current, so without this a replayed older answer could lift an emergency
      checkpoint and return the node to a chain it refused.
    - (node policy) the kept-chain check looks only at real tips (side blocks heavier than the
      main chain that no other side block builds on), skips a tip that failed the checkpoints
      in force until they change, and does nothing when no side block was added and the
      checkpoints are unchanged since the last look found nothing.
    - (RPC) `get_outs` reads an output's transaction to set `dev_fund` only when its unlock
      time is its height + 60 blocks, which consensus requires of every coinbase output, so
      ordinary outputs cost no extra read.
Branding (no behaviour change): string literals and binary names via
`contrib/coin-identity/rebrand.py` (`opacrad`, `opacra-wallet-cli`, `opacra-wallet-rpc`,
units opacra/milliop/microop/nanoop/picoop, `opacra:` payment URIs, file magic
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
  July 2026). Opacra can adopt it with a network upgrade (append `{17, height, 0, time}`)
  once it is released and audited.
