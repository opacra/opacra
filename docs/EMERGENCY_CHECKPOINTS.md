# Emergency checkpoints (DNS)

An emergency checkpoint is a public statement from the project that a given block is
the real one: "block H has hash X". Nodes read it from DNS within about five minutes,
with no software release.

| Network | Names (both must publish exactly the same records) |
|---|---|
| Mainnet | `checkpoints.opacra.org`, `checkpoints.opacra.com` |
| Testnet | `testpoints.opacra.org`, `testpoints.opacra.com` |

Both zones are DNSSEC-signed and held in the Opacra-only registrar account (2FA). A node
uses the records only if **both** names answer, both answers pass DNSSEC validation, and
both hold the same set of records. One name alone, or two names that differ, are ignored.
That protects against a single hijacked or mistyped zone.

## Who enforces

- **Ordinary nodes** read the checkpoints every 5 minutes and log a warning if their chain
  disagrees. They are not forced onto a chain by the project.
- **Seeds, exchanges and pools** run with `enforce-dns-checkpointing=1` (in
  `contrib/launch/opacra.conf`). They refuse any reorganisation at or below the newest
  checkpoint, and if their own chain disagrees they roll back to before it and follow the
  chain that matches. This protects the places where real money moves, and stops the seeds
  from spreading an attacker's rewrite to new nodes.

Without enforcement the project can't steer the chain; with it, a few enforcing nodes
hold the honest chain together during an attack. The same model has run on Monero for
years (MoneroPulse).

## The record

A TXT record whose value is `height:hash`, for example:

```
2000:9d484e6d15883cb1241d91ea6a23e94be03003ad373a9a03ac9e3c1000aa36f2
```

There is always one standing record (an older block). Nodes then see a healthy answer in
normal times, and an emergency only means adding one more record.

**A new chain starts with its genesis as the standing record** (`0:<genesis hash>`, printed
by `make_genesis.py verify`), published on both domains on launch day in place of any older
record. Without any record, every enforcing node (seeds, and home nodes started by the
launchers) logs a red "none could be read" warning and the seeds send an alert. The genesis
is safe to publish: every node already has it built in.

## Keep it ready (before you ever need it)

Emergency checkpoints only help if the seeds can read them. Check after every release, every
seed install, and once a month:

```
ssh opacra-seed1 'grep -E "DNS checkpoint enforced|none could be read|can be read again" /var/lib/opacra/opacra.log | tail -3'
```

The newest line must be `DNS checkpoint enforced: block 2000 = …` (or "can be read again").
If it says "none could be read", fix that first: the phone alert "emergency checkpoints
unreadable" means the same thing. Known causes:

- **The root DNS key changed.** Nodes validate DNSSEC with built-in root keys. The root key
  changed on 11 October 2026 (KSK-2024, tag 38696) and nodes before v0.2.4 could no longer
  validate anything. Test on the seed:
  `unbound-host -f /tmp/new.ds -t TXT testpoints.opacra.org` with the current root keys from
  `/usr/share/dns/root.ds` (package `dns-root-data`). "validation failure … while building
  chain of trust" means the node needs the new key in `src/common/dns_utils.cpp`.
- **The resolver does not pass DNSSEC data.** The node then falls back to Quad9/Cloudflare
  over TCP. The testnet seed also sets `DNS_PUBLIC=tcp://1.1.1.1` in
  `/etc/systemd/system/opacrad.service.d/dns.conf`.
- **The two domains disagree, or a record is missing:** `dig +short TXT testpoints.opacra.org`
  and `.com` must print the same lines.

## Daily checkpoints (first 2-4 weeks of mainnet)

One routine checkpoint a day caps how much history an attack could quietly rewrite while the
network is small. About 5 minutes, from the PC (Opacra Ubuntu tab):

```
cd ~/opacra && contrib/launch/daily-checkpoint --mainnet --node local:127.0.0.1:29961 --node ssh:opacra-seed1:127.0.0.1:29961
```

It picks a block about 6 hours deep, reads its hash from both nodes and refuses if they
disagree or are more than 10 blocks apart. It prints the record, the two `dig` checks and a line
for the website's checkpoint log. Then follow steps 4-6 of the emergency checklist below:
both domains, TTL 1 min, check with dig, and confirm the seed says `DNS checkpoint enforced`.
Keep the earlier daily records; remove them all at once after a release hard-codes them. Stop
the daily routine at that point (white paper: "Protecting a young chain"). Rehearse it on the
testnet first (`--node local:127.0.0.1:29971 --node ssh:opacra-seed1:127.0.0.1:29971`, no `--mainnet`).

## Emergency checklist

Follow it in order, even when it seems obvious. A wrong checkpoint is worse than none:
enforcing nodes would stall on a block that never comes.

1. **Confirm the attack.** A "chain rewritten" phone alert (`docs/ALERTS.md`), or the explorer and the seed showing
   blocks being rewritten. Note the height where the chains split.
