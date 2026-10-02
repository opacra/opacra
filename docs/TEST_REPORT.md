# Test report: private 3-node network

Run 2026-10-03 00:17:54 to 2026-10-03 01:21:32 with `contrib/testnet/functional_test.py` on a 2-vCPU cloud VM (3 nodes on one machine, mainnet consensus rules, isolated from the internet).

**26 of 26 checks passed.**

![Difficulty and block times on the test network](images/test-network.png)

## Key numbers

| Measure | Result |
| --- | --- |
| Blocks mined | 128 (heights 0 to 127) |
| Mean block time after the 30-block startup | 30.22 s (target 30 s) |
| Median block time after startup | 15.0 s |
| Test transaction | 25 inputs, 3 outputs, 17550 bytes, fee 0.00144080 OPCA |
| Ring size of every input | [16] |
| Send to spendable (10 confirmations) | 378 s |
| Chain split | node 2 isolated at height 120; all nodes re-converged at heights [128, 128, 128] |
| Consensus replay | every block's difficulty and reward recomputed in Python; mismatches: 0 |

## Checks

| Check | Result | Detail |
| --- | --- | --- |
| genesis identical on all nodes | pass | 5280c46f32c71a63b78ad766654231adb5394bd5bbaeda4d5a38c9cec2ad5414 |
| genesis reward = MONEY_SUPPLY >> 22 | pass | 2384185791015 |
| standard addresses start with 'Pa' | pass | Pa2TVqCWxi7V... |
| subaddresses start with 'Ps' | pass | Ps18ZEuw6Sc8... |
| integrated addresses start with 'Pi' | pass | Pi2Dsm3G9vyZ... |
| all nodes on the same chain tip | pass |  |
| mined coins unlocked (60-block coinbase lock) | pass |  |
| transaction confirmed in a block | pass | height 110 |
| RingCT with Bulletproofs+ (rct type 6) | pass |  |
| every input uses a 16-member ring | pass | [16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16] |
| outputs carry view tags | pass |  |
| amounts hidden on chain (all vout amounts 0) | pass |  |
| no plaintext addresses in tx | pass |  |
| recipient 2 received exact amount | pass | 0.05 OPCA |
| recipient 3 (subaddress) received exact amount | pass | 0.02 OPCA |
| received funds spendable after 10 blocks | pass |  |
| tx key proves payment to recipient (check_tx_key) | pass | 0.05 OPCA, 10 conf |
| payment proof verifies for a third party (get/check_tx_proof) | pass |  |
| payment proof bound to its message | pass |  |
| reserve proof shows balance without revealing history | pass | total 0.05 OPCA |
| view-only (auditor) wallet sees incoming payments | pass | 0.05 OPCA |
| recipient can re-spend received coins | pass | 29a61a28e98161eb7dcc3930efca20f7494837dc41a18e59cda4421bd59b086a |
| two competing chains exist | pass | 01a7daefff04 vs 834e3a6aa127 |
| network re-converged on one chain after the split (reorg) | pass | heights [128, 128, 128] |
| replayed 128 blocks: every difficulty matches LWMA-1 reference | pass |  |
| replayed 128 blocks: every reward matches emission+slow-start+fees | pass |  |

## What this does not cover

- Behaviour under real-world latency, many peers, or adversarial miners (use the public testnet).
- Blocks above the median weight (the slow-start size cap is covered by `tests/opacra`).
- Hardware wallets and the GUI (not part of this fork).

Genesis hash: `5280c46f32c71a63b78ad766654231adb5394bd5bbaeda4d5a38c9cec2ad5414`

## External miner: XMRig

_XMRig was tested on the build before the rename (Tacita, 2026-09-28). The proof-of-work, block format and daemon RPC are unchanged by the rename; only the coin identity differs._

After the functional test, XMRig 6.26.0 (built from source, unmodified) mined against node 0
in daemon (solo) mode with no built-in miner running:

```
./xmrig -o 127.0.0.1:31001 --daemon -u <wallet address> --coin monero -t 2
 * POOL #1      127.0.0.1:31001 coin Monero
 net      new job from 127.0.0.1:31001 diff 11790 algo rx/0 height 143 (1 tx)
 randomx  dataset ready (11841 ms)
 cpu      accepted (1/0) diff 11790 (19 ms)
 cpu      accepted (2/0) diff 11731 (13 ms)
 cpu      accepted (3/0) diff 12042 (14 ms)
 miner    speed 10s/60s/15m 683.0 n/a n/a H/s max 698.3 H/s
```

Over two runs XMRig added 18 blocks (heights 128 to 145); all three nodes accepted them and share the same tip.
`--coin monero` only selects the block format and algorithm; Opacra uses both unchanged.

## What this does not cover

- Behaviour under real-world latency, many peers, or adversarial miners (use the public testnet).
- Blocks above the median weight (the slow-start size cap is covered by `tests/opacra`).
- Hardware wallets and the GUI (not part of this fork).

Genesis hash: `b84ffdd40b388fda7e5d9eddb84355c1791f65e1b315d9e5c9d07f9880aee2f3`
