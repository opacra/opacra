#!/usr/bin/env python3
"""Two miners behind two relays: a new block must reach a miner promptly.

  relayA <-> relayB ; m1 -> relayA ; m2 -> relayB      (each node on its own 127.0.0.N)

A miner's only links on a small network are a couple of seeds. If a connection that starts
syncing waits for an idle timeout before asking for blocks, a miner goes minutes without the
other miners' blocks and keeps mining its own fork. The case that triggers it: m1 is ahead
and relayA downloads blocks from m1; then m2 finds a block, so relayA gets ahead of m1.
m1 must fetch that block at its next sync with relayA (at most about a minute), not after
the 4-minute idle-peer kick.

Testnet rules with --fixed-difficulty, private nodes only. Usage:
  python3 contrib/testnet/relay_test.py [--bin DIR]     (default: the newest build)
Exit 0 when every check passes.
"""
import argparse
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rpc import Daemon  # noqa: E402

NODES = {  # name: (ip, p2p, rpc, exclusive peers)
    "relayA": ("127.0.0.2", 36110, 36111, ["127.0.0.3:36120"]),
    "relayB": ("127.0.0.3", 36120, 36121, ["127.0.0.2:36110"]),
    "m1": ("127.0.0.4", 36130, 36131, ["127.0.0.2:36110"]),
    "m2": ("127.0.0.5", 36140, 36141, ["127.0.0.3:36120"]),
}
DIFF = 3000
STARTED = []
FAILS = 0


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def check(ok, name, detail=""):
    global FAILS
    log(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILS += 1


def default_bin():
    found = [d for d in (HERE.parent.parent / "build" / n / "bin" for n in ("release", "portable"))
             if (d / "opacrad").exists()]
    return max(found, key=lambda d: (d / "opacrad").stat().st_mtime) if found else HERE


def start(binp, data, name, offline=False):
    ip, p2p, rpc, peers = NODES[name]
    d = data / name
    d.mkdir(parents=True, exist_ok=True)
    args = [str(binp / "opacrad"), "--testnet", "--fixed-difficulty", str(DIFF), "--data-dir", str(d),
            "--p2p-bind-ip", ip, "--p2p-bind-port", str(p2p), "--rpc-bind-ip", ip, "--confirm-external-bind",
            "--rpc-bind-port", str(rpc), "--zmq-rpc-bind-port", str(rpc + 1), "--no-igd", "--allow-local-ip",
            "--check-updates", "disabled", "--disable-dns-checkpoints", "--log-level", "1",
            # every node's outgoing connections come from 127.0.0.1 on one machine
            "--max-connections-per-ip", "20", "--non-interactive", "--log-file", str(d / "node.log")]
    for p in peers:
        args += ["--add-exclusive-node", p]
    if offline:
        args += ["--offline"]
    env = dict(os.environ)
    env.pop("HTTPS_PROXY", None), env.pop("HTTP_PROXY", None)
    p = subprocess.Popen(args, stdout=open(d / "out.log", "a"), stderr=subprocess.STDOUT, env=env,
                         start_new_session=True)
    STARTED.append(p)
    dm = Daemon(rpc, host=ip)
    dm.wait_ready(180)
    return p, dm


def stop(p):
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=120)


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=os.environ.get("BIN") or default_bin())
    a = ap.parse_args()
    binp = pathlib.Path(a.bin).resolve()
    ver = subprocess.run([str(binp / "opacrad"), "--version"], capture_output=True, text=True).stdout.strip()
    log(f"binaries: {binp} | {ver}")
    data = pathlib.Path(tempfile.mkdtemp(prefix="relay-"))

    wd = data / "w"
    wd.mkdir()
    subprocess.run([str(binp / "opacra-wallet-cli"), "--testnet", "--offline", "--generate-new-wallet",
                    str(wd / "a"), "--password", "", "--mnemonic-language", "English",
                    "--create-address-file", "--command", "address"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    addr = (wd / "a.address.txt").read_text().strip()

    # 1. m1 mines 3 blocks alone (offline), so it starts ahead of everyone
    p, m1 = start(binp, data, "m1", offline=True)
    m1.other("start_mining", miner_address=addr, threads_count=1, do_background_mining=False, ignore_battery=True)
    ok = wait(lambda: m1.height() >= 4, 600)
    m1.other("stop_mining")
    check(ok, "m1 mined 3 blocks on its own", f"height {m1.height()}")
    stop(p)
    STARTED.remove(p)

    # 2. everyone starts; relayA downloads m1's blocks (m1 serves them), m2 syncs through relayB
    ds = {}
    for n in ("relayA", "relayB", "m2", "m1"):
        _, ds[n] = start(binp, data, n)
    ok = wait(lambda: all(ds[n].height() == 4 for n in ds), 180)
    check(ok, "all four nodes synced to m1's blocks", str({n: ds[n].height() for n in ds}))

    # 3. m2 finds one block: relayA is now ahead of m1, which had just served it
    ok = wait(lambda: ds["m2"].other("start_mining", miner_address=addr, threads_count=1,
                                     do_background_mining=False, ignore_battery=True).get("status") == "OK", 120)
    check(ok, "m2 can mine")
    ok = wait(lambda: ds["m2"].height() >= 5, 600)
    ds["m2"].other("stop_mining")
    check(ok, "m2 found block 5")
    ok = wait(lambda: ds["relayA"].height() >= 5, 60)
    check(ok, "the block reached relayA", f"height {ds['relayA'].height()}")
    t0 = time.time()

    # 4. m1 must fetch it at its next sync with relayA, not after the 4-minute idle kick
    ok = wait(lambda: ds["m1"].height() >= 5, 300)
    took = time.time() - t0
    check(ok and took < 120, "m1 got the new block within 2 minutes", f"{took:.0f} s")
    kicks = len(re.findall(r"kicking idle peer", (data / "m1" / "node.log").read_text(errors="replace")))
    check(kicks == 0, "m1 never had to wait for the idle-peer kick", f"{kicks} kick(s)")
    same = len({ds[n].rpc("get_block_header_by_height", height=4)["block_header"]["hash"] for n in ds}) == 1
    check(same, "all nodes on the same chain")

    log("ALL CHECKS PASSED" if FAILS == 0 else f"{FAILS} CHECK(S) FAILED")
    if FAILS == 0:
        shutil.rmtree(data, ignore_errors=True)
    else:
        log(f"data: {data}")
    return FAILS


if __name__ == "__main__":
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