2. **Choose the block.** Never a height at or below a hard-coded checkpoint: a different
   hash there shuts enforcing nodes down.
   - **The attack has already landed** (the alert says the seed switched chains "at block H"):
     checkpoint the **first honest block after the split**, at height H. Your nodes are
     now on the attacker's chain, so take its hash from the honest blocks you saved, or from
     the explorer's history, never from a node's current chain. A deeper honest block does
     not work: enforcing nodes then roll back only 2 blocks below it, keep the attacker's
     earlier blocks, and stall (attack rehearsal, 18 Oct 2026, `docs/ATTACK_REHEARSAL.md`).
   - **Before it lands** (you see an attack building but your nodes are still on the honest
     chain): the newest block both your nodes agree on, at least 5 blocks below the tip.
   - **Save the honest blocks first.** After a switch, nodes keep them only as side blocks,
     and drop those when they restart unless they run with `--keep-alt-blocks`. Before
     restarting anything, on the seed: `contrib/launch/save-side-chain save` (in the
     package: `launch-kit/save-side-chain`). It saves them and prints the checkpoint to publish
     (`H:hash`, the first block after the split). It also saves the 10 blocks both chains share
     below the split, which a node needs after the checkpoint rolls it back. A node left stalled on the attacker's blocks
     recovers with: restart it with `--offline`, `save-side-chain restore honest-blocks.json`,
     then restart it normally.
3. **Read its hash from two separate nodes, and the explorer.** All three must match
   character for character.
   - PC (Opacra Ubuntu tab):
     `cd ~/opacra && RPC=127.0.0.1:29971 contrib/launch/make_checkpoint.sh H`
     (testnet; mainnet RPC is 127.0.0.1:29961)
   - Seed: `curl -s http://127.0.0.1:29971/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_block_header_by_height","params":{"height":H}}' | grep '"hash"'`
   - Explorer: https://explorer.opacra.org/block/H
4. **Publish under both domains**, in Namecheap (opacraproject account), Advanced DNS →
   Add New Record:
   - Type **TXT Record**, Host **testpoints** (mainnet: **checkpoints**), Value
     `H:hash`, TTL **1 min**
   - Same record on opacra.org and opacra.com. Copy and paste the value; never retype it.
5. **Check DNS.** From the PC: `dig +short TXT testpoints.opacra.org` and
   `dig +short TXT testpoints.opacra.com` must print the same lines.
6. **Check the seed** within about 5 minutes (the phone also gets "checkpoint now enforced at
   block H" from the seed's watchdog):
   `journalctl -u opacrad --since "10 min ago" | grep "DNS checkpoint"` shows
   `DNS checkpoint enforced: block H = …`.
7. **Tell those who need to know**: exchanges, pools, the website and announcement
   channels. Give the height and hash, and ask them to wait for more confirmations.
8. **Afterwards**: build the checkpoint into the next release (`ADD_CHECKPOINT2` in
   `src/checkpoints/checkpoints.cpp`, values from `make_checkpoint.sh`). Once that release
   is widely run, remove the emergency record from both domains at the same time, keeping
   the standing record.

## Correcting or removing a checkpoint

Enforcing nodes keep every DNS checkpoint they have read until they restart, so:

- **To remove one**, delete the record from both domains, then restart the enforcing
  nodes (seed: `systemctl restart opacrad`). Until they restart they keep enforcing it.
  The seed's phone alert says "checkpoint at block H removed from DNS" when this happens.
  (Drill on 15 Oct 2026, v0.2.4: block 13900 published on both domains, enforced within 5
  minutes, removed, seed restarted; every step alerted.)
- **Never change the hash of a published height in place.** Enforcing nodes treat the new
  hash as a conflict and shut down (and restart in a loop under systemd) until both domains
  show one consistent value. To correct a wrong checkpoint, remove it from both domains,
  restart the enforcing nodes, then publish the right block at a different height.
- While you edit, the two domains differ for a minute or two. Nodes log "no majority of DNS
  TXT records matched" and ignore both until they agree again; that is expected.
- An enforcing node that cannot read any checkpoint (DNS blocked, DNSSEC not validated,
  records missing) logs a red warning once, and "DNS checkpoints can be read again" when it
  recovers. Check for that warning after every seed install.

## Rules

- Change both domains together, with the same values. While they differ, every node
  ignores them, which is the safe failure.
- Never publish a height at or below a hard-coded checkpoint with a different hash.
- The registrar account controls this power: two-factor login, the project email only,
  backup codes offline. Treat it like the release signing key. Both zones are currently in
  one account; moving opacra.com to a second registrar would remove that single point of
  failure. Decided 18 Oct 2026: one account, locked down (long unique password, support PIN,
  domain lock, the project email secured with authenticator 2FA and a recovery phrase).
- Rehearse on the testnet before mainnet (mining security plan, Phase 2).
