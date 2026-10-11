# Mining security audit, October 2026

Scope: everything Opacra changed from Monero v0.18.5.1 that affects mining and block
acceptance. That covers block rewards, the slow start, the development fund, LWMA
difficulty, timestamps, side chains and reorganisations, block relay, and the release
configuration of seed nodes. Monero's own code (RandomX, RingCT, p2p) was taken as
reviewed upstream. The method was code reading, simulations with the real consensus
functions, live tests on throwaway regtest nodes, and a second independent reviewer who
had not seen the fixes being written. This is not a substitute for a paid human audit
before mainnet.

Release: **v0.1.3.0**. The public testnet must upgrade before **block 30,000** (see the
fund-key change below).

## Summary

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | High (mainnet) | Opacra uses Monero's own RandomX, so anyone can rent or redirect Monero hash power and outmine the whole network; with no checkpoints there is no limit on how deep they can rewrite | Partly fixed: own RandomX salt (v0.2.0), DNS emergency checkpoints and testnet hard-coded checkpoints (v0.2.1); attack rehearsal and alerts still to do (see the mining security plan) |
| 2 | High | Free side-chain blocks near genesis: anyone could send any node unlimited side blocks at height 1 (difficulty 1) and near-free ones up to height 121, for as long as the chain exists | Fixed in v0.1.3 |
| 3 | Medium | Development-fund outputs could be pre-burned: the fund's transaction key for every future block was public, so a decoy output with the same one-time key could be planted in advance | Fixed in v0.1.3 (testnet from block 30,000) |
| 4 | Medium | After an eclipse, a node whose difficulty an attacker had inflated would refuse the honest chain for ever | Fixed in v0.1.3 |
| 5 | Low | A block refused only for being too far in the future could be resent endlessly without penalty, each time costing a RandomX check | Fixed in v0.1.3 |
| 6 | Info | 30-second blocks: more orphans, and a 60-block (30-minute) coinbase lock | Documented |

## 1. Shared RandomX hash power (partly fixed)

