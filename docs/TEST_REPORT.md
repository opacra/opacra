# Test report: private 3-node network

Run 2026-10-03 16:07:32 to 2026-10-03 17:14:16 with `contrib/testnet/functional_test.py` on a 2-vCPU cloud VM (3 nodes on one machine, mainnet consensus rules, isolated from the internet).

**26 of 26 checks passed.**

![Difficulty and block times on the test network](images/test-network.png)

## Key numbers

| Measure | Result |
| --- | --- |
| Blocks mined | 130 (heights 0 to 129) |
| Mean block time after the 30-block startup | 31.03 s (target 30 s) |
| Median block time after startup | 25.0 s |
| Test transaction | 29 inputs, 3 outputs, 20186 bytes, fee 0.02683980 OPCA |
| Ring size of every input | [16] |
| Send to spendable (10 confirmations) | 327 s |
| Chain split | node 2 isolated at height 122; all nodes re-converged at heights [130, 130, 130] |
| Consensus replay | every block's difficulty and reward recomputed in Python; mismatches: 0 |

## Checks

| Check | Result | Detail |
| --- | --- | --- |
| genesis identical on all nodes | pass | 5280c46f32c71a63b78ad766654231adb5394bd5bbaeda4d5a38c9cec2ad5414 |
| genesis reward = MONEY_SUPPLY >> 22 | pass | 2384185791015 |
| standard addresses start with 'Pa' | pass | Pa2TMpn6Uced... |
| subaddresses start with 'Ps' | pass | Ps18VF4B6Vm3... |
| integrated addresses start with 'Pi' | pass | Pi2Dds4LKSud... |
| all nodes on the same chain tip | pass |  |
| mined coins unlocked (60-block coinbase lock) | pass |  |
| transaction confirmed in a block | pass | height 112 |
| RingCT with Bulletproofs+ (rct type 6) | pass |  |
| every input uses a 16-member ring | pass | [16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16] |
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
| recipient can re-spend received coins | pass | 47c159171c7fcbd88e984e5d58cf4e6b72401e0e67b32222a1115a2a35ab1390 |
| two competing chains exist | pass | 4a83ce111e38 vs bf178a4033f7 |
| network re-converged on one chain after the split (reorg) | pass | heights [130, 130, 130] |
| replayed 130 blocks: every difficulty matches LWMA-1 reference | pass |  |
| replayed 130 blocks: every reward matches emission+slow-start+fees | pass |  |

## What this does not cover

- Behaviour under real-world latency, many peers, or adversarial miners (use the public testnet).
- Blocks above the median weight (the slow-start size cap is covered by `tests/opacra`).
- Hardware wallets and the GUI (not part of this fork).
- Side-chain, future-timestamp and slow-clock rules: `contrib/testnet/block_rules_test.py`;
  the side-chain difficulty floor: `tests/opacra`. Review: `docs/REVIEW_2026-10.md`.

Genesis hash: `5280c46f32c71a63b78ad766654231adb5394bd5bbaeda4d5a38c9cec2ad5414`
