#!/usr/bin/env python3
"""The launch-time rule (19 Oct 2026 review): no block after genesis may be dated before
the network's launch time (the fork table's height-1 entry).

Needs a build whose testnet launch time is a few minutes in the future (set it in
src/hardforks/hardforks.cpp for the test only, then restore it). The test:
  1. starts mining on a fresh private testnet node (fixed difficulty 1) well before the
     launch time: no block may appear until the last 3 minutes before it (future time limit);
  2. after the launch time: blocks appear, and block 1 is dated at or after the launch time;
  3. a block template with its timestamp changed to before the launch time is refused.

  python3 contrib/testnet/launch_time_test.py --launch <epoch seconds> [--bin build/portable/bin]
"""
import argparse
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rpc import Daemon  # noqa: E402

FAILS = 0


def check(ok, what, detail=""):
    global FAILS
    print("%s %s%s" % ("PASS" if ok else "FAIL", what, ("  (%s)" % detail) if detail else ""), flush=True)
    if not ok:
        FAILS += 1


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7f
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def read_varint(buf, i):
    n = shift = 0
    while True:
        b = buf[i]
        n |= (b & 0x7f) << shift
        i += 1
        if not b & 0x80:
            return n, i
        shift += 7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--launch", type=int, required=True)
    ap.add_argument("--bin", default=str(HERE.parent.parent / "build" / "portable" / "bin"))
    a = ap.parse_args()
    T = a.launch
    if T - time.time() < 300:
        sys.exit("The launch time must be at least 5 minutes ahead")
    cfg = (HERE.parent.parent / "src" / "cryptonote_config.h").read_text()
    t = cfg.index("namespace testnet")
    addr = cfg[cfg.index('DEV_FUND_ADDRESS = "', t) + 20:].split('"')[0]
    data = pathlib.Path(tempfile.mkdtemp(prefix="launch-time-"))
    env = dict(os.environ)
    env.pop("HTTPS_PROXY", None), env.pop("HTTP_PROXY", None)
    p = subprocess.Popen([str(pathlib.Path(a.bin) / "opacrad"), "--testnet", "--offline", "--data-dir", str(data),
                          "--fixed-difficulty", "1", "--rpc-bind-port", "39131", "--zmq-rpc-bind-port", "39132",
                          "--p2p-bind-port", "39130", "--non-interactive", "--log-level", "1",
                          "--check-updates", "disabled"],
                         stdout=open(data / "out.log", "wb"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
    d = Daemon(39131)
    d.wait_ready(timeout=120)
    d.other("start_mining", miner_address=addr, threads_count=1, do_background_mining=False, ignore_battery=True)
    print("mining from %d s before the launch time" % (T - time.time()), flush=True)

    # 1. nothing before the last 3 minutes
    while time.time() < T - 200:
        time.sleep(5)
    check(d.height() == 1, "no block while the launch is more than 3 minutes away", "height %d" % d.height())

    # 2. blocks after the launch time, block 1 dated at or after it
    while time.time() < T + 60:
        time.sleep(5)
    h = d.height()
    check(h > 1, "blocks after the launch time", "height %d" % h)
    if h > 1:
        ts = d.header(1)["timestamp"]
        check(ts >= T, "block 1 is dated at or after the launch time", "block 1 %d, launch %d" % (ts, T))
    d.other("stop_mining")
    time.sleep(2)

    # 3. a template re-dated before the launch time is refused
    tpl = d.rpc("get_block_template", wallet_address=addr, reserve_size=8)
    blob = bytes.fromhex(tpl["blocktemplate_blob"])
    _, i = read_varint(blob, 0)          # major version
    _, i = read_varint(blob, i)          # minor version
    ts, j = read_varint(blob, i)         # timestamp
    early = blob[:i] + varint(T - 100) + blob[j:]
    before = d.height()
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def submit(b):
        req = urllib.request.Request("http://127.0.0.1:39131/json_rpc", headers={"Content-Type": "application/json"},
                                     data=json.dumps({"jsonrpc": "2.0", "id": "0", "method": "submit_block",
                                                      "params": [b.hex()]}).encode())
        return json.loads(op.open(req, timeout=60).read())

    r = submit(early)
    check("error" in r and d.height() == before, "a block dated before the launch time is refused",
          (r.get("error") or {}).get("message", "accepted!"))
    r = submit(blob)
    check(r.get("result", {}).get("status") == "OK" and d.height() == before + 1,
          "the same template, correctly dated, is accepted", "height %d" % d.height())

    p.send_signal(signal.SIGTERM)
    p.wait(timeout=120)
    print("ALL CHECKS PASSED" if FAILS == 0 else "%d CHECK(S) FAILED" % FAILS)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
