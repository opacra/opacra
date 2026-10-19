#!/usr/bin/env python3
"""Emergency checkpoints at the lowest heights (19 Oct 2026 review).

Two private testnet nodes (fixed difficulty 1, so blocks are instant) mine two different
chains from genesis: A (the "attacker", 12 blocks) and B (the honest one, 8 blocks).
Then, for checkpoints at heights 1, 2 and 5:

  1. node A is restarted with a checkpoints.json that names B's block at that height;
     it must roll back without crashing, never below genesis (to height 1, 1 and 3);
  2. for heights 1 and 2 (at or next to the split) it is connected to B and must end up on
     B's chain. A checkpoint further above the split leaves it stalled on A's blocks below
     it, which is why the emergency guide says to checkpoint the first block after the split.

Finally a checkpoint at height 2 is added while node A runs: the background checkpoint
thread must apply it without killing the daemon.

  python3 contrib/testnet/checkpoint_rollback_test.py [--bin build/portable/bin] [--work DIR]
Standard library only. Exit code 0 when every check passes.
"""
import argparse
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rpc import Daemon  # noqa: E402

ADDR = None  # filled from a fresh wallet address for mining
FAILS = 0


def check(ok, what, detail=""):
    global FAILS
    print("%s %s%s" % ("PASS" if ok else "FAIL", what, ("  (%s)" % detail) if detail else ""), flush=True)
    if not ok:
        FAILS += 1


class Node:
    def __init__(self, binary, data, p2p, rpc, peer=None, offline=False):
        self.data, self.p2p, self.rpc = data, p2p, rpc
        args = [str(binary), "--testnet", "--data-dir", str(data), "--fixed-difficulty", "1",
                "--p2p-bind-ip", "127.0.0.1", "--p2p-bind-port", str(p2p),
                "--rpc-bind-port", str(rpc), "--zmq-rpc-bind-port", str(rpc + 1),
                "--no-igd", "--allow-local-ip", "--non-interactive", "--log-level", "1",
                "--check-updates", "disabled"]
        args += ["--add-exclusive-node", peer] if peer else ["--add-exclusive-node", "127.0.0.1:1"]
        if offline:
            args.append("--offline")
        env = dict(os.environ)
        env.pop("HTTPS_PROXY", None), env.pop("HTTP_PROXY", None)
        self.log = open(data.parent / ("%s-%d.out" % (data.name, int(time.time()))), "ab")
        self.p = subprocess.Popen(args, stdout=self.log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        self.d = Daemon(rpc)

    def ready(self, timeout=120):
        end = time.time() + timeout
        while time.time() < end:
            if self.p.poll() is not None:
                return False
            try:
                self.d.info()
                return True
            except Exception:  # noqa: BLE001
                time.sleep(1)
        return False

    def alive(self):
        return self.p.poll() is None

    def mine(self, blocks):
        start = self.d.height()
        self.d.other("start_mining", miner_address=ADDR, threads_count=1, do_background_mining=False,
                     ignore_battery=True)
        end = time.time() + 300
        while self.d.height() < start + blocks and time.time() < end:
            time.sleep(0.5)
        self.d.other("stop_mining")
        time.sleep(1)

    def stop(self):
        if self.p.poll() is None:
            self.p.send_signal(signal.SIGTERM)
            try:
                self.p.wait(timeout=120)
            except subprocess.TimeoutExpired:
                self.p.kill()


def hashes(d, top):
    return [d.header(h)["hash"] for h in range(top)]


def main():
    global ADDR
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=str(HERE.parent.parent / "build" / "portable" / "bin"))
    ap.add_argument("--work", default=None)
    a = ap.parse_args()
    binary = pathlib.Path(a.bin) / "opacrad"
    work = pathlib.Path(a.work or tempfile.mkdtemp(prefix="cp-rollback-"))
    work.mkdir(parents=True, exist_ok=True)
    # a valid testnet address to mine to (the testnet development fund's own, only for these
    # throwaway chains)
    cfg = (HERE.parent.parent / "src" / "cryptonote_config.h").read_text()
    t = cfg.index("namespace testnet")
    ADDR = cfg[cfg.index('DEV_FUND_ADDRESS = "', t) + 20:].split('"')[0]

    # two separate chains from genesis
    chains = {}
    for name, n, port in (("A", 12, 39100), ("B", 8, 39110)):
        node = Node(binary, work / name, port, port + 1, offline=True)
        check(node.ready(), "node %s started" % name)
        node.mine(n)
        chains[name] = hashes(node.d, node.d.height())
        node.stop()
    a_chain, b_chain = chains["A"], chains["B"]
    check(a_chain[0] == b_chain[0] and a_chain[1] != b_chain[1], "two chains, same genesis, different from block 1",
          "A %d blocks, B %d" % (len(a_chain), len(b_chain)))

    for h in (1, 2, 5):
        d = work / ("A-cp%d" % h)
        shutil.copytree(work / "A", d)
        (d / "testnet3" / "checkpoints.json").write_text(json.dumps({"hashlines": [{"height": h, "hash": b_chain[h]}]}))
        node = Node(binary, d, 39120, 39121, offline=True)
        started = node.ready()
        check(started and node.alive(), "checkpoint at block %d: node starts, no crash" % h)
        if started:
            height = node.d.height()
            want = h - 2 if h > 2 else 1
            check(height == want, "checkpoint at block %d: rolled back to height %d" % (h, want), "height %d" % height)
            check(node.d.header(0)["hash"] == a_chain[0], "checkpoint at block %d: genesis kept" % h)
        node.stop()
        if h > 2:
            continue  # a checkpoint above the split leaves the node stalled, as the guide warns
        # now connected to the honest node: it must switch to B's chain
        b = Node(binary, work / "B", 39110, 39111, peer="127.0.0.1:39120")
        node = Node(binary, d, 39120, 39121, peer="127.0.0.1:39110")
        b.ready(), node.ready()
        end = time.time() + 120
        while time.time() < end and node.alive():
            try:
                if node.d.height() == len(b_chain) and node.d.header(len(b_chain) - 1)["hash"] == b_chain[-1]:
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)
        top = node.d.header(len(b_chain) - 1)["hash"] if node.alive() and node.d.height() >= len(b_chain) else "-"
        check(node.alive() and top == b_chain[-1], "checkpoint at block %d: node joins the honest chain" % h,
              "height %s" % (node.d.height() if node.alive() else "dead"))
        node.stop()
        b.stop()

    # a checkpoint at block 2 arriving while the node runs (background checkpoint thread)
    d = work / "A-live"
    shutil.copytree(work / "A", d)
    node = Node(binary, d, 39120, 39121, offline=True)
    node.ready()
    (d / "testnet3" / "checkpoints.json").write_text(json.dumps({"hashlines": [{"height": 2, "hash": b_chain[2]}]}))
    print("waiting up to 11 minutes for the node's checkpoint refresh...", flush=True)
    end = time.time() + 660
    while time.time() < end and node.alive():
        try:
            if node.d.height() == 1:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(10)
    alive = node.alive()
    check(alive, "checkpoint added while running: daemon still running")
    if alive:
        check(node.d.height() == 1, "checkpoint added while running: rolled back to height 1", "height %d" % node.d.height())
    node.stop()

    print("ALL CHECKS PASSED" if FAILS == 0 else "%d CHECK(S) FAILED" % FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
