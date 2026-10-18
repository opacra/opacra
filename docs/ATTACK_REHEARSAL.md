# Attack and recovery rehearsal

A 51% attack rehearsed on a private network running Opacra's real mainnet rules
(v0.2.4 code plus the 17 Oct networking change), 18 October 2026. Nothing touched the
public testnet. The rehearsal must be repeated whenever consensus code changes (release
gates, road-to-mainnet plan).

## Result

| Step | Expected | Result |
|---|---|---|
| Secret chain | An attacker with most of the hash power mines a hidden chain from block 23 | Done: honest chain to block 54, secret chain to block 69, more total work |
| Detection | The seed's alert fires when the attacker releases | **Pass.** Within 2 s: "chain rewritten 32 blocks deep … at block 23", priority 5 |
| No floor in the way | An honest-looking heavier chain is accepted at any depth (side-chain difficulty floor) | **Pass.** The 32-block reorg went through |
| Checkpoint stops the attacker | An enforcing node with a checkpoint on an honest block refuses the attacker chain and blocks the peers sending it | **Pass**, on both the seed and the home node |
| Recovery, checkpoint deep below the honest tip (block 50, as the guide said) | The seed returns to the honest chain | **Fails without extra steps.** The node rolls back only 2 blocks below the checkpoint, keeps the attacker's blocks 23–48, and refuses the honest blocks as side blocks below a checkpoint. It is protected but stalled. It recovered only after winding it back to the split (`pop_blocks`) and resubmitting the saved honest blocks |
| Recovery, checkpoint on the first honest block after the split (block 23) | The node returns to the honest chain by itself | **Pass.** The home node rolled back, refused the attacker, synced the honest blocks from the seed and carried on mining honestly |
| Honest chain continues | Honest miners extend the honest chain; the attacker stays shut out | **Pass.** Seed and home node agreed through block 62 while the attacker pushed to 88 |

## Findings

1. **After an attack has landed, checkpoint the first honest block after the split**:
   the height in the alert ("at block 23"). A checkpoint deeper in the honest chain leaves
   enforcing nodes stalled on the attacker's blocks. `docs/EMERGENCY_CHECKPOINTS.md` step 2 now
   says this.
2. **The honest blocks must still exist somewhere.** After a landed attack every node
   switches chains and keeps the honest blocks only as side blocks, which are dropped when a
   node restarts. Seeds and the explorer now need `--keep-alt-blocks`, and the operator saves
   the honest blocks before anything restarts: `contrib/launch/save-side-chain save` (tested on regtest
   with a save, restart and restore that put the node back on the honest tip).
3. **A checkpoint only wins if the miners enforce it.** Home nodes read DNS checkpoints but
   do not enforce them by default, so after an attack every home miner stays on the attacker's
   chain. The seeds then hold the honest chain alone and nothing mines it (a seed with no
   honest peers refuses to mine: "BUSY"). **Decided 18 Oct:** the launchers (`start-testnet.sh`, "Start Opacra testnet") now
   enforce DNS checkpoints (`--enforce-dns-checkpointing`); the READMEs say how to opt out.
4. **Seeds block every peer that relays the attacker's chain for 24 hours**, including honest
   home nodes that simply followed it. Even after such a node enforces the checkpoint, the
   seeds keep refusing it for a day (in the rehearsal it had to be unblocked by hand).
   **Changed 18 Oct:** a peer whose blocks a checkpoint refuses is now blocked for 10 minutes
   (`OPACRA_CHECKPOINT_MISMATCH_BLOCK_SECONDS`) and not scored; tested against the rehearsal's
   attacker node (block list showed 557 s left).
5. The alert text and the side-chain floor behaved as designed; no code fault was found.
   The attacker node was eventually stopped by this workspace's 8 GB memory limit
   (`std::bad_alloc`, then the out-of-memory killer), with two full-memory miners running,
   not by an Opacra fault.

## Procedure (to repeat it)

`contrib/testnet/rehearsal_net.py` runs the nodes, each on its own loopback address so a
block hits one node only; set `OPACRA_RPC_SOURCE_IP=127.0.0.9` so control commands are not
caught by those blocks. Nodes: S = seed (enforcing, alerts captured by a local
`alerts-server`), H = home node, X = attacker.

1. Start S, H, X connected; mine about 20 blocks on S.
2. Restart X with `--offline` (it can then mine without peers) and mine on X with most of the
   hash power while S mines with less, until X has more total work and S is 12+ blocks past
   the split.
3. Save the honest blocks from S (`get_block` for every height after the split).
4. Restart X connected to S: check S reorganises and the alert fires.
5. Write a checkpoint on the first honest block after the split (`rehearsal_net.py checkpoint`)
   for S and H and restart them; check they refuse X, rejoin the honest chain and keep mining.
6. Optional: repeat step 5 with a deeper checkpoint to see the stall, and recover the seed with
   `pop_blocks` to the split plus `submit_block` of the saved honest blocks.
