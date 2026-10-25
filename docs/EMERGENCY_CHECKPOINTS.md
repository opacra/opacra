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

- **Nodes started by hand** read the checkpoints every 5 minutes and log a warning if their
  chain disagrees. They are not forced onto a chain by the project.
- **Home nodes started by the launchers** only warn, and print at startup how to switch
  enforcement on: `ENFORCE_CHECKPOINTS=1 ./start-testnet.sh` on Linux, or
  `set ENFORCE_CHECKPOINTS=1` in the Windows start file. During an attack the announcement
  asks miners to do that (checklist step 7). Decided 25 Oct 2026 for launch: while both
  domains sit in one registrar account, whoever took that account could publish a matching
  forged record and nobody could withdraw it until the account is recovered, which can take
  days. If every home miner enforced, all of them would stall for that long and only the
  miners not enforcing, the attacker among them, would keep producing blocks.
  **Planned:** enforcement on by default in the first release after opacra.com moves to a
  second registrar, once three things are done: the serial-number check below has shipped
  and been reviewed; the two domains are at different registrars with different people
  holding the logins; and a testnet drill has passed (a record forged in one zone only is
  ignored; a genuine record in both is followed).
- **Seeds, exchanges and pools** run with `enforce-dns-checkpointing=1` (in
  `contrib/launch/opacra.conf`). They refuse any reorganisation at or below the newest
  checkpoint, and if their own chain disagrees they roll back to before it and follow the
  chain that matches. From v0.2.6 the blocks they remove are kept as a side chain, also
  across a restart: if the record was wrong and is withdrawn or corrected, they return to
  those blocks within about 5 minutes, with nothing lost (see "Correcting or removing a
  checkpoint"). This protects the places where real money moves, and stops the seeds
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

**Every set of records also carries a serial number**, as one more TXT record under the
same name: `serial:<number>`, for example `serial:1793217600`. Rules:

- The number is the current time from `date +%s` on the PC, copied exactly: digits only,
  never more than a day ahead.
- **Every change** (adding, correcting or removing any record) gets a new, higher serial,
  the same value on both domains.
- **Change the serial last**, after the other records on that domain. While you edit, the
  registrar signs every in-between state of the zone. An in-between answer with the *new*
  serial but without your change could be saved and replayed later, and nodes would take it
  for the final set. With the serial changed last, every in-between state carries the old
  serial and different records, and nodes refuse it.
- Exactly one `serial:` record per domain. Never delete it.

Nodes from v0.2.6 remember the highest serial they have seen, and the records that came
with it, also across restarts and also when they only warn. They refuse any answer:
- with a lower serial, or with none once they have seen one;
- with the same serial but different records;
- with an unusable serial: not a plain number (`-1` included), more than one, or more
  than a day in the future.

Each release also builds in a minimum serial, so a new install refuses answers from
before the release. An enforcing node restarts with the last set it accepted, so an
emergency checkpoint stays in force across a restart even if DNS can't be read then.

DNSSEC proves an answer was signed, not that it is current: an older signed answer stays
valid for days, so without the serial someone could replay the answer from before an
emergency record to one node and lift the checkpoint there. A refused answer logs
`DNS checkpoint records refused: serial … is …` with the reason, and sends the seed's phone
alert "DNS checkpoint records refused". If you see that while editing, finish both domains
and change the serial last. If you aren't editing, check the registrar account at once,
then that node's network and resolver: someone may be replaying old answers.

**A new chain starts with its genesis as the standing record** (`0:<genesis hash>`, printed
by `make_genesis.py verify`), published on both domains on launch day in place of any older
record. Without any record, every enforcing node (the seeds, pools, exchanges) logs a red "none could be read" warning and the seeds send an alert. Publish it
at the launch minute, not before: until mining opens the genesis is kept private, because
anyone who has it could start mining in secret. From then on every node has it
built in.

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
cd ~/opacra && contrib/launch/daily-checkpoint --network mainnet --node ssh:opacra-seed1:127.0.0.1:29961 --node ssh:opacra-seed2:127.0.0.1:29961
```

It checks both nodes are on the network named, picks a block about 6 hours deep, reads its hash
from both nodes and refuses if they disagree or are more than 10 blocks apart. It prints the record, the two `dig` checks and a line
for the website's checkpoint log. Then follow steps 4-6 of the emergency checklist below:
both domains, TTL 1 min, check with dig, and confirm the seed says `DNS checkpoint enforced`.
Keep the earlier daily records; remove them all at once after a release hard-codes them. Stop
the daily routine at that point (white paper: "Protecting a young chain"). Rehearse it on the
testnet first (`--network testnet --node ssh:opacra-seed1:127.0.0.1:29971 --node ssh:opacra-seed2:127.0.0.1:29971`).

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
     restarting anything, on the seed: `contrib/launch/save-side-chain save --network mainnet`
     (testnet: `--network testnet`; in the package: `launch-kit/save-side-chain`). It checks the
     node is on that network, saves the blocks and prints the checkpoint to publish
     (`H:hash`, the first block after the split) with the TXT record name for that network. It also saves the 10 blocks both chains share
     below the split, which a node needs after the checkpoint rolls it back. A node left stalled on the attacker's blocks
     recovers with: restart it with `--offline`,
     `save-side-chain restore honest-blocks.json --network mainnet`, then restart it normally.
3. **Read its hash from two separate nodes, and the explorer.** All three must match
   character for character, and all must be on the network you publish for (mainnet:
   record `checkpoints`, port 29961; testnet: record `testpoints`, port 29971).
   - PC (Opacra Ubuntu tab), mainnet:
     `cd ~/opacra && NETWORK=mainnet RPC=127.0.0.1:29961 contrib/launch/make_checkpoint.sh H`
     (testnet: `NETWORK=testnet RPC=127.0.0.1:29971`). Its first line names the network; it
     stops if the node is on another one.
   - Seed, mainnet: `curl -s http://127.0.0.1:29961/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_block_header_by_height","params":{"height":H}}' | grep '"hash"'`
     (testnet: port 29971)
   - Explorer: https://explorer.opacra.org/block/H
4. **Publish under both domains**, in Namecheap (opacraproject account), Advanced DNS →
   Add New Record:
   - Type **TXT Record**, Host **testpoints** (mainnet: **checkpoints**), Value
     `H:hash`, TTL **1 min**
   - **Then, last**, in the same zone, change the `serial:` record to a new, higher value:
     `date +%s` on the PC, digits only. Without a higher serial, nodes that already saw the
     old one refuse the new set; changed first, an in-between state could be replayed.
   - Same records on opacra.org and opacra.com. Copy and paste the values; never retype them.
5. **Check DNS.** From the PC: `dig +short TXT testpoints.opacra.org` and
   `dig +short TXT testpoints.opacra.com` must print the same lines.
6. **Check the seed** within about 5 minutes (the phone also gets "checkpoint now enforced at
   block H" from the seed's watchdog):
   `journalctl -u opacrad-mainnet --since "10 min ago" | grep "DNS checkpoint"` (testnet:
   `-u opacrad`) shows
   `DNS checkpoint enforced: block H = …`.
7. **Tell those who need to know**: exchanges, pools, the website and announcement
   channels. Give the height and hash, and ask them to wait for more confirmations. Ask
   home miners to **turn on checkpoint enforcement** and restart, using this text:

   > Opacra emergency checkpoint at block H. Miners: turn on checkpoint enforcement and
   > restart, so your miner follows the honest chain. Windows: right-click "Start Opacra
   > testnet", Edit, change `set ENFORCE_CHECKPOINTS=0` to `set ENFORCE_CHECKPOINTS=1`,
   > save, start it again. Linux: `ENFORCE_CHECKPOINTS=1 ./start-testnet.sh`. Exchanges and
   > pools: wait for more confirmations. Every checkpoint is listed on opacra.org.

8. **Afterwards**: build the checkpoint into the next release (`ADD_CHECKPOINT2` in
   `src/checkpoints/checkpoints.cpp`, values from `make_checkpoint.sh`). Once that release
   is widely run, and **only once the seeds' main chain is heavier than any side chain they
   keep**, remove the emergency record from both domains at the same time (with a new,
   higher serial), keeping the standing record. Check on each seed with
   `curl -s http://127.0.0.1:29961/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_alternate_chains"}'`
   (testnet: port 29971): every chain's `difficulty` must be below the main chain's
   `cumulative_difficulty` from `get_info`. Nodes that haven't upgraded still keep the
   attacker's removed blocks while they are heavier, and would return to them if the record
   went away too early.

## Correcting or removing a checkpoint

From v0.2.6 an enforcing node follows DNS as it is at each read (every 5 minutes): the DNS
checkpoints are a set of their own that each successful read replaces (24 Oct 2026 audit).

- **Every change needs a new, higher `serial:`** on both domains, changed last (see "The
  record"). A set published with an old serial is refused by every node that has seen a
  newer one.
- **To remove one**, delete that record from both domains. Within about 5 minutes the nodes
  log `DNS checkpoint withdrawn: block H … is no longer enforced`, and the seed's phone alert
  says "checkpoint at block H removed from DNS". No restart is needed. **Never delete the
  genesis record** (`0:<genesis hash>`), and never empty the zone: if **no** record can be
  read, nodes keep the last set they read (a DNS outage must not lift a checkpoint during an
  attack), so an empty zone withdraws nothing, and a wrong record would stay in force.
- **A wrong record costs no blocks** (from v0.2.6). An enforcing node whose chain fails it
  rolls back below it, as before, but keeps the removed blocks as a side chain, and logs
  `Rolled back to height … The N removed block(s) are kept as a side chain`. Once the record
  is withdrawn or corrected, the node logs `Returning to a kept side chain of N block(s)` and
  is back on the same tip within about 5 minutes, with its payments confirmed at the same
  heights, without a restart and without anyone mining. While a wrong record at height H
  stands, an enforcing node can still add the two blocks below it (H−2 and H−1) and nothing
  at or above H, so act within minutes: check the record against two nodes and the explorer,
  then delete or correct it on both domains. If one of those two blocks contains a payment
  that conflicts with one in the kept blocks, the kept chain fails its check on the way back
  and the node fetches the honest blocks from its peers instead. (Rehearsed with
  `contrib/testnet/dns_withdraw_test.py`: a forged record at block 1, a wrong daily record,
  a corrected record, an emptied zone, a restart, and a replayed older answer.) Older nodes
  deleted those blocks for good; run v0.2.6 or later wherever checkpoints are enforced.
- **To correct one**, change its value on both domains. Nodes log `DNS checkpoint changed:
  block H was …, now …` and enforce the new hash. (Before v0.2.6 this shut nodes down: run
  only v0.2.6 or later on seeds.)
- **A DNS record that contradicts a checkpoint built into the node** (or its
  checkpoints.json) makes the node ignore all DNS checkpoints and keep running, with a red
  log line and the phone alert "DNS checkpoint conflict, DNS ignored". If you did not just
  publish it, someone may have changed the records: check the registrar account at once.
- While you edit, the two domains differ for a minute or two. Nodes log "no majority of DNS
  TXT records matched" and ignore both until they agree again; that is expected.
- An enforcing node that cannot read any checkpoint (DNS blocked, DNSSEC not validated,
  records missing) logs a red warning once, and "DNS checkpoints can be read again" when it
  recovers. Check for that warning after every seed install.
- Nodes older than v0.2.6 keep every record they ever read until they restart, and stop on a
  corrected record. Upgrade seeds, pools and exchanges before relying on corrections.

## A node stuck after a split

A node can end up stuck on its own side of a split: for example one that was cut off from
honest peers and fed an attacker's blocks, or one that a checkpoint rolled back only partly
(the checkpoint was higher than the first block after the split). A daily or emergency
checkpoint **above** the split does not free it: the node rolls back 2 blocks below the
checkpoint, keeps its wrong blocks below that, and waits. Two ways out:

- **One node:** in its console (Windows: the node window; Linux: `/opt/opacra/opacrad
  --rpc-bind-port 29961 pop_blocks N`, testnet port 29971), remove the blocks above the split
  with `pop_blocks N`, where N is the node's height minus the split height. The node then
  downloads the honest chain from its peers. Check that it has honest peers first
  (`print_cn`); if not, add a seed with `--add-priority-node`.
- **Many nodes:** a checkpoint on the **first honest block after the split** (checklist step 2),
  which every enforcing node follows on its own.

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
