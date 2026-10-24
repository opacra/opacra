#!/usr/bin/env python3
"""A wrong DNS checkpoint must not cost any blocks (24 Oct 2026 review).

One private testnet node (fixed difficulty 1) enforces DNS checkpoints read from a test file
(OPACRA_TEST_DNS_CHECKPOINTS, re-read every 5 seconds; never used on mainnet) that stands in
for the two domains. It mines a chain that includes a real payment, mining stops, and then:

  1. a forged record at block 1: the node rolls back to the genesis block and keeps the removed
     blocks as a side chain; while the record stands it stays there; once the record is
     withdrawn (the genesis record still published) it returns to the same tip, with the
     payment confirmed at the same height, without a restart and without mining;
  2. a mistyped daily record higher up: the same;
  3. a record corrected at the same height (wrong hash replaced by the right one): the same;
  4. every record deleted (the file emptied): the node treats it as DNS being unreadable and
     keeps the last records, so it stays rolled back until the genesis record is back. This
     is why the emergency guide says never to delete the genesis record;
  5. a restart while a forged record stands: the kept blocks survive it, and withdrawing the
     record still brings the node back.

  python3 contrib/testnet/dns_withdraw_test.py [--bin DIR]   (default: the newest build)
Standard library only. Exit code 0 when every check passes.
"""
import argparse
import json
import os
import pathlib
import secrets
import signal
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rpc import Daemon, Wallet  # noqa: E402

