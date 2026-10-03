# Test report: private 3-node network

Run 2026-10-03 23:54:05 to 2026-10-04 00:57:24 with `contrib/testnet/functional_test.py` on a 2-vCPU cloud VM (3 nodes on one machine, mainnet consensus rules, isolated from the internet).

**28 of 28 checks passed.**

![Difficulty and block times on the test network](images/test-network.png)

## Key numbers

| Measure | Result |
| --- | --- |
| Blocks mined | 128 (heights 0 to 127) |
| Mean block time after the 30-block startup | 30.9 s (target 30 s) |
| Median block time after startup | 20.0 s |
| Test transaction | 28 inputs, 3 outputs, 19527 bytes, fee 0.02598310 OPCA |
| Ring size of every input | [16] |
| Send to spendable (10 confirmations) | 276 s |
| Chain split | node 2 isolated at height 120; all nodes re-converged at heights [128, 128, 128] |
| Consensus replay | every block's difficulty and reward recomputed in Python; mismatches: 0 |

## Checks

| Check | Result | Detail |
| --- | --- | --- |
| genesis identical on all nodes | pass | 5280c46f32c71a63b78ad766654231adb5394bd5bbaeda4d5a38c9cec2ad5414 |
| genesis reward = MONEY_SUPPLY >> 22 | pass | 2384185791015 |
| standard addresses start with 'Pa' | pass | Pa2TZ2urFTh2... |
| subaddresses start with 'Ps' | pass | Ps18nL619bwL... |
| integrated addresses start with 'Pi' | pass | Pi2DpLpB5B1K... |
| all nodes on the same chain tip | pass |  |
| mined coins unlocked (60-block coinbase lock) | pass |  |
| transaction confirmed in a block | pass | height 110 |
| RingCT with Bulletproofs+ (rct type 6) | pass |  |
| every input uses a 16-member ring | pass | [16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16] |
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
| recipient can re-spend received coins | pass | 732bee0515ad94ddb9a873859d4e1df88d698e7579dd6357de298258fc063eee |
| two competing chains exist | pass | 487807dc6861 vs f79779aafb85 |
| network re-converged on one chain after the split (reorg) | pass | heights [128, 128, 128] |
| replayed 128 blocks: every difficulty matches LWMA-1 reference | pass |  |
| replayed 128 blocks: every reward matches emission+slow-start+fees | pass |  |
| replayed 128 blocks: every coinbase pays the development fund 5% of the subsidy | pass | fund total 0.048062 OPCA |
| anyone can audit the development fund with its public view key | pass | view-only wallet sees 0.048062 OPCA, chain owes 0.048062 |

## What this does not cover

- Behaviour under real-world latency, many peers, or adversarial miners (use the public testnet).
- Blocks above the median weight (the slow-start size cap is covered by `tests/opacra`).
- Hardware wallets and the GUI (not part of this fork).
- Side-chain, future-timestamp and slow-clock rules: `contrib/testnet/block_rules_test.py`;
  the side-chain difficulty floor: `tests/opacra`. Review: `docs/REVIEW_2026-10.md`.

Genesis hash: `5280c46f32c71a63b78ad766654231adb5394bd5bbaeda4d5a38c9cec2ad5414`
