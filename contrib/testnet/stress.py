#!/usr/bin/env python3
"""
24-hour stress test for the live Opacra testnet, run from a miner's PC.

Phases (default durations, set STRESS_SCALE=0.1 for a 10x shorter run):
  A. Hash-rate swings  - mine with 4, 12, 1, then 4 threads; difficulty must follow
                         and block times recover toward 30 s.
  B. Payment load      - hundreds of small private payments (bursts + steady) from your
                         test wallet to a receiver wallet and its subaddresses, and some
                         back; every payment must confirm, blocks must stay within the
                         size rules, the mempool must drain.
  C. Restarts/outage   - restart the local node, cut it off from the seed for 10 minutes
                         while it keeps mining, reconnect, restart the seed; the two must
                         agree on one chain again each time.
  D. Soak              - keep mining until the total run time is reached.
Throughout: every new block's development-fund payment is checked (5% of the
subsidy as the last coinbase output), the local and seed nodes must agree on the
chain tip, and memory use of both nodes is recorded.

Usage (on your PC, with your testnet node running and synced to the seed):
  STRESS_WALLET=~/opacra-test/mytest python3 contrib/testnet/stress.py
It asks for the wallet password once. Writes $STRESS_DATA/stress_report.md + .json.

Environment:
  BIN            build/portable/bin            binaries
  STRESS_WALLET  ~/opacra-test/mytest           your testnet wallet file (receives mining)
  STRESS_DATA    ~/opacra-stress                working directory and reports
  STRESS_SCALE   1.0                            multiply every phase duration
  SEED_HOST      opacra-seed1                   ssh name of the seed server
  SEED_IP        169.58.62.247                  seed IP (for the outage test)
  NET            testnet                        testnet | regtest (regtest = local dry run)
  LOCAL_RPC      29971                          local node RPC port
  SEED_RPC       (unset)                        dry run only: seed RPC port on 127.0.0.1
"""
import getpass
import json
import os
import pathlib
import random
import shlex
import statistics as st
import subprocess
import sys
import tempfile
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "sim"))
from rpc import Daemon, Wallet, RPCError, ATOMIC, _post  # noqa: E402
import opacra_params as tp  # noqa: E402

BIN = pathlib.Path(os.path.expanduser(os.environ.get("BIN", str(HERE.parent.parent / "build" / "portable" / "bin"))))
WALLET_FILE = pathlib.Path(os.path.expanduser(os.environ.get("STRESS_WALLET", "~/opacra-test/mytest")))
DATA = pathlib.Path(os.path.expanduser(os.environ.get("STRESS_DATA", "~/opacra-stress")))
SCALE = float(os.environ.get("STRESS_SCALE", "1.0"))
SEED_HOST = os.environ.get("SEED_HOST", "opacra-seed1")
SEED_IP = os.environ.get("SEED_IP", "169.58.62.247")
NET = os.environ.get("NET", "testnet")
LOCAL_RPC = int(os.environ.get("LOCAL_RPC", "29971"))
SEED_RPC = os.environ.get("SEED_RPC")
NETFLAG = ["--testnet"] if NET == "testnet" else []
SEED_P2P = 29970 if NET == "testnet" else int(os.environ.get("SEED_P2P", "0"))
TARGET = 30
SLOW_START_END = 20160
ZONE = 75000

