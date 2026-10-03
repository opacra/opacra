# Mainnet launch checklist

Work through this in order. Anything marked **(consensus)** changes the chain identity
or rules, and must be final before the first public binaries are published.

## 0. Before writing any more code

- [ ] Final name and ticker. Search CoinGecko, CoinMarketCap, miningpoolstats.stream,
      GitHub and the trademark registers where you operate (for South Africa: CIPC)
      for conflicts. Buy the domain(s).
- [ ] Decide the legal wrapper (usually a non-profit foundation or a company that
      publishes open-source software, not one that sells coins). Take legal advice on
      your jurisdiction before launch; see the concept document for the key rules.
- [ ] Create project accounts: GitHub organisation, website, X/Twitter, Discord or
      Matrix, Reddit, BitcoinTalk.

## 1. Rename (if the name changes)

```bash
python3 contrib/coin-identity/rebrand.py --from Opacra --to NewName --ticker-from OPCA --ticker-to NEW
```

Then edit `COIN_NAME`, `COIN_TICKER` and `CRYPTONOTE_NAME` in `src/cryptonote_config.h`,
and the `HASH_KEY_MESSAGE_SIGNING` string.

## 2. Chain identity (consensus)

```bash
cd contrib/coin-identity
python3 coinid.py prefix Pa          # standard address (Opacra: 30598)
python3 coinid.py prefix Pi --integrated   # integrated (Opacra: 24839)
python3 coinid.py prefix Ps          # subaddress (Opacra: 22408)
python3 coinid.py network-id         # run 3x: mainnet, testnet, stagenet
python3 coinid.py genesis --reward 2384185791015 \
  --message "Opacra mainnet genesis | <date> | <a headline from that day's newspaper>"
# The output key is a "nothing up my sleeve" point derived from the message, so the
# genesis transaction is reproducible from the message alone and has no secret key.
# The current development genesis predates this: regenerate it for mainnet.
```

- [ ] Put the prefixes, network IDs and genesis transactions into `src/cryptonote_config.h`.
      The genesis `--reward` must stay `MONEY_SUPPLY >> EMISSION_SPEED_FACTOR_PER_BLOCK`
      (2384185791015 with the current parameters) or the genesis block is rejected.
- [ ] A newspaper headline in the genesis message proves no blocks were mined before that date.
- [ ] Set the time of the last entry in each table in `src/hardforks/hardforks.cpp` to
      the launch time (UTC epoch seconds). Wallets use it to estimate chain height.
- [ ] Build, start a node once, and read the genesis hash:
      `curl -s localhost:29961/json_rpc -d '{"jsonrpc":"2.0","id":"0","method":"get_block_header_by_height","params":{"height":0}}'`
      Add `ADD_CHECKPOINT2(0, "<genesis hash>", "0x1");` in `src/checkpoints/checkpoints.cpp`.

## 3. Network endpoints (`src/coin_network.h`)

- [ ] 3+ seed nodes on different providers and continents (2 vCPU, 4 GB RAM, 80 GB SSD;
      ~$5–10 a month each). Run `contrib/launch/seed-node-setup.sh` on each (section 5).
- [ ] Add their `ip:29960` to `ip_seed_nodes(MAINNET)`.
- [ ] Optional: a DNS seed name (e.g. `seeds.yourcoin.org`) with one A record per seed,
      DNSSEC enabled, listed in `dns_seed_domains()`.
- [ ] Optional: a Tor onion service on one seed (`tor_seed_nodes()`), see
      `docs/ANONYMITY_NETWORKS.md`.
- [ ] Leave `checkpoint_dns_domains`, `update_dns_domains` and `blocklist_dns_domains`
      empty until you control DNSSEC-signed domains for them.
- [ ] Development fund (5% of every block): create one wallet per network on an offline
      machine (`opacra-wallet-cli --generate-new-wallet devfund`, add `--testnet` for the
      testnet one), write down the seed, and put each standard address and its secret
      view key (`viewkey` command) into `DEV_FUND_ADDRESS` / `DEV_FUND_VIEW_KEY` in
      `src/cryptonote_config.h`. The view keys are published so anyone can audit the fund
      (audit wallets must scan coinbase outputs, i.e. not use `refresh-type no-coinbase`).
      The current values are development placeholders with no usable spend key.
      Changing the fund address after launch is a hard fork, so decide on a 2-of-3 multisig
      wallet before mainnet (its combined address and view key go into the config).