Before v0.2.0, Opacra's RandomX was configured exactly as Monero's (`external/randomx/src/configuration.h`,
`RANDOMX_ARGON_SALT "RandomX\x03"`, XMRig's `rx/0`); v0.2.0 gave it its own salt (point 5 below). At that time every Monero miner, pool and hash-rate
rental market could point at Opacra without changing anything. The testnet runs at about
2 kH/s, and even a successful mainnet will be a tiny fraction of Monero's. In August 2025
the Qubic pool claimed a majority of Monero's own hash rate and reorganised several Monero
blocks ([The Block](https://www.theblock.co/post/366535/monero-faces-chain-reorganization-fears-after-qubic-says-it-controls-51-of-hashrate),
[Halborn](https://www.halborn.com/blog/post/explained-the-monero-51-percent-attack-august-2025)).
A small chain on the same algorithm is far easier to overpower.

What an attacker with more hash power than the rest of the network can do:
- rewrite recent blocks and double-spend payments that were considered final;
- mine every block, so others earn nothing (selfish mining);
- reorganise past the 60-block coinbase lock (30 minutes) and orphan miners' rewards.

They cannot steal coins from wallets, create coins beyond the reward, skip the
development fund, or break privacy. Consensus rules still apply to their blocks.

No code change can stop someone with more hash power. These measures limit the damage and
raise the cost; they are listed in order of value for money:
1. **Checkpoints in every release** (`src/checkpoints/checkpoints.cpp`,
   `contrib/launch/make_checkpoint.sh`). Nodes refuse any reorganisation below the
   newest checkpoint. Add one at launch day + 1 and then in every release.
2. **DNS checkpoints** (MoneroPulse-style). **Done in v0.2.1 (11 Oct 2026):**
   `checkpoints.opacra.org`/`.com` and `testpoints.opacra.org`/`.com`, both zones
   DNSSEC-signed in a dedicated 2FA registrar account; both names must agree. Read every
   5 minutes on mainnet and testnet; seeds enforce them. Procedure:
   `docs/EMERGENCY_CHECKPOINTS.md`.
3. **Published confirmation guidance** (now in `docs/MINING.md`): 20 blocks (10 minutes)
   for ordinary payments, 120 blocks (1 hour) for large amounts and exchange deposits.
4. **Monitoring.** Run seeds with `--block-rate-notify` (already built in) and alert when
   the block rate or a reorganisation looks abnormal.
5. **An Opacra-specific RandomX variant. Done in v0.2.0 (10 Oct 2026).** RandomOPCA changes
   only RandomX's Argon2 salt, as RandomX's documentation asks of every implementation, so
   the algorithm's design and security analysis are unchanged. Rental markets and Monero
   pools can no longer redirect hash power without new software. Miners use the built-in
   miner or the Opacra XMRig build (`rx/opca`). Live test on a local node: stock XMRig
   (`rx/0`) submitted 10 blocks and all 10 were refused for insufficient proof of work; the
   Opacra build mined 17 blocks, all accepted. The public testnet was restarted as testnet 2.

## 2. Free side-chain blocks near genesis (fixed)

The side-chain difficulty floor (1/4 of the main chain's difficulty) did not apply to side
blocks below height 122, at any time, not only in the launch hour. Two facts made those
heights nearly free:
- block 1's difficulty was 1, because LWMA has no history;
- the genesis block's timestamp is 0, so a side chain forked from genesis can claim days
  of slow blocks, and LWMA walks its difficulty down to about 16 by height 121.

A side chain forked from genesis costs about 150,000 hashes in total (a few minutes on one
laptop core). After that, unlimited sibling blocks at height 1 cost 1 hash each, and at
height 121 about 16. Every one is checked with RandomX and stored in the node's side-chain
table.

**Live test, v0.1.2** (`contrib/testnet/side_chain_spam_test.py`, regtest at real
difficulty, main chain 12 blocks): 20 of 20 free side blocks at height 1 were accepted and
stored. The same test on v0.1.3 stored 0 of 20.

**Fix** (`difficulty.cpp` `alt_difficulty_acceptable`, `blockchain.cpp`):
- Block 1 costs the startup guess (10,000) instead of 1, on every network except the
  public testnet, whose block 1 already exists. The weekly difficulty recheck uses the
  same rule.
- In the first hour (main chain below 122 blocks) side blocks need 1/4 of min(main
  reference, 10,000). Honest blocks always meet this, even when LWMA jumps 10x after the
  startup guess.
- After the first hour, side blocks at every height need 1/4 of the main chain's reference
  difficulty.

**Trade-off.** Suppose a launch partition splits within the first 12 blocks and is still
split after the first hour. It cannot then merge by itself: those blocks have the fixed
difficulty of 10,000, below the floor once the network is faster than about 1.3 kH/s.
Nodes on the losing side need `pop_blocks` and a resync. Launch with at least two seeds and
check that every public node is on the same chain after the first hour. Accepting those
blocks instead would allow unlimited side blocks at 10,000 hashes each for ever, a
continuous DoS that costs an attacker only a few dollars a day in rented hash power.

## 3. Development-fund outputs could be pre-burned (fixed)

The fund's transaction key was r_f = Hs("OpacraDevFund" ‖ height), so anyone could work out
the one-time key of every future fund output. That allows Monero's "burning bug" attack:
1. Send the fund a tiny output with the same one-time key as the fund output of a future
   block H. This costs one transaction fee (about 0.003 OPCA), and the fund's wallet
   decodes it correctly because r_f is public.
2. If the fund wallet spends that decoy before block H arrives (a sweep of small outputs
   would), its key image is the same as block H's fund output.
3. When block H arrives, `wallet2` sees an already-spent output with that key and ignores
   the real one. The block's fund payment is then unspendable for ever.

An attacker could prepare this for thousands of future blocks in advance. A view-only
auditor would also see the decoys as fund income.

**Fix:** r_f = Hs("OpacraDevFund" ‖ height ‖ previous block's hash). The key is unknown
until block H−1 exists. A decoy can then at best land in block H itself, where the wallet
processes the coinbase first and keeps it (it keeps the larger of two outputs with the
same key). Mainnet and regtest use the new key from block 1. The public testnet switches
at block 30,000, and its blocks below that keep the original key, tested to be bit-for-bit
identical.

## 4. Eclipse plus inflated difficulty (fixed)

The floor compared side blocks with the main chain's next difficulty. An attacker who
eclipses a node can feed it blocks stamped 1 second apart. This raises that node's
difficulty 4x in 27 blocks, about 52 honest blocks of work. Once the eclipse ends, every
honest block is below 1/4 of the inflated difficulty, so the node refuses the honest chain
and penalises the peers that send it, for ever.

**Fix:** the floor's reference is now the lower of the next difficulty and the lowest
main-chain difficulty of the last 720 blocks, counting only blocks after the first hour
(`Blockchain::get_alt_floor_reference`). The attacker would need more than 720 inflated
blocks, about a day of the whole network's hash power. The floor can only be lower than
before, so it never refuses a block the old rule accepted.

## 5. Replaying a too-new block (fixed)

A block with valid proof of work but a timestamp more than 3 minutes ahead of the node's
clock is refused without penalising the peer, because the node's own clock may be wrong.
The same block could be sent again and again, and each time the node redid the RandomX
check.

**Fix:** such blocks are remembered (up to 1,024; the block id commits to the timestamp
and every transaction) and refused again without rechecking until the clock catches up.
In the regression run, the node with a slow clock received the same blocks 103 times and
checked proof of work once.

## 6. Notes

- **30-second blocks.** Orphans are more common than on Monero (the two-miner testnet
  run saw several single-block races a night), and a well-connected miner gains a little
  from that. The coinbase lock is 60 blocks, 30 minutes. See the confirmation guidance.
- **Pools** must credit miners from `expected_reward` (documented). Pools that build their
  own coinbase must include the previous block's hash in the fund key (documented in
  `docs/MINING.md`).
- **Seed RPC** binds to localhost only (`contrib/launch/opacra.conf`), so nobody can start
  mining or stop the daemon on a seed remotely.

## Checked and sound

- **Emission:** the 10M curve, tail emission, slow-start ramp and generated-coins total
  (unchanged from the October review, and confirmed again on the live testnet: 0.72 OPCA
  at block 6,413, exactly on the ramp).
- **Coinbase validation:**
  - the fund amount, one-time key, view tag and position are all enforced;
  - the coinbase's public keys must be exactly [miner, R_f];
  - partial rewards cannot short the fund;
  - blocks above the median are refused during the slow start;
  - a miner can neither claim more than subsidy plus fees nor move subsidy into fees.
- **LWMA:**
  - no overflow (256-bit intermediate values);
  - out-of-order timestamps count as 1 second;
  - solve times are capped at 6T, with a floor on the weighted sum;
  - with the 3-minute future limit and an 11-block median, an attacker can push the
    difficulty only a few percent down, or waste their own work pushing it up.
- **Main and side chains** use exactly the same difficulty window and the same
  median-time-past rule.
- **Fork table:** only version 16 (RandomX) from block 1. Monero's hard-coded proof of
  work for its block 202612 is removed.
- **The prev-hash fund key** is applied identically in templates (including cached
  templates and `get_block_template` with `prev_block`), in main-chain validation and in
  side-chain blocks validated at reorganisation. Nothing in the wallet derives it.
- **Locking:** the new node state (too-new cache, floor cache) is only touched under the
  blockchain lock.

## Tests

- `tests/opacra` (`opacra_consensus_tests`): 0 failures. New checks cover:
  - the floor at every height;
  - the first-hour floor and block 1;
  - a side chain from genesis (0 of 121 blocks accepted after the first hour);
  - the eclipse-inflation case;
  - the fund key changing with the previous block;
  - the testnet's legacy key below 30,000.
- `contrib/testnet/block_rules_test.py`: 25/25 on v0.1.3.
- `contrib/testnet/side_chain_spam_test.py` (new): v0.1.2 stored 20/20 free side blocks;
  v0.1.3 stored 0/20.
- Independent review of the fixes. It found these problems, all fixed before release:
  - the first version's block-1 rule could split an isolated launch miner from the network
    for ever;
  - the lookback included the fixed startup blocks for six hours;
  - the weekly difficulty recheck needed the block-1 rule too (found while fixing the
    first problem).

## Follow-up review of v0.2.0 and v0.2.1 (11 Oct 2026)

Two independent reviewers, who had not seen the changes being written, checked v0.2.0
(RandomOPCA, testnet 2, Opacra XMRig) and v0.2.1 (DNS emergency checkpoints). No critical
or high findings. Fixed in v0.2.2:

| Severity | Finding | Fix |
|---|---|---|
| Medium | XMRig and libuv were cloned by tag only; a moved tag would change the signed miner | `build-xmrig.sh` checks the exact commits and always clones libuv fresh |
| Medium | The Windows "Start testnet mining" launcher ran commands hidden in a pasted address (`&`, `|`) | The saved address must be letters and digits only, and is quoted with delayed expansion |
| Medium | An enforcing seed that could not read DNS checkpoints said so only at log level 1 | A red warning once, and a notice when reading works again |
| Low | `m_checkpoints` was changed without the blockchain lock while block validation reads it (inherited from Monero, more frequent with the 5-minute timer) | DNS read without a lock, list changed under the tx-pool and blockchain locks |
| Low | Two DNS records with different hashes for one height loaded half the set | The whole set is ignored and logged |
| Low | The DNS lookup ran in the block-relay path | Only the idle timer refreshes checkpoints |
| Low | The launcher's `(it starts with Te)` closed its `if` block early, so it asked for the address every time | Rewritten without brackets |
| Low | Testnet config-file and libwallet ringdb defaults still said `testnet` | `testnet2` |
| Info | The XMRig coinbase relaxation applied to every coin | Limited to `--coin opacra` |
| Info | The XMRig donation-level edit was not checked | The build stops if it did not apply |

Documented rather than changed: testnet 2 keeps the testnet exemption from the block-1
startup difficulty (its block 1 was mined under it); enforcing nodes keep a DNS checkpoint
until restart, and a hash changed in place stops them (`docs/EMERGENCY_CHECKPOINTS.md`); both
DNS zones are in one registrar account (second registrar planned before mainnet). Checked
and sound: the vendored RandomX is byte-identical to upstream 6c4340b apart from the salt;
XMRig's salt matches the node's; mainnet and stagenet identity unchanged; the fund-key
binding is applied identically in every path; non-enforcing nodes only warn; peers cannot
influence DNS checkpoints; the testnet checkpoint at block 2000 matches the chain (the
enforcing seed and the PC run past it without a rollback).

