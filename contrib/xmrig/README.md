# XMRig for Opacra

Opacra mines **RandomOPCA**: RandomX with Opacra's own salt (`"RandomOPCA\x01"`, see
`external/randomx/OPACRA.md`). Stock XMRig doesn't know it, so Opacra publishes a patched
build. `opacra-xmrig.patch` (against XMRig v6.26.0) does two things:

1. Adds the algorithm `rx/opca` (RandomX with Opacra's salt; nothing else changed) and
   the coin `opacra` / `OPCA`.
2. Lets solo (`--daemon`) mode accept Opacra block templates, whose coinbase has two
   outputs (the miner's and the 5% development fund). Stock XMRig accepts only one.

```bash
git clone https://github.com/xmrig/xmrig && cd xmrig && git checkout v6.26.0
git apply /path/to/opacra/contrib/xmrig/opacra-xmrig.patch
mkdir build && cd build && cmake .. && make -j$(nproc)

# solo, against your own node (testnet RPC port 29971, mainnet 29961)
./xmrig -o 127.0.0.1:29971 --daemon -a rx/opca --coin opacra -u Te<your testnet address>
```

Hashing, block submission and everything else in XMRig are unchanged. The Opacra
release script signs the built binaries' checksums with the release key; download
miners only from opacra.org.