- [ ] Optional community fund: a mainnet address in `OPACRA_DONATION_ADDR`
      (`src/simplewallet/simplewallet.h`). Publish its view key so anyone can audit it.

## 4. Public testnet (2–4 weeks)

- [ ] Build the release candidate, run 2–3 testnet seed nodes:
      `bash seed-node-setup.sh <package> testnet` (P2P port 29970; see section 5).
- [ ] Invite miners and developers; run the block explorer and pool against testnet.
- [ ] Run `contrib/testnet/functional_test.py` on the release candidate.
- [x] Independent AI review of the consensus diff, October 2026 (`docs/REVIEW_2026-10.md`).
- [ ] Paid human audit of the changed files before mainnet (see `docs/OPACRA_SPEC.md` §5);
      the diff is a few hundred lines.
- [x] Block-size constants scaled for 30 s blocks (`docs/REVIEW_2026-10.md`, decision).
- [ ] Fix, rebuild and restart testnet if anything changes.

## 5. Seed nodes

On each Ubuntu 24.04 VPS:

```bash
scp dist/opacra-v<version>-linux-x64.tar.gz contrib/launch/{seed-node-setup.sh,opacrad.service,opacra.conf} root@SEED:
ssh root@SEED 'bash seed-node-setup.sh opacra-v<version>-linux-x64.tar.gz'            # mainnet
ssh root@SEED 'bash seed-node-setup.sh opacra-v<version>-linux-x64.tar.gz testnet'    # public testnet
```

Edit `/etc/opacra/opacra.conf` on each seed and add the other seeds as
`add-priority-node=IP:29960` (testnet: `IP:29970`). Check with `journalctl -u opacrad -f`.

## 6. Release binaries

- [ ] Today: `contrib/launch/package_release.sh` packages a portable Linux x86_64 build
      (`-DARCH=x86-64`) with SHA256SUMS. It is not bit-for-bit reproducible.
- [ ] Before mainnet: port Monero's reproducible build descriptors in `contrib/gitian`
      (they still clone monero-project/monero and name files `monero-*`) to this
      repository, for Linux x86_64/aarch64, Windows and macOS.
- [ ] Two people build independently and compare hashes.
- [ ] Publish `hashes.txt` signed with the release GPG key, and the source tag.

## 7. Infrastructure before the first block

- [ ] **Block explorer:** fork `moneroexamples/onion-monero-blockchain-explorer`, point
      its CMake at this source tree, change network name and ports. Host at
      `explorer.yourcoin.org`.
- [ ] **Mining pool:** at least one pool at launch, ideally two operators. Options:
      `jtgrassie/monero-pool` (C, lightweight) or a CryptoNote Node.js pool fork. Set
      the address prefixes and 30 s block time in the pool config.
- [ ] **Public nodes** with restricted RPC (`--rpc-restricted-bind-port`) for light wallets.
- [ ] **Wallets:** CLI and RPC wallets ship with the release. For a GUI, fork
      `monero-project/monero-gui` or Feather Wallet; for mobile, work with Cake Wallet or
      a light-wallet server (`monero-lws` fork).
- [ ] **Merchant plugin:** a BTCPay Server / WooCommerce plugin fork (the Monero plugins use
      `monero-wallet-rpc`, which `opacra-wallet-rpc` replaces with the same API).

## 8. Launch day

1. T−7 days: announce the exact launch time, the release tag, binary hashes and the
   genesis hash. State clearly that there is **no premine** and that 5% of every block
   goes to the development fund, with the fund's address and view key.
2. T−1 hour: seed nodes, explorer and pools running and synced at height 0.
3. T: announce "mining is open". The 7-day slow start keeps early blocks small, so
   there is no advantage in being first.
4. Watch the explorer and `opacrad status` on all seeds. Block times settle after about
   60 blocks (30 minutes).
5. After ~1 day: post the first hard-coded checkpoint in the next point release
   (`contrib/launch/make_checkpoint.sh <height>`).

## 9. After launch

- [ ] Add a checkpoint every few thousand blocks in each release.
- [ ] List on miningpoolstats.stream as soon as a pool is running.
- [ ] Apply to CoinGecko / CoinMarketCap once there is a market with volume.
- [ ] Network upgrades: append `{17, height, 0, time}` to the fork tables, ship binaries
      at least 4–6 weeks before the height.
