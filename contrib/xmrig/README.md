# XMRig for Opacra solo mining

Every Opacra coinbase has two outputs: the miner's and the 5% development fund. XMRig 6.26
accepts only one coinbase output in solo (`--daemon`) mode, so it rejects Opacra templates.
Pool mining is not affected.

```bash
git clone https://github.com/xmrig/xmrig && cd xmrig && git checkout v6.26.0
git apply /path/to/opacra/contrib/xmrig/opacra-solo-mining.patch
mkdir build && cd build && cmake .. && make -j$(nproc)
./xmrig -o 127.0.0.1:29961 --daemon -a rx/0 -u Pa<your address> --coin monero
```

The patch only teaches XMRig's template parser to skip extra coinbase outputs; hashing and
block submission are unchanged.
