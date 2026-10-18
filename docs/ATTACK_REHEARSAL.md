# Attack and recovery rehearsal

A 51% attack rehearsed on a private network running Opacra's real mainnet rules
(v0.2.4 code plus the 17 Oct networking change), 18 October 2026. Nothing touched the
public testnet. The rehearsal must be repeated whenever consensus code changes (release
gates, road-to-mainnet plan).

## Repeat on the release-candidate code (18 Oct 2026, afternoon)

Repeated after the slow start was removed and the 10-minute checkpoint block and enforcing
launchers were added (release gate: consensus code changed). Same three nodes, mainnet rules,
the corrected procedure below.

| Step | Result |
|---|---|
| Secret chain | Split at block 23; honest chain to 38, attacker to 56 with 51% more total work |
| Detection | **Pass.** Alert within seconds: "chain rewritten 15 blocks deep … at block 23", priority 5 |
| Save the honest blocks | **Pass**, `save-side-chain save` printed `23:8687af6e…`, the checkpoint to publish |
| Checkpoint on the first honest block after the split | **Pass.** Seed and home node rolled back, refused the attacker's blocks |
| Seed recovery with `save-side-chain restore` | **Failed first time, tool fixed.** The checkpoint rolls a node back 2 blocks *below* the split, and the saved file held only blocks from the split up, so blocks 21–22 were missing and the honest blocks were refused as orphans (the RPC still answered "OK"). `save` now also keeps the 10 shared blocks below the split and `restore` submits the missing ones first, then checks every block actually became the tip. With the fixed tool the seed returned to the honest tip (38, `f1b0bc06…`) |
| 10-minute block | **Pass.** The seed blocked the attacker and the home node (which was still on the attacker's chain) for 10 minutes, not a day. The home node, now enforcing, reconnected on its own after the block expired, synced the honest chain and mined on. The attacker was blocked again every time it reconnected |
| Honest chain continues | **Pass.** Seed and home node agreed through block 44 while the attacker pushed to 71 with more work |

Notes: a node started with `--add-exclusive-node` refuses connections from peers not on its
list (the seed had to list the attacker to receive its chain); on a shared loopback the seed
also blocked 127.0.0.1, the address the other nodes connect from. Both are artefacts of the
private network, not of Opacra. The workspace restarted once during the run; every node's data
survived and the run carried on from there.

## Result (first run, morning)

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
3. After step 4, save the honest blocks from S: `contrib/launch/save-side-chain save`
   (side blocks by hash, plus the 10 shared blocks below the split).
4. Restart X connected to S: check S reorganises and the alert fires.
5. Write a checkpoint on the first honest block after the split (`rehearsal_net.py checkpoint`)
   for S and H and restart them; check they refuse X, rejoin the honest chain and keep mining.
   Recover a node stuck on the attacker's blocks: restart it with `--offline`,
   `save-side-chain restore`, restart it normally.
6. Check the block lasts 10 minutes (`get_bans` on S) and that H reconnects by itself after it.
