# External miner test: XMRig


_XMRig was tested on the build before the rename (Tacita, 2026-09-28). The proof-of-work, block format and daemon RPC are unchanged by the rename; only the coin identity differs._

After the functional test, XMRig 6.26.0 (built from source, unmodified) mined against node 0
in daemon (solo) mode with no built-in miner running:

```
./xmrig -o 127.0.0.1:31001 --daemon -u <wallet address> --coin monero -t 2
 * POOL #1      127.0.0.1:31001 coin Monero
 net      new job from 127.0.0.1:31001 diff 11790 algo rx/0 height 143 (1 tx)
 randomx  dataset ready (11841 ms)
 cpu      accepted (1/0) diff 11790 (19 ms)
 cpu      accepted (2/0) diff 11731 (13 ms)
 cpu      accepted (3/0) diff 12042 (14 ms)
 miner    speed 10s/60s/15m 683.0 n/a n/a H/s max 698.3 H/s
```

Over two runs XMRig added 18 blocks (heights 128 to 145); all three nodes accepted them and share the same tip.
`--coin monero` only selects the block format and algorithm; Opacra uses both unchanged.

## With the development fund (3 October 2026)

Since every coinbase has a second output for the 5% development fund, unmodified XMRig
6.26.0 refuses the node's block templates in solo (`--daemon`) mode:

```
net      127.0.0.1:33101 job error: "Invalid block template received from daemon."
```

With `contrib/xmrig/opacra-solo-mining.patch` (it skips the extra coinbase outputs when
parsing the template) XMRig mined against a regtest node and every block it found was
accepted, for example block 5 with outputs `[561749991, 29565788]`: the second is exactly
5% of the subsidy. Pool mining is unaffected because the pool builds the job.
