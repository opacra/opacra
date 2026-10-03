#!/usr/bin/env python3
"""Regression tests for Opacra's block-acceptance rules, on throwaway regtest nodes.

  1. There is no reorg-depth limit: honest side chains forking 700 and 721 blocks deep
     are accepted. (The side-chain difficulty floor that stops low-difficulty floods is
     covered by tests/opacra; regtest runs at a fixed difficulty, which bypasses it.)
  2. A side-chain block more than 3 minutes in the future is not accepted.
  3. In the first 11 blocks a side chain follows the main chain's median-time-past
     rule (no check below height 11), so a node can reorganise onto it.
  4. A node whose clock is 5 minutes slow does not accept a peer's new blocks
     (too far in the future for it) but does not ban that honest peer either, and
     syncs from it once its clock is fixed.

Usage:  BIN=build/portable/bin python3 contrib/testnet/block_rules_test.py
Needs gcc (builds the clock-offset shim for test 4). Ports 33000-33100 on 127.0.0.1.
Exit code 0 when every check passes. Writes $DATA/block_rules_report.json.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "coin-identity"))
from rpc import Daemon, RPCError, _post  # noqa: E402
import coinid  # noqa: E402

BIN = pathlib.Path(os.environ.get("BIN", HERE.parent.parent / "build" / "release" / "bin"))
DATA = pathlib.Path(os.environ.get("DATA", tempfile.mkdtemp(prefix="opacra-rules-")))
DATA.mkdir(parents=True, exist_ok=True)
FTL = 180

results = []
procs = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def address():
    _, spend = coinid.gen_keypair()
    _, view = coinid.gen_keypair()
    return coinid.encode_address(30598, spend, view)


ADDR = address()


def start_node(name, p2p, extra=(), env_extra=None):
    d = DATA / name
    d.mkdir(parents=True, exist_ok=True)
    args = [str(BIN / "opacrad"), "--regtest", "--fixed-difficulty", "1", "--non-interactive",
            "--data-dir", str(d), "--log-file", str(d / "opacra.log"), "--log-level", "1",
            "--p2p-bind-ip", "127.0.0.1", "--p2p-bind-port", str(p2p),
            "--rpc-bind-ip", "127.0.0.1", "--rpc-bind-port", str(p2p + 1), "--zmq-rpc-bind-port", str(p2p + 2),
            "--no-igd", "--disable-dns-checkpoints", "--check-updates", "disabled", *extra]
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=env)
    procs.append(p)
    node = Daemon(p2p + 1)
    node.wait_ready(180)
    return node, p


def stop(p):
    p.terminate()
    try:
        p.wait(60)
    except subprocess.TimeoutExpired:
        p.kill()


def generate(node, n):
    return node.rpc("generateblocks", amount_of_blocks=n, wallet_address=ADDR, starting_nonce=0)


def json_rpc_list(node, method, params):
    r = _post(node.base + "/json_rpc", {"jsonrpc": "2.0", "id": "0", "method": method, "params": params})
    return r


def varint(n):
    return coinid.varint(n)


def read_varint(b, i):
    n, shift = 0, 0
    while True:
        c = b[i]
        i += 1
        n |= (c & 0x7F) << shift
        shift += 7
        if not c & 0x80:
            return n, i


def template(node, prev=None):
    params = {"wallet_address": ADDR, "reserve_size": 8}
    if prev:
        params["prev_block"] = prev
    return node.rpc("get_block_template", **params)


def with_timestamp(blob_hex, ts, nonce=0):
    """Rewrite a block blob's timestamp (and nonce); fixed difficulty 1 accepts any hash."""
    b = bytes.fromhex(blob_hex)
    _, i = read_varint(b, 0)     # major version
    _, i = read_varint(b, i)     # minor version
    _, j = read_varint(b, i)     # timestamp
    out = b[:i] + varint(ts) + b[j:j + 32] + nonce.to_bytes(4, "little") + b[j + 36:]
    return out.hex()


def submit(node, blob_hex):
    r = json_rpc_list(node, "submit_block", [blob_hex])
    return "error" not in r, r.get("error", r.get("result"))


def alt_chains(node):
    return node.rpc("get_alternate_chains").get("chains", [])


def header_hash(node, h):
    return node.header(h)["hash"]


