#!/usr/bin/env python3
"""A node whose clock steps back must keep working (25 Oct 2026 review).

One private testnet node runs with its clock shifted by fake_time_offset.so, whose offset file
lets the test step the running node's clock back, as an NTP correction does:

  1. two payments sit in the pool, sent 20 seconds apart; the clock steps back 10 seconds, so
     the newer one now looks received in the future; one call to get_transaction_pool_stats
     must answer with sane numbers, and the node must still be running (before the fix, Monero's
     histogram code wrote far past the end of its table and the node died);
  2. DNS checkpoint refreshes keep running after the clock steps back 2 minutes: a newer set of
     records published right after the step is taken within seconds, not once the clock has
     caught up (the saved serial in dns_checkpoint_serial shows it).

  python3 contrib/testnet/clock_step_test.py [--bin DIR]   (default: the newest build)
Standard library only. Exit code 0 when every check passes.
"""
import argparse
import os
import pathlib
import signal
import socket
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rpc import Daemon, Wallet  # noqa: E402

FAILS = 0
STARTED = []
PORTS = (34290, 34291, 34292, 34293)


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

    for port in PORTS:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                log(f"port {port} is in use (a node left from an earlier run?); stop it first")
                return 1

    D = pathlib.Path(tempfile.mkdtemp(prefix="clock-", dir=os.environ.get("TMPDIR")))
    records = D / "dns-records.txt"
    offset = D / "clock-offset"
    offset.write_text("0\n")
    shim = D / "fake_time_offset.so"
    subprocess.check_call(["gcc", "-shared", "-fPIC", "-O2", "-o", str(shim), str(HERE / "fake_time_offset.c")])
    env = dict(os.environ, OPACRA_TEST_DNS_CHECKPOINTS=str(records))
    env.pop("HTTPS_PROXY", None); env.pop("HTTP_PROXY", None)
    node_env = dict(env, LD_PRELOAD=str(shim), FAKE_TIME_OFFSET_FILE=str(offset))

    def step_clock(seconds):
        tmp = offset.with_suffix(".new")
        tmp.write_text(f"{seconds}\n")
        tmp.replace(offset)
        time.sleep(2.5)            # the shim re-reads the file once a second

    serial = [int(time.time())]

    def publish(*lines):
        serial[0] += 1
        tmp = records.with_suffix(".new")
        tmp.write_text("".join(l + "\n" for l in (f"serial:{serial[0]}",) + lines))
        tmp.replace(records)
        return serial[0]

    def start_node(offline):
        p = subprocess.Popen([str(BIN / "opacrad"), "--testnet", "--fixed-difficulty", "1", "--data-dir", str(D / "node"),
                              "--enforce-dns-checkpointing", "--add-exclusive-node", "127.0.0.1:34299", "--no-igd",
                              # a new wallet asks for blocks from height 1, which fails until the
                              # first block is mined (about 40 s with RandomX); after 3 failures
                              # the node would ban 127.0.0.1, this test's own RPC client included
                              "--disable-rpc-ban",
                              "--p2p-bind-ip", "127.0.0.1", "--p2p-bind-port", str(PORTS[0]),
                              "--rpc-bind-port", str(PORTS[1]), "--zmq-rpc-bind-port", str(PORTS[2]),
                              "--non-interactive", "--log-level", "0", "--log-file", str(D / "node.log")]
                             + (["--offline"] if offline else []),
                             stdout=open(D / "node.out", "a"), stderr=subprocess.STDOUT,
                             env=node_env, start_new_session=True)
        STARTED.append(p)
        return p

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

    node = start_node(True)
    d = Daemon(PORTS[1])
    d.wait_ready(180)
    G = "0:" + d.rpc("get_block_header_by_height", height=0)["block_header"]["hash"]

    (D / "w").mkdir()
    wp = subprocess.Popen([str(BIN / "opacra-wallet-rpc"), "--testnet", "--wallet-dir", str(D / "w"),
                           "--rpc-bind-port", str(PORTS[3]), "--disable-rpc-login",
                           "--daemon-address", f"127.0.0.1:{PORTS[1]}", "--trusted-daemon",
                           "--non-interactive", "--log-file", str(D / "w.log")],
                          stdout=open(D / "w.out", "w"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
    STARTED.append(wp)
    w = Wallet(PORTS[3])
    w.wait_ready(120)
    w.rpc("create_wallet", filename="a", password="", language="English")
    addr = w.rpc("get_address")["address"]

    def mine_to(h):
        d.other("start_mining", miner_address=addr, threads_count=1, do_background_mining=False, ignore_battery=True)
        while d.height() < h:
            time.sleep(1)
        d.other("stop_mining")
        time.sleep(2)

    # a 16-member ring needs 15 unlocked miner outputs (60-block coinbase lock)
    mine_to(100)
    w.rpc("refresh")

    # 1. pool statistics with a payment "received in the future"
    tx1 = w.rpc("transfer", destinations=[{"amount": 10**12, "address": addr}], priority=0)["tx_hash"]
    time.sleep(20)
    tx2 = w.rpc("transfer", destinations=[{"amount": 10**12, "address": addr}], priority=0)["tx_hash"]
    pool = d.other("get_transaction_pool_hashes").get("tx_hashes", [])
    check(tx1 in pool and tx2 in pool, "two payments in the pool, 20 seconds apart", f"{len(pool)} in the pool")
    step_clock(-10)
    stats = None
    try:
        stats = d.other("get_transaction_pool_stats")["pool_stats"]
    except Exception as e:
        log(f"get_transaction_pool_stats failed: {e!r}")
    time.sleep(2)
    check(node.poll() is None, "clock stepped back 10 s: the node survives get_transaction_pool_stats",
          "running" if node.poll() is None else f"exit code {node.poll()}")
    if stats is not None:
        histo = stats.get("histo", [])
        in_bins = sum(b["txs"] for b in histo)
        check(stats["txs_total"] == 2 and in_bins == 2 and len(histo) == 2 and stats["num_10m"] == 0,
              "the pool statistics are sane",
              f"txs {stats['txs_total']}, histogram bins {len(histo)} holding {in_bins}, older than 10 min {stats['num_10m']}")
    else:
        check(False, "the pool statistics are sane", "no answer")
    if node.poll() is not None:
        log(f"data: {D}")
        return FAILS
    step_clock(0)

    # 2. DNS checkpoint refreshes after the clock steps back
    mine_to(d.height() + 2)                 # the payments leave the pool
    H = d.height()
    agreeing = f"{H - 10}:" + d.rpc("get_block_header_by_height", height=H - 10)["block_header"]["hash"]
    first = publish(G)
    node.send_signal(signal.SIGTERM)
    node.wait(timeout=120)
    node = start_node(False)               # an offline node never reads DNS checkpoints
    d.wait_ready(180)

    def saved_serial():
        files = list((D / "node").rglob("dns_checkpoint_serial"))
        return int(files[0].read_text().split()[0]) if files else 0

    ok = wait(lambda: saved_serial() == first, 60)
    check(ok, "the node reads the test DNS records", f"saved serial {saved_serial()}")
    time.sleep(6)                           # a refresh has just run
    step_clock(-120)
    newer = publish(G, agreeing)
    t0 = time.time()
    ok = wait(lambda: saved_serial() == newer, 30)
    check(ok, "clock stepped back 2 minutes: a newer set is still taken within seconds",
          f"after {time.time() - t0:.0f} s" if ok else f"saved serial still {saved_serial()} after 30 s")
    check(node.poll() is None and d.height() == H, "the node is still running, on its chain", f"height {d.height()}")
    step_clock(0)

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
