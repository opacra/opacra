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
