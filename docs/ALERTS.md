# Seed alerts

Each seed sends a push notification to your phone when something on the network looks
wrong. Notifications go through [ntfy](https://ntfy.sh): free, no account, an app for Android
and iOS. The public ntfy.sh server allows 250 messages a day per server, far more than the
cooldowns below can use. (ntfy.sh no longer sends e-mail without an account, which is why
alerts are push notifications.)

| Alert | When | Source |
|---|---|---|
| Chain rewritten N blocks deep | A reorganisation replaces more than 10 blocks (ordinary orphans replace 1, rarely 2). Urgent. At most one per 10 minutes unless deeper. | `reorg-notify` in opacrad |
| Blocks coming much too fast / slowly | opacrad's built-in block-rate check (a rate that should happen only once in 10 days by chance) keeps firing for 30 minutes. At most one of each per hour. | `block-rate-notify` in opacrad |
| No new block for N minutes | The height has not changed for 20 minutes (40 blocks expected). | watchdog |
| Node not answering | The node's RPC has not answered for 10 minutes. | watchdog |
| No peers connected | No peers for 15 minutes. | watchdog |
| Emergency checkpoints unreadable | The seed enforces DNS checkpoints but logged that it cannot read them. | watchdog (node log) |
| Checkpoint now enforced at block N | A new DNS checkpoint took effect: confirms step 6 of `EMERGENCY_CHECKPOINTS.md`, or warns of a change you did not make. | watchdog (node log) |
| DNS checkpoint conflict | A DNS checkpoint disagrees with one the node has; the node stops. Urgent. | watchdog (node log) |

The thresholds follow the mining security plan's risk review: alerts that cry wolf get
ignored exactly when they matter, so shallower rewrites and short spells of odd block rates
are only written to `alerts.log` (and opacrad's own log). Every threshold can be changed in
`/etc/opacra/alert.conf`.

Watchdog alerts also send one "OK again" message when the problem clears. The watchdog runs
every 5 minutes (systemd timer `opacra-alert.timer`).

On the testnet, "no new block" and "no peers" are expected when all your own miners are off,
because they are most of the hash power.

## Install on a seed

From the machine with the repository (PC, Opacra Ubuntu tab):

```
scp ~/opacra/contrib/launch/{opacra-alert,install-alerts.sh,opacra-alert.service,opacra-alert.timer} opacra-seed1:/root/
ssh opacra-seed1 'bash /root/install-alerts.sh testnet'
```

It prints a topic name. On the phone: install **ntfy**, tap **+**, type the topic exactly,
leave the server as ntfy.sh, Subscribe. Then on the seed: `opacra-alert test`.

A second seed joins the same feed with `bash install-alerts.sh testnet <topic>`. For mainnet
use `mainnet` (it reads RPC port 29961). Anyone who knows the topic can read the alerts (public
chain data) or send fake ones, so share it only with seed operators. To change it, edit
`/etc/opacra/alert.conf` and resubscribe.

## Files on the seed

| Path | What |
|---|---|
| `/usr/local/bin/opacra-alert` | The script (Python 3, standard library only) |
| `/etc/opacra/alert.conf` | Topic, thresholds, network (root:opacra 640) |
| `/etc/opacra/opacra.conf` | Gets `reorg-notify=` and `block-rate-notify=` lines |
| `/var/lib/opacra/alert/alerts.log` | Every event, including small reorgs that were not sent |
| `opacra-alert status` | What the watchdog sees now |

## Tested (11 Oct 2026)

Two regtest nodes mined separate chains and were then connected: the node's `reorg-notify`
ran the script (opacrad starts it with an empty environment, as root or as opacra), which
posted "chain rewritten" to a local stand-in for ntfy. Every watchdog alert and
its recovery message, the 11-block and 30-minute thresholds, the cooldowns, the root-to-opacra switch, the notify lines read from a
config file, and two runs of the installer (same result, one set of lines) were checked the
same way.
