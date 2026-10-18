#!/usr/bin/env python3
"""
End-to-end functional test of an Opacra network on one machine.

  1. starts 3 isolated nodes running mainnet consensus rules (contrib/testnet/localnet.sh)
  2. creates 3 wallets (opacra-wallet-rpc) and mines to wallet 1
  3. checks block times / LWMA difficulty, then sends private transactions
     (standard address + subaddress) and waits for them to unlock
  4. inspects the on-chain transactions (RingCT type, 16-member rings, view tags)
  5. exercises selective disclosure: tx key, payment proof and reserve proof
  6. forces a chain split and checks that the network re-converges (reorg)
  7. replays every block: recomputes difficulty (LWMA-1), the development fund payment, and reward (emission +
     fees) independently in Python and compares with the chain

Writes a JSON report to $DATA/report.json.   Needs a built tree (build/release/bin).
"""
import json
import os
import pathlib
import re
import statistics as st
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "sim"))
from rpc import Daemon, Wallet, ATOMIC, RPCError  # noqa: E402
import opacra_params as tp  # noqa: E402

BIN = pathlib.Path(os.environ.get("BIN", HERE.parent.parent / "build" / "release" / "bin"))
DATA = pathlib.Path(os.environ.get("DATA", pathlib.Path.home() / "opacra-localnet"))
BASE_P2P = int(os.environ.get("BASE_P2P", "31000"))
MIN_HEIGHT_FOR_TX = int(os.environ.get("MIN_HEIGHT_FOR_TX", "110"))
MINER_THREADS = int(os.environ.get("MINER_THREADS", "2"))
ENV = dict(os.environ, BIN=str(BIN), DATA=str(DATA), BASE_P2P=str(BASE_P2P), NODES="3")

