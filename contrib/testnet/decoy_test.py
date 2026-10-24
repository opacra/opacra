#!/usr/bin/env python3
"""Development fund outputs are never decoys (24 Oct 2026). Quick check on a private testnet chain (fixed difficulty 1):
mine to a wallet, send several payments, and check that no ring member is a fund output, that
the node marks fund outputs exactly, and that rings are still full (16).

  python3 contrib/testnet/decoy_test.py      (about 10 minutes; ports 34070-34080)
"""
import json, os, pathlib, signal, subprocess, sys, tempfile, time
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "contrib" / "testnet"))
from rpc import Daemon, Wallet  # noqa: E402
BIN = REPO / "build" / "portable" / "bin"
D = pathlib.Path(tempfile.mkdtemp(prefix="decoy-", dir=os.environ.get("TMPDIR")))
env = dict(os.environ); env.pop("HTTPS_PROXY", None); env.pop("HTTP_PROXY", None)
fails = 0
def check(what, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + what + (f"  ({detail})" if detail else ""), flush=True)
    fails += 0 if ok else 1

node = subprocess.Popen([str(BIN / "opacrad"), "--testnet", "--offline", "--fixed-difficulty", "1", "--data-dir", str(D / "node"),
                         "--rpc-bind-port", "34071", "--p2p-bind-port", "34070", "--zmq-rpc-bind-port", "34072",
                         "--non-interactive", "--log-level", "0"], stdout=open(D / "node.out", "w"), stderr=subprocess.STDOUT,
                        env=env, start_new_session=True)
d = Daemon(34071); d.wait_ready(180)
(D / "w").mkdir()
wp = subprocess.Popen([str(BIN / "opacra-wallet-rpc"), "--testnet", "--wallet-dir", str(D / "w"), "--rpc-bind-port", "34080",
                       "--disable-rpc-login", "--daemon-address", "127.0.0.1:34071", "--trusted-daemon", "--non-interactive",
                       "--log-file", str(D / "w.log")], stdout=open(D / "w.out", "w"), stderr=subprocess.STDOUT, env=env,
                      start_new_session=True)
w = Wallet(34080); w.wait_ready(120)
w.rpc("create_wallet", filename="a", password="", language="English")
addr = w.rpc("get_address")["address"]
d.other("start_mining", miner_address=addr, threads_count=1, do_background_mining=False, ignore_battery=True)
while d.height() < 300:
    time.sleep(2)
d.other("stop_mining")
w.rpc("refresh")
print("height", d.height(), "unlocked", w.rpc("get_balance")["unlocked_balance"] / 1e12, flush=True)

total_members = fund_members = 0
for k in range(5):
    tx = w.rpc("transfer", destinations=[{"amount": 10**12, "address": addr}], priority=0)
    raw = d.other("get_transactions", txs_hashes=[tx["tx_hash"]], decode_as_json=True)["txs"][0]
    j = json.loads(raw["as_json"])
    idx = []
    for v in j["vin"]:
        acc = 0
        for off in v["key"]["key_offsets"]:
            acc += off; idx.append(acc)
        check(f"payment {k+1}: ring of 16", len(v["key"]["key_offsets"]) == 16, str(len(v["key"]["key_offsets"])))
    outs = d.other("get_outs", outputs=[{"amount": 0, "index": i} for i in idx])["outs"]
    total_members += len(outs); fund_members += sum(1 for o in outs if o.get("dev_fund"))
    d.other("start_mining", miner_address=addr, threads_count=1, do_background_mining=False, ignore_battery=True)
    h = d.height()
    while d.height() < h + 12:
        time.sleep(1)
    d.other("stop_mining"); w.rpc("refresh")
check("no ring member is a fund output", fund_members == 0, f"{fund_members} of {total_members}")
# independent check: outputs 0..19 belong to the coinbases of blocks 1..10 (the genesis output has
# a plain amount and is not among the amount-0 outputs); in each, the second output is the fund's
early = d.other("get_outs", outputs=[{"amount": 0, "index": i} for i in range(20)], get_txid=True)["outs"]
cb = {d.rpc("get_block", height=h)["miner_tx_hash"]: h for h in range(1, 11)}
ok_tx = all(o["txid"] in cb for o in early)
pos = {}
for i, o in enumerate(early):
    pos.setdefault(o["txid"], []).append(i)
expected = set(v[-1] for v in pos.values())          # last output of each coinbase
flags = set(i for i, o in enumerate(early) if o.get("dev_fund"))
check("outputs 0-19 are the coinbases of blocks 1-10", ok_tx and len(pos) == 10)
check("the node marks exactly the last output of each coinbase", flags == expected, f"marked {sorted(flags)}")
for p in (wp, node):
    p.send_signal(signal.SIGTERM)
for p in (wp, node):
    p.wait(timeout=120)
print("ALL CHECKS PASSED" if fails == 0 else f"{fails} CHECK(S) FAILED")
sys.exit(1 if fails else 0)