# --------------------------------------------------------------------------- tests
def test_reorg_depth():
    node, p = start_node("depth", 33000, ["--offline"])
    generate(node, 760)
    top = node.height() - 1
    check("depth: chain built", top == 760, f"top height {top}")

    fork_ok = top - 700           # depth 700 -> allowed
    t = template(node, header_hash(node, fork_ok))
    ok, info = submit(node, with_timestamp(t["blocktemplate_blob"], int(time.time()), 1))
    chains = alt_chains(node)
    check("depth: side chain forking 700 blocks deep is accepted", ok and len(chains) == 1, info)

    fork_deep = top - 721         # deeper still -> also allowed (no depth limit)
    t = template(node, header_hash(node, fork_deep))
    ok, info = submit(node, with_timestamp(t["blocktemplate_blob"], int(time.time()), 2))
    check("depth: side chain forking 721 blocks deep is accepted (no depth limit)", ok and len(alt_chains(node)) == 2, info)

    # test 2 on the same node: a side-chain block from the future
    fork = top - 10
    t = template(node, header_hash(node, fork))
    ok, info = submit(node, with_timestamp(t["blocktemplate_blob"], int(time.time()) + FTL + 600, 3))
    check("future: side-chain block 13 minutes ahead is not accepted", (not ok) and len(alt_chains(node)) == 2, info)
    t = template(node, header_hash(node, fork))
    ok, info = submit(node, with_timestamp(t["blocktemplate_blob"], int(time.time()) + 60, 4))
    check("future: side-chain block 1 minute ahead is accepted", ok and len(alt_chains(node)) == 3, info)
    stop(p)


def test_early_median_time():
    node, p = start_node("mtp", 33010, ["--offline"])
    generate(node, 2)
    T = node.header(2)["timestamp"]
    genesis = header_hash(node, 0)
    # side chain 1', 2' from genesis, then 3' dated 100 s before the median of 1'-2'
    t1 = template(node, genesis)
    ok1, i1 = submit(node, with_timestamp(t1["blocktemplate_blob"], T + 1, 11))
    c = alt_chains(node)
    h1 = c[0]["block_hash"] if c else None
    t2 = template(node, h1)
    ok2, i2 = submit(node, with_timestamp(t2["blocktemplate_blob"], T + 1, 12))
    c = alt_chains(node)
    h2 = c[0]["block_hash"] if c else None
    check("mtp: side chain of 2 blocks built", ok1 and ok2 and h2, f"{i1} {i2}")
    t3 = template(node, h2)
    ok3, i3 = submit(node, with_timestamp(t3["blocktemplate_blob"], T - 100, 13))
    top = node.header(node.height() - 1)
    check("mtp: block 3 dated below the side chain's median is accepted and the node reorganises",
          ok3 and node.height() == 4 and top["timestamp"] == T - 100, f"{i3}; height {node.height()}")
    stop(p)


def test_slow_clock_no_ban(shim):
    a, pa = start_node("clockA", 33020, ["--add-exclusive-node", "127.0.0.1:33030"])
    b, pb = start_node("clockB", 33030, ["--add-exclusive-node", "127.0.0.1:33020"],
                       {"LD_PRELOAD": shim, "FAKE_TIME_OFFSET": "-300"})
    # wait for the two nodes to connect
    t0 = time.time()
    while time.time() - t0 < 90:
        if b.info()["outgoing_connections_count"] + b.info()["incoming_connections_count"] > 0:
            break
        time.sleep(2)
    check("clock: nodes connected", b.info()["outgoing_connections_count"] + b.info()["incoming_connections_count"] > 0)
    for _ in range(14):
        generate(a, 1)
        time.sleep(3)
    time.sleep(10)
    bans = b.rpc("get_bans").get("bans", [])
    check("clock: slow node did not accept blocks from 5 minutes in its future", b.height() == 1, f"B height {b.height()}, A height {a.height()}")
    check("clock: slow node did not ban the honest peer", not bans, bans)
    log = (DATA / "clockB" / "opacra.log").read_text(errors="replace")
    check("clock: slow node logged the clock problem", "check this computer's clock" in log)
    # fix the clock: the same node must now catch up with its peer
    stop(pb)
    b, pb = start_node("clockB", 33030, ["--add-exclusive-node", "127.0.0.1:33020"])
    t0 = time.time()
    while time.time() - t0 < 120 and b.height() < a.height():
        time.sleep(3)
    check("clock: with its clock fixed, the node syncs from the same peer", b.height() == a.height(),
          f"B height {b.height()}, A height {a.height()}")
    stop(pa)
    stop(pb)


def main():
    shim = DATA / "fake_time_offset.so"
    subprocess.check_call(["gcc", "-shared", "-fPIC", "-O2", "-o", str(shim), str(HERE / "fake_time_offset.c")])
    tests = [("reorg depth / future side-chain blocks", test_reorg_depth),
             ("early median-time-past", test_early_median_time),
             ("slow clock", lambda: test_slow_clock_no_ban(str(shim)))]
    for name, fn in tests:
        try:
            fn()
        except (RPCError, OSError) as e:
            check(f"{name}: test ran without errors", False, e)
        finally:
            for p in procs:
                if p.poll() is None:
                    p.kill()
            procs.clear()
    (DATA / "block_rules_report.json").write_text(json.dumps(results, indent=2))
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed. Data: {DATA}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