DATA.mkdir(parents=True, exist_ok=True)
LOG = open(DATA / "stress.log", "a", buffering=1)
state = {"phase": "start", "blocks": [], "events": [], "checks": [], "tx": [], "memory": [],
         "tip_mismatch_polls": 0, "max_mempool": 0, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
lock = threading.Lock()
stop_flag = threading.Event()


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    LOG.write(line + "\n")


def event(msg):
    with lock:
        state["events"].append({"t": time.time(), "phase": state["phase"], "msg": msg})
    log("EVENT " + msg)


def check(name, ok, detail=""):
    with lock:
        state["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)})
    log(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def minutes(m):
    return m * 60 * SCALE


# --------------------------------------------------------------------------- node access
local = Daemon(LOCAL_RPC)


def seed_info():
    """get_info from the seed: directly in a dry run, else over ssh (its RPC is not public)."""
    if SEED_RPC:
        return Daemon(int(SEED_RPC)).info()
    out = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", SEED_HOST,
                          "curl -s -m 10 http://127.0.0.1:29971/get_info"],
                         capture_output=True, text=True, timeout=40)
    return json.loads(out.stdout)


def seed_rss_kb():
    if SEED_RPC:
        return None
    out = subprocess.run(["ssh", "-o", "BatchMode=yes", SEED_HOST, "ps -C opacrad -o rss= | head -1"],
                         capture_output=True, text=True, timeout=40)
    return int(out.stdout.strip() or 0)


def local_rss_kb():
    out = subprocess.run(["ps", "-C", "opacrad", "-o", "rss="], capture_output=True, text=True)
    vals = [int(x) for x in out.stdout.split() if x.isdigit()]
    return max(vals) if vals else None


def start_mining(address, threads):
    """Start mining; retry while the node is busy (e.g. just after a restart, still syncing)."""
    for attempt in range(30):
        try:
            local.other("stop_mining")
            time.sleep(2)
            r = local.other("start_mining", miner_address=address, threads_count=threads,
                            do_background_mining=False, ignore_battery=True)
        except Exception as e:
            r = {"status": str(e)}
        if r.get("status") == "OK":
            break
        time.sleep(20)
    event(f"mining with {threads} thread(s): {r.get('status')}")


def stop_mining():
    local.other("stop_mining")


def set_ban(ip, ban, seconds=0):
    r = _post(local.base + "/json_rpc", {"jsonrpc": "2.0", "id": "0", "method": "set_bans",
                                          "params": {"bans": [{"host": ip, "ban": ban, "seconds": seconds}]}})
    event(f"{'ban' if ban else 'unban'} {ip}: {r.get('result', r.get('error'))}")


# --------------------------------------------------------------------------- block monitor
def block_fees(height, tx_hashes):
    if not tx_hashes:
        return 0
    txs = local.other("get_transactions", txs_hashes=tx_hashes, decode_as_json=True).get("txs", [])
    return sum(json.loads(t["as_json"])["rct_signatures"]["txnFee"] for t in txs)


def monitor():
    """Follow new blocks: record timing/difficulty/weight and check the fund payment."""
    last = local.height() - 1
    while not stop_flag.is_set():
        try:
            top = local.height() - 1
            for h in range(last + 1, top + 1):
                hdr = local.header(h)
                blk = local.rpc("get_block", height=h)
                j = json.loads(blk["json"])
                fees = block_fees(h, blk.get("tx_hashes", []))
                vout = [o["amount"] for o in j["miner_tx"]["vout"]]
                subsidy = hdr["reward"] - fees
                fund_ok = h == 0 or (len(vout) >= 2 and vout[-1] == tp.dev_fund_share(subsidy, h))
                with lock:
                    state["blocks"].append({"h": h, "t": hdr["timestamp"], "seen": time.time(), "d": hdr["difficulty"],
                                            "w": hdr["block_weight"], "n": hdr["num_txes"], "fund_ok": fund_ok,
                                            "phase": state["phase"]})
                if not fund_ok:
                    log(f"FUND MISMATCH at {h}: outputs {vout}, subsidy {subsidy}")
            last = top
            pool = local.other("get_transaction_pool_stats").get("pool_stats", {})
            with lock:
                state["max_mempool"] = max(state["max_mempool"], pool.get("txs_total", 0))
        except Exception as e:  # node restarting, etc.
            log(f"monitor: {e}")
        stop_flag.wait(10)


def tip_watch():
    """Every 60 s: compare local and seed tips, record memory."""
    while not stop_flag.is_set():
        try:
            li, si = local.info(), seed_info()
            same = li["top_block_hash"] == si["top_block_hash"] or abs(li["height"] - si["height"]) <= 1
            if not same and not state["phase"].startswith("C-"):
                # the two reads are seconds apart (the seed is read over ssh): look again
                # before counting it, and keep the details
                stop_flag.wait(20)
                li2, si2 = local.info(), seed_info()
                if abs(li2["height"] - si2["height"]) > 1:
                    with lock:
                        state["tip_mismatch_polls"] += 1
                    log(f"tips differ: local {li2['height']}, seed {si2['height']}")
            with lock:
                state["memory"].append({"t": time.time(), "local_kb": local_rss_kb(), "seed_kb": seed_rss_kb(),
                                        "local_h": li["height"], "seed_h": si["height"]})
        except Exception as e:
            log(f"tip watch: {e}")
        stop_flag.wait(60)


def wait_converged(timeout_s, label):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            li, si = local.info(), seed_info()
            if li["top_block_hash"] == si["top_block_hash"]:
                check(f"{label}: local and seed agree on one chain", True,
                      f"height {li['height']} after {int(time.time() - t0)} s")
                return True
        except Exception:
            pass
        time.sleep(10)
    li, si = local.info(), seed_info()
    check(f"{label}: local and seed agree on one chain", False, f"local {li['height']} seed {si['height']}")
    return False


# --------------------------------------------------------------------------- wallets
def start_wallet_rpc(port, extra, logname):
    args = [str(BIN / "opacra-wallet-rpc"), *NETFLAG, "--daemon-address", f"127.0.0.1:{LOCAL_RPC}",
            "--rpc-bind-port", str(port), "--disable-rpc-login", "--trusted-daemon", "--non-interactive",
            "--log-file", str(DATA / f"{logname}.log"), *extra]
    p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    w = Wallet(port)
    w.wait_ready(180)
    return p, w


def phase_payments(sender, receiver, duration_s):
    """Bursts and steady payments; returns once all have confirmed or time is up."""
    recv_addrs = [receiver.rpc("get_address")["address"]]
    for i in range(5):
        recv_addrs.append(receiver.rpc("create_address", account_index=0, label=f"stress {i}")["address"])
    sent, failed = [], 0
    t_end = time.time() + duration_s
    burst_every = max(600, duration_s / 6)
    next_burst = time.time()
    while time.time() < t_end:
        n = 40 if time.time() >= next_burst else 1
        if n > 1:
            next_burst = time.time() + burst_every
            event(f"payment burst of {n}")
        for _ in range(n):
            try:
                sender.rpc("refresh")
                bal = sender.rpc("get_balance")["unlocked_balance"]
                if bal < 20 * 10 ** 9:
                    log(f"waiting for unlocked coins ({bal / ATOMIC:.6f} OPCA)")
                    time.sleep(60)
                    continue
                amt = random.randint(1, 20) * 10 ** 8   # 0.0001 - 0.002 OPCA
                r = sender.rpc("transfer", destinations=[{"address": random.choice(recv_addrs), "amount": amt}],
                               priority=0, get_tx_key=True)
                sent.append({"hash": r["tx_hash"], "fee": r["fee"], "weight": r.get("weight"),
                             "t": time.time(), "h": local.height()})
            except RPCError as e:
                failed += 1
                log(f"transfer failed: {e}")
                time.sleep(20)
        time.sleep(60 if n == 1 else 5)
    event(f"sent {len(sent)} payments, {failed} failed attempts")
    # the receiver sends a few back once its coins unlock
    back, returns = 0, []
    for _ in range(20):
        try:
            receiver.rpc("refresh")
            if receiver.rpc("get_balance")["unlocked_balance"] > 10 ** 9:
                r = receiver.rpc("transfer", destinations=[{"address": sender.rpc("get_address")["address"],
                                                            "amount": 5 * 10 ** 8}], priority=0)
                returns.append(r["tx_hash"])
                back += 1
                if back >= 5:
                    break
        except RPCError as e:
            log(f"return payment: {e}")
        time.sleep(60)
    # wait for every payment to confirm
    t0 = time.time()
    pending = {s["hash"] for s in sent} | set(returns)   # return payments too, so the pool can drain
    while pending and time.time() - t0 < 3600:
        txs = local.other("get_transactions", txs_hashes=list(pending)).get("txs", [])
        for t in txs:
            if not t.get("in_pool") and t.get("block_height"):
                for s in sent:
                    if s["hash"] == t["tx_hash"]:
                        s["confirmed_h"] = t["block_height"]
                pending.discard(t["tx_hash"])
        time.sleep(30)
    with lock:
        state["tx"] = sent
    unconfirmed = len(pending - set(returns))
    check("payments: every payment confirmed", unconfirmed == 0 and sent, f"{len(sent)} sent, {unconfirmed} unconfirmed")
    check("payments: receiver sent payments back", back > 0, f"{back} return payments")
    if sent:
        delays = [s["confirmed_h"] - s["h"] for s in sent if "confirmed_h" in s]
        if delays:
            check("payments: median confirmation within 3 blocks", st.median(delays) <= 3,
                  f"median {st.median(delays)} blocks, max {max(delays)}")
    # give anything still in flight a few blocks to confirm before judging the pool
    for _ in range(20):
        pool = local.other("get_transaction_pool_stats").get("pool_stats", {})
        if pool.get("txs_total", 0) == 0:
            break
        time.sleep(30)
    check("payments: mempool drained", pool.get("txs_total", 0) == 0, f"{pool.get('txs_total', 0)} left")


# --------------------------------------------------------------------------- report
def phase_stats(phase):
    bs = [b for b in state["blocks"] if b["phase"] == phase]
    if len(bs) < 3:
        return None
    # only gaps between consecutive heights: a phase can run twice (A-4thr), and the
    # hours between its two runs are not a block time
    gaps = [bs[i]["t"] - bs[i - 1]["t"] for i in range(1, len(bs)) if bs[i]["h"] == bs[i - 1]["h"] + 1]
    if not gaps:
        return None
    return {"blocks": len(bs), "mean_s": round(st.mean(gaps), 1), "median_s": round(st.median(gaps), 1),
            "max_s": round(max(gaps)), "d_start": bs[0]["d"], "d_end": bs[-1]["d"],
            "mean_last_half_s": round(st.mean(gaps[len(gaps) // 2:]), 1)}


def write_report():
    with lock:
        s = json.loads(json.dumps(state))
    s["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (DATA / "stress_report.json").write_text(json.dumps(s, indent=1))
    blocks = s["blocks"]
    lines = ["# Opacra testnet stress test", "",
             f"Run {s['started']} to {s['finished']} ({NET}), {len(blocks)} blocks observed.", "",
             f"**{sum(c['ok'] for c in s['checks'])} of {len(s['checks'])} checks passed.**", "",
             "## Block times by phase (from block timestamps)", "",
             "| Phase | Blocks | Mean | Median | Longest | Mean, 2nd half | Difficulty start → end |",
             "|---|---|---|---|---|---|---|"]
    for ph in sorted({b["phase"] for b in blocks}, key=lambda p: min(b["seen"] for b in blocks if b["phase"] == p)):
        ps = phase_stats(ph)
        if ps:
            lines.append(f"| {ph} | {ps['blocks']} | {ps['mean_s']} s | {ps['median_s']} s | {ps['max_s']} s | "
                         f"{ps['mean_last_half_s']} s | {ps['d_start']:,} → {ps['d_end']:,} |")
    tx = s["tx"]
    if tx:
        lines += ["", "## Payments", "",
                  f"- Sent {len(tx)}; confirmed {sum(1 for t in tx if 'confirmed_h' in t)}.",
                  f"- Fees: median {st.median([t['fee'] for t in tx]) / ATOMIC:.8f} OPCA.",
                  f"- Largest block {max(b['w'] for b in blocks):,} bytes; largest mempool {s['max_mempool']} transactions."]
    mem = [m for m in s["memory"] if m["local_kb"]]
    if mem:
        lines += ["", "## Memory (resident)", "",
                  f"- Local node: {mem[0]['local_kb'] // 1024} MB at start, {mem[-1]['local_kb'] // 1024} MB at end, "
                  f"peak {max(m['local_kb'] for m in mem) // 1024} MB."]
        sm = [m for m in mem if m.get("seed_kb")]
        if sm:
            lines.append(f"- Seed node: {sm[0]['seed_kb'] // 1024} MB at start, {sm[-1]['seed_kb'] // 1024} MB at end, "
                         f"peak {max(m['seed_kb'] for m in sm) // 1024} MB.")
    lines += ["", "## Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for c in s["checks"]:
        lines.append(f"| {c['name']} | {'pass' if c['ok'] else '**FAIL**'} | {c['detail'].replace('|', '/')} |")
    lines += ["", "## Events", ""] + [f"- {time.strftime('%H:%M', time.localtime(e['t']))} [{e['phase']}] {e['msg']}"
                                       for e in s["events"]]
    (DATA / "stress_report.md").write_text("\n".join(lines) + "\n")
    log(f"report written to {DATA / 'stress_report.md'}")


# --------------------------------------------------------------------------- main
def restart_local_node():
    event("restarting the local node")
    stop_mining()
    try:
        _post(local.base + "/stop_daemon", {})
    except Exception:
        pass
    time.sleep(20)
    args = [str(BIN / "opacrad"), *NETFLAG, "--detach"]
    if NET == "testnet":
        args += ["--add-priority-node", f"{SEED_IP}:{SEED_P2P}"]
    else:
        args += shlex.split(os.environ.get("LOCAL_NODE_ARGS", ""))
    subprocess.run(args, check=True)
    local.wait_ready(300)


def main():
    password = os.environ.get("STRESS_PASSWORD") or getpass.getpass(f"Password for {WALLET_FILE}: ")
    pwfile = tempfile.NamedTemporaryFile("w", delete=False, dir=DATA)
    pwfile.write(password)
    pwfile.close()
    os.chmod(pwfile.name, 0o600)
    procs = []
    try:
        ps, sender = start_wallet_rpc(32110, ["--wallet-file", str(WALLET_FILE), "--password-file", pwfile.name], "wallet-sender")
        procs.append(ps)
        os.unlink(pwfile.name)
        wdir = DATA / "receiver"
        wdir.mkdir(exist_ok=True)
        pr, receiver = start_wallet_rpc(32111, ["--wallet-dir", str(wdir)], "wallet-receiver")
        procs.append(pr)
        if (wdir / "stress-recv.keys").exists():
            receiver.rpc("open_wallet", filename="stress-recv", password="")
        else:
            receiver.rpc("create_wallet", filename="stress-recv", password="", language="English")
        miner_addr = sender.rpc("get_address")["address"]
        log(f"miner / sender address {miner_addr[:12]}..., data in {DATA}")

        li, si = local.info(), seed_info()
        check("start: local node and seed agree on one chain", abs(li["height"] - si["height"]) <= 1,
              f"local {li['height']} seed {si['height']}")
        threading.Thread(target=monitor, daemon=True).start()
        threading.Thread(target=tip_watch, daemon=True).start()
        t_start = time.time()

        # A. hash-rate swings
        full = max(2, os.cpu_count() or 4)          # every thread the PC has (12 on a 6-core/12-thread CPU)
        for threads, mins in [(4, 60), (full, 90), (1, 150), (4, 90)]:
            state["phase"] = f"A-{threads}thr" if threads != full else "A-max"
            start_mining(miner_addr, threads)
            time.sleep(minutes(mins))
        with lock:
            a1 = phase_stats("A-1thr")
        check("swings: after dropping to 1 thread, blocks recover toward 30 s",
              a1 is not None and a1["mean_last_half_s"] < 3 * TARGET,
              f"2nd-half mean {a1['mean_last_half_s']} s, difficulty {a1['d_start']:,} → {a1['d_end']:,}" if a1 else "no blocks in this phase")
        with lock:
            a12 = phase_stats("A-max")
        check("swings: after jumping to all threads, difficulty rises",
              a12 is not None and a12["d_end"] > a12["d_start"],
              f"{a12['d_start']:,} → {a12['d_end']:,}" if a12 else "no blocks in this phase")

        # B. payment load (mining continues with 4 threads)
        state["phase"] = "B-payments"
        start_mining(miner_addr, 4)
        phase_payments(sender, receiver, minutes(240))

        # C. restarts and an outage
        state["phase"] = "C-restart-local"
        restart_local_node()
        start_mining(miner_addr, 4)
        wait_converged(minutes(15) + 300, "after restarting the local node")
        if not SEED_RPC:   # (a local dry run can't ban 127.0.0.1 without cutting its own RPC)
            state["phase"] = "C-outage"
            set_ban(SEED_IP, True, int(minutes(10)) + 60)
            time.sleep(minutes(10))
            h_local, h_seed = local.height(), seed_info()["height"]
            check("outage: local node kept mining while cut off", h_local > h_seed, f"local {h_local}, seed {h_seed}")
            set_ban(SEED_IP, False)
            state["phase"] = "C-reconnect"
            wait_converged(minutes(15) + 300, "after the outage")
            state["phase"] = "C-restart-seed"
            event("restarting the seed node")
            subprocess.run(["ssh", SEED_HOST, "systemctl restart opacrad"], check=False)
            time.sleep(60)
            wait_converged(minutes(15) + 300, "after restarting the seed")

        # D. soak until 24 hours (scaled)
        state["phase"] = "D-soak"
        while time.time() - t_start < minutes(24 * 60):
            time.sleep(60)
            write_report()

        stop_flag.set()
        time.sleep(12)
        with lock:
            blocks = list(state["blocks"])
            mism = state["tip_mismatch_polls"]
        bad = [b["h"] for b in blocks if not b["fund_ok"]]
        check("fund: every block paid the development fund exactly 5% of its subsidy", not bad and blocks,
              f"{len(blocks)} blocks checked, mismatches at {bad[:10]}")
        if blocks and blocks[-1]["h"] < SLOW_START_END:
            check("size: no block above 75 kB during the launch slow start", max(b["w"] for b in blocks) <= ZONE,
                  f"largest {max(b['w'] for b in blocks):,} bytes")
        check("tips: local node and seed never disagreed for long outside the restart/outage tests", mism <= 3,
              f"{mism} one-minute polls with different tips")
        mem = [m for m in state["memory"] if m["local_kb"]]
        if len(mem) > 10:
            first = st.median([m["local_kb"] for m in mem[:5]])
            last = st.median([m["local_kb"] for m in mem[-5:]])
            check("memory: local node did not keep growing", last < first * 2 + 512 * 1024,
                  f"{first // 1024} MB -> {last // 1024} MB")
    finally:
        stop_flag.set()
        write_report()
        for p in procs:
            p.terminate()
        if os.path.exists(pwfile.name):
            os.unlink(pwfile.name)
    failed = [c for c in state["checks"] if not c["ok"]]
    print(f"\n{len(state['checks']) - len(failed)}/{len(state['checks'])} checks passed. Report: {DATA / 'stress_report.md'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
