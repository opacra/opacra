# Test report: private 3-node network

Run 2026-10-03 21:48:59 to 2026-10-03 22:51:11 with `contrib/testnet/functional_test.py` on a 2-vCPU cloud VM (3 nodes on one machine, mainnet consensus rules, isolated from the internet).

**28 of 28 checks passed.**

![Difficulty and block times on the test network](images/test-network.png)

## Key numbers

| Measure | Result |
| --- | --- |
| Blocks mined | 129 (heights 0 to 128) |
| Mean block time after the 30-block startup | 29.91 s (target 30 s) |
| Median block time after startup | 20 s |
| Test transaction | 30 inputs, 3 outputs, 20845 bytes, fee 0.02769650 OPCA |
| Ring size of every input | [16] |
| Send to spendable (10 confirmations) | 306 s |
| Chain split | node 2 isolated at height 120; all nodes re-converged at heights [129, 129, 129] |
| Consensus replay | every block's difficulty and reward recomputed in Python; mismatches: 0 |

## Checks

| Check | Result | Detail |
| --- | --- | --- |
| genesis identical on all nodes | pass | 5280c46f32c71a63b78ad766654231adb5394bd5bbaeda4d5a38c9cec2ad5414 |
| genesis reward = MONEY_SUPPLY >> 22 | pass | 2384185791015 |
| standard addresses start with 'Pa' | pass | Pa2TNScLz8PH... |
| subaddresses start with 'Ps' | pass | Ps18fqG3DAmA... |
| integrated addresses start with 'Pi' | pass | Pi2Do6gGdCs9... |
| all nodes on the same chain tip | pass |  |
| mined coins unlocked (60-block coinbase lock) | pass |  |
| transaction confirmed in a block | pass | height 110 |
| RingCT with Bulletproofs+ (rct type 6) | pass |  |
| every input uses a 16-member ring | pass | [16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16] |
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
| recipient can re-spend received coins | pass | e68f6a59b098b033f95fea25552c4643f76d0018d2de87a578fdbadb5818f9b2 |
| two competing chains exist | pass | 1734d4932f2d vs b6ae295d9002 |
| network re-converged on one chain after the split (reorg) | pass | heights [129, 129, 129] |
| replayed 129 blocks: every difficulty matches LWMA-1 reference | pass |  |
| replayed 129 blocks: every reward matches emission+slow-start+fees | pass |  |
| replayed 129 blocks: every coinbase pays the development fund 5% of the subsidy | pass | fund total 0.048819 OPCA |
| anyone can audit the development fund with its public view key | pass | view-only wallet sees 0.048819 OPCA, chain owes 0.048819 |

## What this does not cover

- Behaviour under real-world latency, many peers, or adversarial miners (use the public testnet).
- Blocks above the median weight (the slow-start size cap is covered by `tests/opacra`).
- Hardware wallets and the GUI (not part of this fork).
- Side-chain, future-timestamp and slow-clock rules: `contrib/testnet/block_rules_test.py`;
  the side-chain difficulty floor: `tests/opacra`. Review: `docs/REVIEW_2026-10.md`.

Genesis hash: `5280c46f32c71a63b78ad766654231adb5394bd5bbaeda4d5a38c9cec2ad5414`