report = {"checks": [], "started": time.strftime("%Y-%m-%d %H:%M:%S")}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def check(name, ok, detail=""):
    report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    log(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not ok and os.environ.get("STRICT", "1") == "1":
        save_report()
        raise SystemExit(f"check failed: {name}")


def save_report():
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (DATA / "report.json").write_text(json.dumps(report, indent=2))


def localnet(*args):
    subprocess.run([str(HERE / "localnet.sh"), *args], check=True, env=ENV)


def rpc_port(i):
    return BASE_P2P + 10 * i + 1


def start_wallet_rpc(i, daemon_idx):
    port = 32000 + i
    wdir = DATA / f"wallets{i}"
    wdir.mkdir(parents=True, exist_ok=True)
    log_file = open(DATA / f"wallet-rpc{i}.log", "w")
    p = subprocess.Popen([str(BIN / "opacra-wallet-rpc"), "--wallet-dir", str(wdir), "--rpc-bind-port", str(port),
                          "--disable-rpc-login", "--daemon-address", f"127.0.0.1:{rpc_port(daemon_idx)}",
                          "--trusted-daemon", "--log-level", "0", "--non-interactive",
                          "--log-file", str(DATA / f"wallet-rpc{i}.core.log")],
                         stdout=log_file, stderr=subprocess.STDOUT)
    w = Wallet(port)
    w.wait_ready()
    return p, w


def wait_height(d, h, label="", poll=10):
    last = -1
    while True:
        cur = d.height()
        if cur >= h:
            return cur
        if cur != last and cur % 10 == 0:
            info = d.info()
            log(f"  height {cur}/{h} difficulty {info['difficulty']:,} {label}")
        last = cur
        time.sleep(poll)


def start_mining(d, address, threads):
    r = d.other("start_mining", miner_address=address, threads_count=threads,
                do_background_mining=False, ignore_battery=True)
    if r.get("status") != "OK":
        raise RPCError(f"start_mining: {r}")


def stop_mining(d):
    d.other("stop_mining")


def block_stats(headers):
    sol = [b["timestamp"] - a["timestamp"] for a, b in zip(headers, headers[1:])]
    return {
        "blocks": len(headers),
        "mean_solvetime": round(st.mean(sol), 2) if sol else None,
        "median_solvetime": st.median(sol) if sol else None,
        "last_difficulty": headers[-1]["difficulty"],
    }


def dev_fund_keys():
    """Mainnet development fund address and its public view key, from cryptonote_config.h."""
    cfg = (HERE.parent.parent / "src" / "cryptonote_config.h").read_text()
    addr = re.search(r'DEV_FUND_ADDRESS = "([^"]+)"', cfg).group(1)
    view = re.search(r'DEV_FUND_VIEW_KEY = "([0-9a-f]{64})"', cfg).group(1)
    return addr, view


def verify_chain(d):
    """Recompute difficulty, reward and development fund payment for every block from genesis."""
    top = d.height() - 1
    hs = d.headers(0, top)
    ts, cds = [], []
    generated = 0
    mismatches = []
    fee_blocks = 0
    fund_total = 0
    for h in hs:
        height = h["height"]
        exp_diff = tp.lwma_next_difficulty(ts, cds)
        # security audit rule: block 1 costs the startup guess on every network
        # (same rule as Blockchain::get_difficulty_for_next_block)
        if height == 1:
            exp_diff = tp.STARTUP_GUESS
        if exp_diff != h["difficulty"]:
            mismatches.append(("difficulty", height, exp_diff, h["difficulty"]))
        base = tp.block_reward(generated, height)
        fees = 0
        if h["num_txes"] > 0:
            fee_blocks += 1
            blk = d.rpc("get_block", height=height)
            txs = d.other("get_transactions", txs_hashes=blk["tx_hashes"], decode_as_json=True)["txs"]
            for t in txs:
                fees += json.loads(t["as_json"])["rct_signatures"]["txnFee"]
        if h["reward"] != base + fees:
            mismatches.append(("reward", height, base + fees, h["reward"]))
        if height > 0:
            # the last coinbase output pays the fund 5% of the subsidy; the miner gets the rest + fees
            blk = d.rpc("get_block", height=height)
            vout = json.loads(blk["json"])["miner_tx"]["vout"]
            fund = tp.dev_fund_share(base, height)
            fund_total += fund
            if len(vout) < 2 or vout[-1]["amount"] != fund or sum(o["amount"] for o in vout[:-1]) != base - fund + fees:
                mismatches.append(("devfund", height, fund, [o["amount"] for o in vout]))
        generated = min(generated + base, tp.MONEY_SUPPLY)
        if height > 0:
            ts.append(h["timestamp"])
            cds.append(h["cumulative_difficulty"])
    return len(hs), fee_blocks, generated, mismatches, fund_total


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    log(f"binaries: {BIN}")
    resume = os.environ.get("RESUME") == "1"   # attach to a running localnet + wallet RPCs
    if not resume:
        localnet("wipe")
        localnet("start")
    nodes = [Daemon(rpc_port(i)) for i in range(3)]
    for n in nodes:
        n.wait_ready()

    # --- genesis identical on all nodes
    g = [n.header(0) for n in nodes]
    check("genesis identical on all nodes", len({x["hash"] for x in g}) == 1, g[0]["hash"])
    report["genesis_hash"] = g[0]["hash"]
    check("genesis reward = MONEY_SUPPLY >> 22", g[0]["reward"] == tp.base_reward(0), str(g[0]["reward"]))

    # --- wallets
    procs, wallets, addrs = [], [], []
    for i in range(3):
        if resume:
            w = Wallet(32000 + i)
        else:
            p, w = start_wallet_rpc(i, daemon_idx=i)
            procs.append(p)
            w.rpc("create_wallet", filename=f"w{i}", password="", language="English")
        addrs.append(w.rpc("get_address")["address"])
        wallets.append(w)
    report["addresses"] = addrs
    check("standard addresses start with 'Pa'", all(a.startswith("Pa") for a in addrs), addrs[0][:12] + "...")
    if resume:
        sub = wallets[2].rpc("get_address", account_index=0, address_index=[1])["addresses"][0]["address"]
    else:
        sub = wallets[2].rpc("create_address", account_index=0, label="shop checkout")["address"]
    check("subaddresses start with 'Ps'", sub.startswith("Ps"), sub[:12] + "...")
    integ = wallets[1].rpc("make_integrated_address")["integrated_address"]
    check("integrated addresses start with 'Pi'", integ.startswith("Pi"), integ[:12] + "...")

    # --- mine
    miner = nodes[0]
    if not miner.other("mining_status").get("active"):
        start_mining(miner, addrs[0], MINER_THREADS)
    t0 = time.time()
    wait_height(miner, MIN_HEIGHT_FOR_TX, "(mining to wallet 1)")
    report["time_to_min_height_s"] = round(time.time() - t0)
    for n in nodes:
        wait_height(n, MIN_HEIGHT_FOR_TX, "(sync)", poll=2)
    tops = {n.info()["top_block_hash"] for n in nodes}
    hs = miner.headers(1, miner.height() - 1)
    report["startup_stats"] = block_stats(hs)
    report["post_startup_stats"] = block_stats(hs[30:])
    log(f"block stats after startup: {report['post_startup_stats']}")
    check("all nodes on the same chain tip", len(tops) <= 2)  # may differ by one fresh block

    # --- private transfers
    w1, w2, w3 = wallets
    w1.rpc("refresh")
    bal = w1.rpc("get_balance")
    report["miner_balance_before"] = bal
    log(f"wallet1 balance {bal['balance']/ATOMIC:.6f} OPCA, unlocked {bal['unlocked_balance']/ATOMIC:.6f} OPCA")
    check("mined coins unlocked (60-block coinbase lock)", bal["unlocked_balance"] > 0)
    amt2, amt3 = 50_000_000_000, 20_000_000_000  # 0.05 and 0.02 OPCA
    tx = w1.rpc("transfer", destinations=[{"address": addrs[1], "amount": amt2}, {"address": sub, "amount": amt3}],
                priority=0, get_tx_key=True)
    txid, txkey, fee = tx["tx_hash"], tx["tx_key"], tx["fee"]
    report["tx"] = {"hash": txid, "fee": fee}
    log(f"sent tx {txid} fee {fee/ATOMIC:.8f} OPCA")
    h_sent = miner.height()

    # --- on-chain inspection
    # A block found a moment after sending may have been mined on an older template,
    # so wait for the transaction itself rather than for the next height.
    log(f"  waiting for inclusion of {txid[:12]}...")
    deadline = time.time() + 30 * 60
    while True:
        raw = miner.other("get_transactions", txs_hashes=[txid], decode_as_json=True)["txs"][0]
        if raw.get("block_height", 0) > 0 or time.time() > deadline:
            break
        time.sleep(3)
    j = json.loads(raw["as_json"])
    ring_sizes = [len(v["key"]["key_offsets"]) for v in j["vin"]]
    view_tags = all("tagged_key" in o["target"] for o in j["vout"])
    check("transaction confirmed in a block", raw.get("block_height", 0) > 0, f"height {raw.get('block_height')}")
    check("RingCT with Bulletproofs+ (rct type 6)", j["rct_signatures"]["type"] == 6)
    check("every input uses a 16-member ring", all(r == 16 for r in ring_sizes), str(ring_sizes))
    check("outputs carry view tags", view_tags)
    check("amounts hidden on chain (all vout amounts 0)", all(o["amount"] == 0 for o in j["vout"]))
    check("no plaintext addresses in tx", addrs[1] not in raw["as_json"] and sub not in raw["as_json"])
    report["tx"].update({"inputs": len(j["vin"]), "outputs": len(j["vout"]), "ring_sizes": ring_sizes,
                         "weight_bytes": len(raw["as_hex"]) // 2, "block_height": raw.get("block_height")})

    # --- confirmations & unlock (10 blocks)
    t_sent = time.time()
    wait_height(miner, raw["block_height"] + 10, "(10 confirmations)", poll=3)
    report["seconds_to_spendable"] = round(time.time() - t_sent)
    for w in (w2, w3):
        w.rpc("refresh")
    b2, b3 = w2.rpc("get_balance"), w3.rpc("get_balance")
    check("recipient 2 received exact amount", b2["balance"] == amt2, f"{b2['balance']/ATOMIC} OPCA")
    check("recipient 3 (subaddress) received exact amount", b3["balance"] == amt3, f"{b3['balance']/ATOMIC} OPCA")
    check("received funds spendable after 10 blocks", b2["unlocked_balance"] == amt2 and b3["unlocked_balance"] == amt3)

    # --- selective disclosure ("auditable by choice")
    ck = w2.rpc("check_tx_key", txid=txid, tx_key=txkey, address=addrs[1])
    check("tx key proves payment to recipient (check_tx_key)", ck["received"] == amt2, f"{ck['received']/ATOMIC} OPCA, {ck['confirmations']} conf")
    proof = w1.rpc("get_tx_proof", txid=txid, address=addrs[1], message="invoice #1001")["signature"]
    cp = w3.rpc("check_tx_proof", txid=txid, address=addrs[1], message="invoice #1001", signature=proof)
    check("payment proof verifies for a third party (get/check_tx_proof)", cp["good"] and cp["received"] == amt2)
    bad = w3.rpc("check_tx_proof", txid=txid, address=addrs[1], message="invoice #9999", signature=proof)
    check("payment proof bound to its message", not bad["good"])
    rp = w2.rpc("get_reserve_proof", all=True, message="audit 2026-Q4")["signature"]
    cr = w3.rpc("check_reserve_proof", address=addrs[1], message="audit 2026-Q4", signature=rp)
    check("reserve proof shows balance without revealing history", cr["good"] and cr["total"] == amt2, f"total {cr['total']/ATOMIC} OPCA")
    vk = w2.rpc("query_key", key_type="view_key")["key"]
    w3.rpc("generate_from_keys", filename="w1-auditor-view", address=addrs[1], viewkey=vk, password="", restore_height=0)
    w3.rpc("refresh")
    aud = w3.rpc("get_transfers", **{"in": True})
    seen = sum(t["amount"] for t in aud.get("in", []) if t["txid"] == txid)
    check("view-only (auditor) wallet sees incoming payments", seen == amt2, f"{seen/ATOMIC} OPCA")
    w3.rpc("close_wallet")
    w3.rpc("open_wallet", filename="w2", password="")

    # recipient 2 can spend onward
    tx2 = w2.rpc("transfer", destinations=[{"address": addrs[2], "amount": 10_000_000_000}], priority=0)
    check("recipient can re-spend received coins", "tx_hash" in tx2, tx2.get("tx_hash", ""))

    # --- chain split and reorg
    stop_mining(miner)
    localnet("stop-node", "2")
    localnet("start-node", "2", "--offline")
    n2 = Daemon(rpc_port(2))
    n2.wait_ready()
    split_height = n2.height()
    start_mining(miner, addrs[0], 1)
    start_mining(n2, addrs[2], 1)
    log(f"chain split at height {split_height}: node0+1 vs isolated node2")
    wait_height(miner, split_height + 8, "(majority side)", poll=3)
    wait_height(n2, split_height + 4, "(isolated side)", poll=3)
    stop_mining(miner)
    stop_mining(n2)
    top_a, top_b = miner.info()["top_block_hash"], n2.info()["top_block_hash"]
    check("two competing chains exist", top_a != top_b, f"{top_a[:12]} vs {top_b[:12]}")
    localnet("stop-node", "2")
    localnet("start-node", "2")
    n2.wait_ready()
    t0 = time.time()
    converged = False
    while time.time() - t0 < 300:
        tops = {n.info()["top_block_hash"] for n in nodes}
        if len(tops) == 1:
            converged = True
            break
        time.sleep(3)
    heights = [n.height() for n in nodes]
    check("network re-converged on one chain after the split (reorg)", converged, f"heights {heights}")
    report["reorg"] = {"split_height": split_height, "converged_heights": heights}

    # --- independent consensus replay
    n_blocks, fee_blocks, generated, mism, fund_total = verify_chain(nodes[1])
    report["replay"] = {"blocks": n_blocks, "blocks_with_fees": fee_blocks, "generated_atomic": generated,
                        "mismatches": mism[:20]}
    check(f"replayed {n_blocks} blocks: every difficulty matches LWMA-1 reference", not [m for m in mism if m[0] == "difficulty"])
    check(f"replayed {n_blocks} blocks: every reward matches emission+fees", not [m for m in mism if m[0] == "reward"])
    check(f"replayed {n_blocks} blocks: every coinbase pays the development fund 5% of the subsidy",
          not [m for m in mism if m[0] == "devfund"], f"fund total {fund_total / ATOMIC:.6f} OPCA")

    # --- development fund audit: a view-only wallet built from the public view key
    fund_addr, fund_view = dev_fund_keys()
    pf, wf = start_wallet_rpc(3, daemon_idx=1)
    procs.append(pf)
    if (DATA / "wallets3" / "fund-audit.keys").exists():
        wf.rpc("open_wallet", filename="fund-audit", password="")
    else:
        wf.rpc("generate_from_keys", filename="fund-audit", address=fund_addr, viewkey=fund_view, password="",
               restore_height=0)
    wf.rpc("refresh")
    fund_bal = wf.rpc("get_balance")["balance"]
    report["dev_fund"] = {"address": fund_addr, "expected_atomic": fund_total, "view_only_balance_atomic": fund_bal}
    check("anyone can audit the development fund with its public view key",
          fund_bal == fund_total, f"view-only wallet sees {fund_bal / ATOMIC:.6f} OPCA, chain owes {fund_total / ATOMIC:.6f}")

    hs = nodes[1].headers(1, nodes[1].height() - 1)
    report["final_stats"] = block_stats(hs)
    report["final_stats_after_startup"] = block_stats(hs[30:])
    report["headers"] = [{"h": h["height"], "t": h["timestamp"], "d": h["difficulty"], "r": h["reward"], "n": h["num_txes"]} for h in hs]
    save_report()
    for p in procs:
        p.terminate()
    log("ALL CHECKS PASSED" if all(c["ok"] for c in report["checks"]) else "SOME CHECKS FAILED")


if __name__ == "__main__":
    main()
