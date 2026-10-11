# Chain audit

`contrib/launch/opacra-audit` checks every block of a chain against Opacra's rules,
recomputed from the specification rather than taken from the node's code. Anyone with a
synced node can run it and get the same answer; it is how the project shows that the
emission and the development fund work as published.

| Check | What must hold for every block |
|---|---|
| Chain links | Heights run without gaps, each block names the previous block's hash, cumulative difficulty is the previous total plus this block's |
| Timestamps | Not below the median of the previous 11 blocks |
| Difficulty | Equals LWMA-1 (N = 60, 30 s target) recomputed from the previous blocks; block 1 is 1 on the testnet, 10,000 elsewhere; 10,000 for blocks 2-12 |
| Coinbase form | Input names the block height, outputs locked for 60 blocks, no RingCT data, header reward equals the outputs |
| Block rewards | Outputs total exactly `max((10,000,000 OPCA - created) >> 22, 0.05 OPCA)`, scaled by `height / 20,160` during the slow start, plus the block's transaction fees |
| Development fund | Last output is exactly 5% of the subsidy (rounded down), paid to the one-time key derived from `Hs("OpacraDevFund" ‖ height ‖ previous hash)` and the fund address, found with the published view key, with the right view tag; the coinbase's transaction keys are exactly [miner's key, fund key] |
| Total coins created | The node's own total (`get_coinbase_tx_sum`) equals the sum of the rules, and its fee total equals the fees in the blocks |

Blocks heavier than 75 kB can carry a size penalty that depends on the median block
weight; for those the reward is only checked to lie between the fees and the full reward
(none can occur during the slow start, which the audit also checks).

The script uses only the Python standard library: its Keccak, base58 and ed25519 code is
included and was checked against a reference Keccak implementation and against the fund
addresses' published view keys.

## Run it

On the seed (testnet):

```
opacra-audit --quiet --report /root/audit-$(date +%F).txt
```

Mainnet: add `--rpc 127.0.0.1:29961`. It stops 10 blocks below the tip (a block replaced
while it runs would otherwise look like a broken link); `--to H` stops earlier. About 100
blocks a second on a seed. Exit status: 0 all passed, 1 a check failed, 2 could not run.

## Tested (11 Oct 2026)

- A private regtest chain with two real payments: every check passed, including fees and
  the node's totals.
- Ten kinds of tampering fed in between the node and the checker (an atomic unit too much
  for the miner, the fund short by one unit, the fund paid to another key, a wrong view tag,
  a third transaction key, a broken link, an old timestamp, no lock time, a changed fee, a
  wrong node total), and a block claiming one unit more difficulty than LWMA allows: each
  was caught by the right check.
- A private testnet chain mined on a workstation: every block's difficulty matched,
  through the startup blocks and past the first full 61-block LWMA window, as did the
  testnet fund's payments.

## Audit log

| Date | Network | Blocks | Result |
|---|---|---|---|
| 11 Oct 2026 | Testnet 2 | 0 to 3,981 | All checks passed. 939.714265 OPCA created (genesis included), fund 46.866504 OPCA (5.0% of the 937.33 OPCA mined since genesis), average block time 30.0 s, longest gap 5 min 30 s (before block 3,769, while the PC switched to the Windows launcher). No transactions yet, so fees were not exercised. |
