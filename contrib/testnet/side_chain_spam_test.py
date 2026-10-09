#!/usr/bin/env python3
"""Side-chain spam check (security audit, October 2026), on a throwaway regtest node with
real difficulty (no --fixed-difficulty, so the side-chain difficulty floor is active).

Before v0.1.3 block 1's difficulty was 1 (LWMA has no history) and the floor never
applied to side blocks below height 122, so a side block at height 1 forking from
genesis cost one hash, for as long as the chain exists. Anyone could send any node
unlimited free side blocks; each one was checked with RandomX and written to disk.

From v0.1.3 block 1 costs the startup guess (10,000) on every network but the public
testnet (whose block 1 already exists), and side blocks at any height are held to the
floor once the main chain is past its first hour.

The test builds a short main chain with real proof of work, then submits 20 side blocks
at height 1 built on genesis without doing any work for them.
v0.1.2: all 20 are stored (template difficulty 1). v0.1.3: none (template difficulty 10,000).

Usage:  MONERO_RANDOMX_FULL_MEM=1 BIN=build/portable/bin python3 contrib/testnet/side_chain_spam_test.py
(needs about 2.5 GB of memory with MONERO_RANDOMX_FULL_MEM; without it mining is slow).
Exit 0 when no free side block is stored.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import block_rules_test as brt  # noqa: E402  (reuses its node and block helpers)

MAIN_BLOCKS = int(os.environ.get("MAIN_BLOCKS", "12"))
SPAM = 20


def start_real_difficulty_node(name, p2p):
    d = brt.DATA / name
    d.mkdir(parents=True, exist_ok=True)
    args = [str(brt.BIN / "opacrad"), "--regtest", "--offline", "--non-interactive",
            "--data-dir", str(d), "--log-file", str(d / "opacra.log"), "--log-level", "1",
            "--p2p-bind-ip", "127.0.0.1", "--p2p-bind-port", str(p2p),
            "--rpc-bind-ip", "127.0.0.1", "--rpc-bind-port", str(p2p + 1), "--zmq-rpc-bind-port", str(p2p + 2),
            "--no-igd", "--disable-dns-checkpoints", "--check-updates", "disabled"]
    p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    brt.procs.append(p)
    node = brt.Daemon(p2p + 1)
    node.wait_ready(180)
    return node, p


def main():
    node, p = start_real_difficulty_node("spam", 33200)
    t0 = time.time()
    while node.height() < MAIN_BLOCKS + 1:   # one at a time: each takes ~10,000 RandomX hashes (reuses an existing DATA chain)
        brt._post(node.base + "/json_rpc", {"jsonrpc": "2.0", "id": "0", "method": "generateblocks",
                  "params": {"amount_of_blocks": 1, "wallet_address": brt.ADDR, "starting_nonce": 0}}, timeout=3600)
        print(f"  height {node.height()}  ({time.time() - t0:.0f} s)", flush=True)
    main_height = node.height()
    print(f"main chain: {main_height} blocks (real proof of work, {time.time() - t0:.0f} s)", flush=True)
    genesis = brt.header_hash(node, 0)
    before = len(brt.alt_chains(node))
    stored = 0
    for i in range(SPAM):
        t = brt.template(node, genesis)
        ok, info = brt.submit(node, brt.with_timestamp(t["blocktemplate_blob"], int(time.time()), 1000 + i))
        stored += 1 if ok else 0
    chains = len(brt.alt_chains(node)) - before
    print(f"free side blocks at height 1 (difficulty {t['difficulty']}): {stored}/{SPAM} accepted, {chains} new side chains stored", flush=True)
    brt.check(f"free side blocks at height 1 are refused once the main chain has {main_height} blocks",
              stored == 0 and chains == 0, f"{stored} accepted, {chains} side chains")
    brt.stop(p)
    return 0 if all(r["ok"] for r in brt.results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        for proc in brt.procs:
            if proc.poll() is None:
                proc.kill()
