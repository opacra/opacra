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
     record still brings the node back;
  6. the replay attack (25 Oct 2026 review): an emergency record stands and the node is served
     the older, still validly signed answer from before it. Every published set carries a
     "serial:N" record, and the node refuses a set older than the newest it has seen, so it
     stays; the real withdrawal (a higher serial) brings it back;
  7. the newest serial survives a restart, so an older answer is still refused after one;
  8. once serials are in use, a set without one is refused;
  0, 9-11 (25 Oct 2026 review of the serials): the release's built-in minimum serial; unusable
     serials ("-1", an extra digit, two records); the same serial with different records (a
     zone caught mid-edit), also after a restart; a warn-only node saving the serial;
  12. a set that conflicts with checkpoints.json is ignored and not saved, so a restart keeps the
     emergency set really in force;
  13. a node booting with its clock 3 days behind keeps its saved emergency set and its kept
     blocks.

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

    # serials are Unix times: nodes refuse one below the release's built-in minimum or more than
    # a day ahead, so start from now
    serial = [int(time.time())]

    def publish_raw(*lines):
        tmp = records.with_suffix(".new")
        tmp.write_text("".join(l + "\n" for l in lines))
        tmp.replace(records)   # atomic, so the node never reads half a file

    def publish(*lines, at=None):
        # every change publishes a higher serial, as the emergency guide says; "at" replays an
        # older serial (what a saved, still validly signed DNS answer would carry)
        if not lines:
            publish_raw()
            return
        if at is None:
            serial[0] += 1
            at = serial[0]
        publish_raw(f"serial:{at}", *lines)

    def refused_count(reason=""):
        text = (D / "node.log").read_text(errors="replace")
        return sum(1 for l in text.splitlines() if "DNS checkpoint records refused" in l and reason in l)

    def start_node(offline, enforce=True, extra_env=None):
        # Mining needs a node that counts as synchronised: --offline, while the chain is built.
        # The checkpoint part needs the opposite (an offline node never reads DNS checkpoints),
        # so the node is restarted once, before it; a dead exclusive peer keeps it alone.
        p = subprocess.Popen([str(BIN / "opacrad"), "--testnet", "--fixed-difficulty", "1", "--data-dir", str(D / "node")]
                             + (["--enforce-dns-checkpointing"] if enforce else []) +
                             ["--add-exclusive-node", "127.0.0.1:34199", "--no-igd",
                              "--p2p-bind-ip", "127.0.0.1", "--p2p-bind-port", "34190", "--rpc-bind-port", "34191",
                              "--zmq-rpc-bind-port", "34192", "--non-interactive", "--log-level", "0",
                              "--log-file", str(D / "node.log")] + (["--offline"] if offline else []),
                             stdout=open(D / "node.out", "a"), stderr=subprocess.STDOUT,
                             env=dict(env, **(extra_env or {})), start_new_session=True)
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
    # launch day publishes only the genesis record (block 0): the node must still log that it read
    # it, or the seed's alert keeps reporting the checkpoints as unreadable (27 Oct 2026)
    ok = wait(lambda: "DNS checkpoint enforced: block 0 = " in (D / "node.log").read_text(errors="replace"), 30)
    check(ok, "a set with only the genesis record is logged as enforced (block 0)")
    pid0 = node.pid
    log(f"chain: {H0} blocks, tip {tip0[:16]}…, mining stopped")

    def hash_at(h):
        return d.rpc("get_block_header_by_height", height=h)["block_header"]["hash"]

    def on_full_chain():
        return d.height() == H0 and hash_at(H0 - 1) == tip0

    def restart(enforce=True, extra_env=None):
        nonlocal node, pid0
        node.send_signal(signal.SIGTERM)
        node.wait(timeout=120)
        node = start_node(False, enforce, extra_env)
        d.wait_ready(180)
        pid0 = node.pid

    # 0. a node with no serial history still refuses a set older than the release's built-in
    #    minimum serial (here: a replayed answer from long before the release, with a forged record)
    refused0 = refused_count("older than")
    publish(G, f"1:{secrets.token_hex(32)}", at=1000)
    time.sleep(20)
    check(on_full_chain(), "a set older than the built-in minimum serial is refused", f"height {d.height()}")
    check(refused_count("older than") > refused0, "the node logs it as refused")
    publish(G)

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

    # 6. the replay attack: an emergency record stands, and someone serves this node the older
    #    answer from before it (still validly signed). The node must ignore it and stay.
    before_emergency = serial[0]          # the serial of the answer just before the emergency
    publish(G, f"1:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 1, 60)
    check(ok, "emergency record at block 1: rolled back to the genesis block", f"height {d.height()}")
    refused0 = refused_count()
    publish(G, at=before_emergency)       # the replayed pre-emergency answer
    time.sleep(20)
    check(d.height() == 1, "a replayed older answer does not lift the emergency record", f"height {d.height()}")
    check(refused_count() > refused0, "the node logs the older answer as refused")
    publish(G)                            # the real withdrawal, with a higher serial
    back_to_full_chain("real withdrawal after the replay")

    # 7. the newest serial survives a restart: after one, an older answer carrying a wrong
    #    record is still refused
    serial_files = list((D / "node").rglob("dns_checkpoint_serial"))
    # the first line is the serial; the records accepted with it follow
    saved = serial_files[0].read_text().split()[0] if serial_files else ""
    check(saved == str(serial[0]), "the newest serial is saved in the data folder", f"saved {saved or 'nothing'}")
    node.send_signal(signal.SIGTERM)
    node.wait(timeout=120)
    node = start_node(False)
    d.wait_ready(180)
    pid0 = node.pid
    refused0 = refused_count()
    publish(G, f"40:{secrets.token_hex(32)}", at=serial[0] - 3)
    time.sleep(20)
    check(d.height() == H0 and hash_at(H0 - 1) == tip0, "after a restart, an older answer with a wrong record is refused",
          f"height {d.height()}")
    check(refused_count() > refused0, "after a restart, the node logs it as refused")

    # 8. once serials are in use, a set without one is refused too
    refused0 = refused_count()
    publish_raw(G, f"50:{secrets.token_hex(32)}")
    time.sleep(20)
    check(d.height() == H0 and hash_at(H0 - 1) == tip0, "a set without a serial is refused once serials are in use",
          f"height {d.height()}")
    check(refused_count() > refused0, "the set without a serial is logged as refused")
    publish(G)

    # 9. unusable serials are refused and never saved: "-1" (parses as 2^64-1), a typo with an
    #    extra digit (centuries ahead), and two serial records; a genuine later set still works
    for bad, label in ((["serial:-1"], "serial:-1"), ([f"serial:{serial[0]}0"], "a serial with an extra digit"),
                       ([f"serial:{serial[0] + 1}", f"serial:{serial[0] + 2}"], "two serial records")):
        refused0 = refused_count()
        publish_raw(*bad, G, f"40:{secrets.token_hex(32)}")
        time.sleep(15)
        check(on_full_chain(), f"{label}: refused, the node stays on its chain", f"height {d.height()}")
        check(refused_count() > refused0, f"{label}: logged as refused")
    saved = list((D / "node").rglob("dns_checkpoint_serial"))[0].read_text().split()[0]
    check(int(saved) <= serial[0], "no unusable serial was saved", f"saved {saved}")
    publish(G, f"40:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 38, 60)
    check(ok, "a genuine later set is still followed after the bad serials", f"height {d.height()}")
    publish(G)
    back_to_full_chain("withdrawn after the bad serials")

    # 10. the same serial with different records is refused: the zone is caught mid-edit (the
    #     serial already changed, the emergency record not yet added) and that answer is replayed
    publish(G, f"1:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 1, 60)
    check(ok, "emergency record at block 1 (serial S): rolled back to the genesis block", f"height {d.height()}")
    refused0 = refused_count("records differ")
    publish(G, at=serial[0])              # serial S, without the emergency record
    time.sleep(20)
    check(d.height() == 1, "the same serial without the record does not lift it", f"height {d.height()}")
    check(refused_count("records differ") > refused0, "logged as the same serial with different records")
    restart()
    time.sleep(15)
    check(d.height() == 1, "after a restart, the same serial without the record is still refused", f"height {d.height()}")
    publish(G)                            # the real withdrawal, serial S+1
    back_to_full_chain("real withdrawal after the mid-edit replay")

    # 11. a node that only warns tracks and saves the serial too, so switching enforcement on
    #     later starts with that history
    restart(enforce=False)
    publish(G)
    newest = serial[0]
    ok = wait(lambda: list((D / "node").rglob("dns_checkpoint_serial"))[0].read_text().split()[0] == str(newest), 60)
    check(ok, "a warn-only node saves the newest serial")
    restart(enforce=True)
    refused0 = refused_count("older than")
    publish(G, f"40:{secrets.token_hex(32)}", at=newest - 2)
    time.sleep(20)
    check(on_full_chain(), "after switching enforcement on, an older answer with a wrong record is refused",
          f"height {d.height()}")
    check(refused_count("older than") > refused0, "logged as refused")
    publish(G)

    def log_count(text):
        return (D / "node.log").read_text(errors="replace").count(text)

    def saved_serial():
        return list((D / "node").rglob("dns_checkpoint_serial"))[0].read_text().split()[0]

    # 12. a set that conflicts with a checkpoint in checkpoints.json is ignored and not saved, so
    #     a restart keeps the emergency set that was really in force (the reviewer's test)
    net_dir = next((D / "node").rglob("lmdb")).parent   # the network's data folder (testnet3)
    (net_dir / "checkpoints.json").write_text(json.dumps({"hashlines": [{"height": 5, "hash": hash_at(5)}]}))
    restart()                             # loads checkpoints.json
    check(on_full_chain(), "checkpoints.json naming the real block 5 is loaded, node on its chain", f"height {d.height()}")
    publish(G, f"3:{secrets.token_hex(32)}")
    ok = wait(lambda: d.height() == 1, 60)
    check(ok, "emergency record at block 3: rolled back to height 1", f"height {d.height()}")
    in_force = saved_serial()
    conflicts0 = log_count("conflicts with a checkpoint built into this node")
    publish(G, f"3:{secrets.token_hex(32)}", f"5:{secrets.token_hex(32)}")   # a typo at the JSON height
    ok = wait(lambda: log_count("conflicts with a checkpoint built into this node") > conflicts0, 60)
    check(ok and d.height() == 1, "a set conflicting with checkpoints.json is ignored; the node holds", f"height {d.height()}")
    check(saved_serial() == in_force, "the conflicting set is not saved as accepted", f"saved {saved_serial()}")
    restored0 = log_count("restored from the last accepted set")
    restart()
    time.sleep(15)
    check(d.height() == 1, "after a restart the emergency set is still in force", f"height {d.height()}")
    check(log_count("restored from the last accepted set") > restored0, "the node logs that it restored the saved set")
    publish(G)
    back_to_full_chain("withdrawn after the conflicting set")

    # 13. a node that boots with its clock 3 days behind keeps its saved emergency set, and keeps
    #     the kept blocks instead of trying (and failing) to return to them
    shim = D / "fake_time_offset.so"
    subprocess.check_call(["gcc", "-shared", "-fPIC", "-O2", "-o", str(shim), str(HERE / "fake_time_offset.c")])
    forged = f"1:{secrets.token_hex(32)}"
    publish(G, forged)
    ok = wait(lambda: d.height() == 1, 60)
    check(ok, "emergency record at block 1: rolled back to the genesis block", f"height {d.height()}")
    restart(extra_env={"LD_PRELOAD": str(shim), "FAKE_TIME_OFFSET": str(-3 * 86400)})
    time.sleep(20)
    check(d.height() == 1, "clock 3 days behind: the saved emergency set is still in force", f"height {d.height()}")
    check(kept_chain_len() >= H0 - 1, "clock 3 days behind: the kept blocks are still kept", f"side chain of {kept_chain_len()}")
    # a newer set now looks more than a day ahead to this node: refused, with a hint about the clock
    clock0 = log_count("this node's clock is behind")
    publish(G, forged)
    ok = wait(lambda: log_count("this node's clock is behind") > clock0, 30)
    check(ok and d.height() == 1, "a newer set is refused with a hint to check the clock; the node holds", f"height {d.height()}")
    restart()                             # clock right again
    publish(G)
    back_to_full_chain("withdrawn once the clock is right")

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
