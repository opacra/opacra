# Opacra release notes

What changed in each release, for users, miners and node operators. Technical details
are in `docs/OPACRA_SPEC.md` (section 5).

## v0.2.6 (testnet 3)

Testnet 3 is a new chain. Use a new folder and a new wallet; nothing from testnet 2 carries
over. It runs exactly the rules planned for mainnet.

### Security fixes from Monero

- Every fix Monero published from v0.18.5.2 to v0.18.5.4 (97 changes) is included:
  peer-to-peer and parser hardening, mempool protection against flooding, restricted-RPC
  fixes, extra wallet checks against a malicious node (including reserve proofs), and log
  injection fixes.
- The Windows build uses OpenSSL 3.0.22 and Unbound 1.26.1, and RandomX v1.2.3
  (Opacra's RandomOPCA salt is unchanged).

### Emergency checkpoints

- Nodes follow the DNS checkpoint records as they are at each read (every 5 minutes). A
  record that is withdrawn or corrected applies without a restart.
- A DNS record that contradicts a checkpoint built into the node is ignored, with a red line
  in the log, and the node keeps running.
- A node whose chain fails a checkpoint rolls back below it as before, but now keeps the
  blocks it removes, also across a restart. If the record was wrong and is withdrawn or
  corrected, the node returns to those blocks within about 5 minutes. Nothing is lost unless
  one of the two blocks the node may still add below the record conflicts with a kept one;
  the node then fetches the honest blocks from its peers.
- Every set of records carries a serial number (`serial:N`, a Unix time). A node refuses
  records older than the newest it has seen, the same serial with different records, and
  unusable serials (not a plain number, several, or more than a day ahead). It remembers the
  newest serial and its records across restarts, also when it only warns, and each release
  builds in a minimum. So a replayed old DNS answer, or one caught mid-edit, can't lift an
  emergency checkpoint, and a bad serial can't lock nodes out.
- If no record can be read at all, nodes keep the last records they accepted, also across a
  restart, so a DNS outage cannot lift a checkpoint during an attack.

### Wallet privacy

- Wallets no longer pick development fund outputs as decoys. The fund's view key is
  public, so those outputs made poor decoys. Rings stay at 16 members. The node marks fund
  outputs in `get_outs` (`dev_fund`). Other wallet software should skip them too: a ring
  that contains a fund output now stands out as made by older or different software.

### Mining and the launchers

- The launchers ("Start Opacra testnet" on Windows, `start-testnet.sh` on Linux) only warn
  about emergency checkpoints, and say at startup how to follow them: `set
  ENFORCE_CHECKPOINTS=1` in the Windows start file, or `ENFORCE_CHECKPOINTS=1
  ./start-testnet.sh`. During an attack opacra.org asks miners to switch it on. Seeds, pools
  and exchanges follow them from the start. The launchers will follow them by default in a
  later release, once the two checkpoint domains are held at separate registrars.
- The Windows launcher refuses a wallet address file with more than one line.

### For seed and node operators

- Seeds accept up to 1,000 incoming connections (was 128); the setup script raises existing
  seeds too.
- `seed-node-setup.sh --no-start` installs or upgrades a seed without starting it.
- Seeds keep 3 old logs instead of 50 (`max-log-files=3`, added to existing seeds by the
  setup script). At the seeds' log level a log doesn't record where transactions came from.
- `daily-checkpoint` requires `--network mainnet` or `--network testnet` and refuses nodes
  on another network.
- The seed's phone alerts also report a rollback for a checkpoint, the return to the kept
  blocks, and a refused older answer.
- Every change to the checkpoint records needs a new, higher `serial:` record on both
  domains (`date +%s`, digits only), changed last. See `docs/EMERGENCY_CHECKPOINTS.md`.
- `get_outs` reads a transaction only for outputs that can be coinbase outputs, so
  public RPC requests for many outputs stay cheap.
- The block explorer may read the seed's chain but write only LMDB's lock file
  (opacra-explorer repository).
- Run v0.2.6 or later wherever checkpoints are enforced. Older nodes deleted the blocks a
  checkpoint rolled back.

### Tests added

`contrib/testnet/dns_withdraw_test.py` (wrong, withdrawn and corrected checkpoint records,
and replayed older answers),
`contrib/testnet/decoy_test.py` (fund outputs never used as decoys), and the Windows
launcher check `contrib/windows/test-launcher.sh`. The full functional test now stops what
it started and refuses ports that are already in use.
