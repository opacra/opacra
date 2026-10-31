# Opacra release notes

What each release means for users, miners and node operators. Technical details are in
`docs/OPACRA_SPEC.md`.

## v1.0.0

Opacra's first full version. It runs the rules mainnet will launch with.

**On the testnet (testnet 3):** the same chain and the same wallets as before. Unzip v1.0.0
into a new folder, copy your `testnet-wallet`, `testnet-wallet.keys` and
`testnet-wallet.address.txt` into it, and start it. On Windows, make sure the old node has
quit before starting the new one (Task Manager: no `opacrad.exe` running).

**Mainnet:** the mainnet genesis block is made on launch day from that day's headline, and
the mainnet download is published at the announced launch time, on opacra.org only. Nobody,
the project included, can mine before then.

**What Opacra is:**
- A private coin with its own blockchain: every payment hides the sender, the receiver and the
  amount (ring signatures with 16 members, stealth addresses, RingCT, Bulletproofs+,
  Dandelion++).
- 30-second blocks; received coins can be spent after 10 blocks, about 5 minutes.
- Mined on ordinary CPUs with RandomOPCA, Opacra's own RandomX variant.
- 10,000,000 OPCA on a smooth curve, then 0.05 OPCA a block for ever. No premine, no ICO,
  full rewards from block 1.
- 5% of every block's new coins funds development, to a published address with a public view
  key, so anyone can check every payment it receives. Wallets never use fund coins as decoys.
- Owners can prove what they choose: payment proofs, reserve proofs and view-only wallets.
- Emergency checkpoints, signed in DNS under opacra.org and opacra.com, protect the young chain
  against an attack. Seeds, pools and exchanges follow them; home nodes warn and can opt in.

**Downloads:** Windows (64-bit) and Linux (64-bit, Ubuntu 24.04 or similar), with checksums
signed by the Opacra release key (fingerprint `D861 7219 6FEC AAB6 84F5 B3FD CB65 D212 D0B1
162B`). The Windows programs are not code-signed yet: Windows may ask you to choose "Run
anyway".