FAILS = 0
STARTED = []


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def check(ok, what, detail=""):
    global FAILS
    log(("PASS " if ok else "FAIL ") + what + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILS += 1


def default_bin():
    found = [d for d in (HERE.parent.parent / "build" / n / "bin" for n in ("release", "portable"))
             if (d / "opacrad").exists()]
    return max(found, key=lambda d: (d / "opacrad").stat().st_mtime) if found else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=os.environ.get("BIN") or default_bin())
    args = ap.parse_args()
    BIN = pathlib.Path(args.bin)
    ver = subprocess.run([str(BIN / "opacrad"), "--version"], capture_output=True, text=True).stdout.strip()
    log(f"binaries: {BIN} | {ver}")

    D = pathlib.Path(tempfile.mkdtemp(prefix="dnsw-", dir=os.environ.get("TMPDIR")))
    records = D / "dns-records.txt"
    env = dict(os.environ, OPACRA_TEST_DNS_CHECKPOINTS=str(records))
    env.pop("HTTPS_PROXY", None); env.pop("HTTP_PROXY", None)

    def publish(*lines):
        tmp = records.with_suffix(".new")
        tmp.write_text("".join(l + "\n" for l in lines))
        tmp.replace(records)   # atomic, so the node never reads half a file

    def start_node(offline):
        # Mining needs a node that counts as synchronised: --offline, while the chain is built.
        # The checkpoint part needs the opposite (an offline node never reads DNS checkpoints),
        # so the node is restarted once, before it; a dead exclusive peer keeps it alone.
        p = subprocess.Popen([str(BIN / "opacrad"), "--testnet", "--fixed-difficulty", "1", "--data-dir", str(D / "node"),
                              "--enforce-dns-checkpointing", "--add-exclusive-node", "127.0.0.1:34199", "--no-igd",
                              "--p2p-bind-ip", "127.0.0.1", "--p2p-bind-port", "34190", "--rpc-bind-port", "34191",
                              "--zmq-rpc-bind-port", "34192", "--non-interactive", "--log-level", "0",
                              "--log-file", str(D / "node.log")] + (["--offline"] if offline else []),
                             stdout=open(D / "node.out", "a"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
        STARTED.append(p)
        return p

    node = start_node(True)
    d = Daemon(34191)
    d.wait_ready(180)
    genesis = d.rpc("get_block_header_by_height", height=0)["block_header"]["hash"]
    G = f"0:{genesis}"
    publish(G)

    (D / "w").mkdir()
    wp = subprocess.Popen([str(BIN / "opacra-wallet-rpc"), "--testnet", "--wallet-dir", str(D / "w"), "--rpc-bind-port", "34193",
                           "--disable-rpc-login", "--daemon-address", "127.0.0.1:34191", "--trusted-daemon",
                           "--non-interactive", "--log-file", str(D / "w.log")],
                          stdout=open(D / "w.out", "w"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
    STARTED.append(wp)
    w = Wallet(34193)
    w.wait_ready(120)
    w.rpc("create_wallet", filename="a", password="", language="English")
    addr = w.rpc("get_address")["address"]

    def wait(pred, secs):
        end = time.time() + secs
        while time.time() < end:
            try:
                if pred():
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def mine_to(h):
        d.other("start_mining", miner_address=addr, threads_count=1, do_background_mining=False, ignore_battery=True)
        while d.height() < h:
            time.sleep(1)
        d.other("stop_mining")
        time.sleep(2)

    # a 16-member ring needs 15 unlocked miner outputs (60-block coinbase lock, fund outputs skipped)
    mine_to(100)
    w.rpc("refresh")
    tx = w.rpc("transfer", destinations=[{"amount": 10**12, "address": addr}], priority=0)["tx_hash"]
    mine_to(d.height() + 6)
    info = d.other("get_transactions", txs_hashes=[tx])["txs"][0]
    tx_height = info.get("block_height", 0)
    check(tx_height > 0, "the payment is in a block", f"height {tx_height}")
    H0 = d.height()
    # by height: get_last_block_header answers BUSY (empty) on a node that is not synchronised,
    # which this one, alone by design, never is
    tip0 = d.rpc("get_block_header_by_height", height=H0 - 1)["block_header"]["hash"]
    node.send_signal(signal.SIGTERM)
    node.wait(timeout=120)
    node = start_node(False)
    d.wait_ready(180)
    wait(lambda: "can be read again" in (D / "node.log").read_text() or d.height() == H0, 30)
    check(d.height() == H0, "restarted without --offline, reading the test DNS records", f"height {d.height()}")
    pid0 = node.pid
    log(f"chain: {H0} blocks, tip {tip0[:16]}…, mining stopped")

    def hash_at(h):
        return d.rpc("get_block_header_by_height", height=h)["block_header"]["hash"]

    def kept_chain_len():
        chains = d.rpc("get_alternate_chains").get("chains", [])
        return max((c["length"] for c in chains), default=0)

    def back_to_full_chain(name):
        # the height can reach H0 a moment before the switch is committed, so wait for the tip too
        ok = wait(lambda: d.height() == H0 and hash_at(H0 - 1) == tip0, 90)
        check(ok, f"{name}: back on the same chain, same tip", f"height {d.height()}")
        t = d.other("get_transactions", txs_hashes=[tx])["txs"][0]
        check(t.get("block_height") == tx_height and not t.get("in_pool"),
              f"{name}: the payment is confirmed at the same height again", f"height {t.get('block_height')}")
        check(node.poll() is None and node.pid == pid0, f"{name}: the node was not restarted for it")

    # 1. a forged record at block 1
    publish(G, f"1:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 1, 60)
    check(ok, "forged record at block 1: the node rolls back to the genesis block", f"height {d.height()}")
    check(kept_chain_len() >= H0 - 1, "the removed blocks are kept as a side chain", f"side chain of {kept_chain_len()}")
    time.sleep(15)
    check(d.height() == 1, "while the record stands, the node stays rolled back", f"height {d.height()}")
    publish(G)
    back_to_full_chain("record withdrawn")

    # 2. a mistyped daily record higher up
    publish(G, f"40:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 38, 60)
    check(ok, "wrong record at block 40: the node rolls back to height 38 (2 below it)", f"height {d.height()}")
    publish(G)
    back_to_full_chain("wrong daily record withdrawn")

    # 3. a record corrected at the same height (the right hash read now, while block 30 is on the chain)
    right30 = hash_at(30)
    publish(G, f"30:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 28, 60)
    check(ok, "wrong record at block 30: rolled back to height 28", f"height {d.height()}")
    publish(G, f"30:{right30}")
    back_to_full_chain("record corrected")
    check(right30 == hash_at(30), "record corrected: block 30 is the one the corrected record names")

    # 4. every record deleted: same as DNS unreadable, the last records stay
    publish(G, f"50:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 48, 60)
    check(ok, "wrong record at block 50: rolled back to height 48", f"height {d.height()}")
    publish()
    time.sleep(20)
    check(d.height() == 48, "every record deleted: the node keeps the last records and stays rolled back",
          f"height {d.height()}")
    publish(G)
    back_to_full_chain("genesis record back")

    # 5. a restart while a forged record stands: the kept blocks survive it
    publish(G, f"1:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 1, 60)
    check(ok, "forged record at block 1 again: rolled back to the genesis block", f"height {d.height()}")
    node.send_signal(signal.SIGTERM)
    node.wait(timeout=120)
    node = start_node(False)
    d.wait_ready(180)
    pid0 = node.pid
    check(d.height() == 1 and kept_chain_len() >= H0 - 1, "after a restart the removed blocks are still kept",
          f"height {d.height()}, side chain of {kept_chain_len()}")
    publish(G)
    back_to_full_chain("withdrawn after a restart")

    log("ALL CHECKS PASSED" if FAILS == 0 else f"{FAILS} CHECK(S) FAILED")
    log(f"data: {D}")
    return FAILS


if __name__ == "__main__":
    # stopped from outside (kill, a timeout): still shut down the node and wallet it started
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    rc = 1
    try:
        rc = main()
    finally:
        for p in STARTED:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
        for p in STARTED:
            try:
                p.wait(timeout=120)
            except subprocess.TimeoutExpired:
                p.kill()
    sys.exit(1 if rc else 0)
