#!/usr/bin/env python3
"""Launch-day genesis: one scripted procedure for a new chain (testnet 3 now, mainnet later).

  make_genesis.py apply  --network testnet --message "Opacra testnet 3 genesis | 2026-10-25 | <headline>" \
                         --launch "2026-10-25 18:00"
      writes a new network ID, the genesis transaction (built from the message alone, see
      coinid.genesis_tx) and the launch time into src/cryptonote_config.h and
      src/hardforks/hardforks.cpp, and prints what changed. The launch time is a consensus
      rule (since 19 Oct 2026): no block after genesis may be dated before it, and nodes accept block 1
      from 3 minutes before it. Use the minute mining opens, never later.

  make_genesis.py verify --network testnet [--build build/portable]
      builds opacrad, starts it offline on a scratch folder, and checks that block 0 carries
      exactly that genesis transaction (hash recomputed independently here); prints the genesis
      hash and the ADD_CHECKPOINT2 line, and with --checkpoint writes it into
      src/checkpoints/checkpoints.cpp

Mainnet on launch day: the same two commands with --network mainnet and that day's headline.
Run from the repository root. Standard library only (coinid.py supplies Keccak and ed25519).
"""
import argparse
import calendar
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "contrib" / "coin-identity"))
import coinid  # noqa: E402

CONFIG = ROOT / "src" / "cryptonote_config.h"
HARDFORKS = ROOT / "src" / "hardforks" / "hardforks.cpp"
CHECKPOINTS = ROOT / "src" / "checkpoints" / "checkpoints.cpp"
COIN_NETWORK = ROOT / "src" / "coin_network.h"
GENESIS_REWARD = (10_000_000 * 10 ** 12) >> 22   # MONEY_SUPPLY >> EMISSION_SPEED_FACTOR_PER_BLOCK
RPC_PORT = {"mainnet": 29961, "testnet": 29971}
FLAG = {"mainnet": [], "testnet": ["--testnet"]}


def network_block(text, network):
    """(start, end) of the config namespace holding this network's identity."""
    if network == "testnet":
        m = re.search(r"\n  namespace testnet\n  \{\n", text)
        start = m.end()
    else:
        start = text.index("namespace config\n{")
    end = text.index("\n  }", start) if network == "testnet" else text.index("namespace testnet", start)
    return start, end


def check_constants(text):
    ms = re.search(r"#define MONEY_SUPPLY\s+\(\(uint64_t\)(\d+) \* \(uint64_t\)(\d+)\)", text)
    ef = re.search(r"#define EMISSION_SPEED_FACTOR_PER_BLOCK\s+\((\d+)\)", text)
    if not ms or not ef or (int(ms.group(1)) * int(ms.group(2))) >> int(ef.group(1)) != GENESIS_REWARD:
        sys.exit("MONEY_SUPPLY or the emission factor changed: update GENESIS_REWARD in this script first.")


def apply(a):
    msg = a.message.strip()
    if not msg or len(msg.encode()) > 255:
        sys.exit("The message must be 1-255 bytes (it is stored in the genesis block).")
    t = calendar.timegm(time.strptime(a.launch, "%Y-%m-%d %H:%M"))
    # the lowest DNS checkpoint serial this release accepts: now, before any record of the new
    # chain exists, so a node with no history refuses every older (replayed) record set
    min_serial = int(time.time())
    cn = COIN_NETWORK.read_text()
    cn, n6 = re.subn(r"(case cryptonote::%s: return )\d+(;\s*// dns min serial \(make_genesis\.py\))"
                     % ("MAINNET" if a.network == "mainnet" else "TESTNET"),
                     lambda m: m.group(1) + str(min_serial) + m.group(2), cn, count=1)
    if n6 != 1:
        sys.exit("Could not find the %s DNS min serial line in %s" % (a.network, COIN_NETWORK))
    text = CONFIG.read_text()
    check_constants(text)
    tx, out_key, tx_pub = coinid.genesis_tx(GENESIS_REWARD, msg)
    nid = coinid.network_id()
    s, e = network_block(text, a.network)
    block = text[s:e]
    block, n1 = re.subn(r"(boost::uuids::uuid const NETWORK_ID = \{ \{\n\s*)[^\n]*(\n\s*\} \};)",
                        lambda m: m.group(1) + coinid.c_uuid(nid) + m.group(2), block, count=1)
    block, n2 = re.subn(r'(std::string const GENESIS_TX = ")[0-9a-f]+(";)', lambda m: m.group(1) + tx + m.group(2), block, count=1)
    if (n1, n2) != (1, 1):
        sys.exit("Could not find NETWORK_ID and GENESIS_TX for %s in %s" % (a.network, CONFIG))
    CONFIG.write_text(text[:s] + block + text[e:])

    hf = HARDFORKS.read_text()
    table = "mainnet_hard_forks" if a.network == "mainnet" else "testnet_hard_forks"
    i = hf.index("const hardfork_t %s[] = {" % table)
    j = hf.index("};", i)
    body = hf[i:j]
    body, n3 = re.subn(r"\{ 1, 0, 0, \d+ \}", "{ 1, 0, 0, %d }" % (t - 1), body, count=1)
    # the launch entry, with any old comment on its line replaced
    body, n4 = re.subn(r"\{ 16, 1, 0, \d+ \},[^\n]*", "{ 16, 1, 0, %d }, // launch: %s UTC (make_genesis.py)" % (t, a.launch),
                       body, count=1)
    if (n3, n4) != (1, 1):
        sys.exit("Could not find the fork table entries for %s" % a.network)
    HARDFORKS.write_text(hf[:i] + body + hf[j:])

    # a new genesis makes every hard-coded checkpoint of this network wrong (they name the old
    # chain's blocks), and a node refuses to start when its genesis fails one: remove them all;
    # verify --checkpoint then adds the new genesis
    cp = CHECKPOINTS.read_text()
    marker = "    if (nettype == TESTNET)\n    {\n" if a.network == "testnet" else "    if (nettype == MAINNET)\n    {\n"
    if marker not in cp:
        sys.exit("Could not find the %s block in %s" % (a.network, CHECKPOINTS))
    k = cp.index(marker) + len(marker)
    end = cp.index("\n    }\n", k)
    block, n5 = re.subn(r"\n?[ \t]*ADD_CHECKPOINT2\([^;]*\);[^\n]*", "", cp[k:end])
    CHECKPOINTS.write_text(cp[:k] + block.lstrip("\n") + cp[end:] if n5 else cp)
    COIN_NETWORK.write_text(cn)

    print("Network:        %s" % a.network)
    print("Message:        %s" % msg)
    print("Network ID:     %s" % coinid.c_uuid(nid))
    print("Genesis tx:     %s" % tx)
    print("Output key:     %s (derived from the message: nobody holds its secret key)" % out_key)
    print("Launch time:    %s UTC (%d) written into the fork table" % (a.launch, t))
    print("Checkpoints:    %d old %s checkpoint(s) removed from checkpoints.cpp" % (n5, a.network))
    print("DNS min serial: %d written into coin_network.h; publish the genesis record with serial:$(date +%%s) at launch"
          % min_serial)
    print("                consensus: no block 1 before this; mining works from 3 minutes before it")
    if t > time.time() + 2 * 86400:
        print("WARNING: the launch time is more than 2 days away; nobody can mine this chain until then")
    print("Next: make_genesis.py verify --network %s" % a.network)


def rpc(port, method, params=None):
    req = urllib.request.Request("http://127.0.0.1:%d/json_rpc" % port, headers={"Content-Type": "application/json"},
                                 data=json.dumps({"jsonrpc": "2.0", "id": "0", "method": method, "params": params or {}}).encode())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=10) as r:
        return json.loads(r.read().decode())["result"]


def verify(a):
    text = CONFIG.read_text()
    s, e = network_block(text, a.network)
    tx = re.search(r'std::string const GENESIS_TX = "([0-9a-f]+)";', text[s:e]).group(1)
    expected_tx_hash = coinid.keccak256(bytes.fromhex(tx)).hex()   # version-1 transaction hash
    build = ROOT / a.build
    subprocess.run(["cmake", "--build", str(build), "--target", "daemon", "-j%d" % (os.cpu_count() or 2)], check=True,
                   stdout=subprocess.DEVNULL)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="genesis-"))
    port = RPC_PORT[a.network] + 1000      # avoid a node already running on this machine
    p = subprocess.Popen([str(build / "bin" / "opacrad")] + FLAG[a.network] + [
        "--offline", "--data-dir", str(tmp), "--rpc-bind-port", str(port), "--zmq-rpc-bind-port", str(port + 1),
        "--p2p-bind-port", str(port + 2), "--non-interactive", "--log-level", "0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        hdr = None
        for _ in range(90):
            try:
                hdr = rpc(port, "get_block_header_by_height", {"height": 0})["block_header"]
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        if not hdr:
            sys.exit("The node did not start.")
        blk = rpc(port, "get_block", {"height": 0})
        got = blk["miner_tx_hash"]
        print("Genesis block hash:  %s" % hdr["hash"])
        print("Genesis tx hash:     %s (node)  %s (recomputed)" % (got, expected_tx_hash))
        print("Genesis reward:      %d (expected %d)" % (hdr["reward"], GENESIS_REWARD))
        ok = got == expected_tx_hash and hdr["reward"] == GENESIS_REWARD and hdr["height"] == 0
        print("RESULT: %s" % ("GENESIS OK" if ok else "MISMATCH: do not launch"))
        line = '      ADD_CHECKPOINT2(0, "%s", "0x1");' % hdr["hash"]
        print("Checkpoint line:  %s" % line.strip())
        # enforcing nodes warn ("none could be read") while no DNS checkpoint record exists,
        # so launch day publishes the genesis as the first record on both domains
        print("DNS record:       %s TXT  0:%s  (on both domains, replacing any older record)" % (
            "checkpoints" if a.network == "mainnet" else "testpoints", hdr["hash"]))
        if ok and a.checkpoint:
            cp = CHECKPOINTS.read_text()
            marker = "    if (nettype == TESTNET)\n    {\n" if a.network == "testnet" else "    if (nettype == MAINNET)\n    {\n"
            if marker not in cp:
                sys.exit("Could not find the %s block in checkpoints.cpp; add the line by hand." % a.network)
            cp = cp.replace(marker, marker + line + "\n", 1)
            CHECKPOINTS.write_text(cp)
            print("Written into src/checkpoints/checkpoints.cpp")
        if not ok:
            sys.exit(1)
    finally:
        p.terminate()
        p.wait(timeout=60)
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("apply")
    x.add_argument("--network", choices=["mainnet", "testnet"], required=True)
    x.add_argument("--message", required=True)
    x.add_argument("--launch", required=True, help='launch time, UTC: "YYYY-MM-DD HH:MM"')
    v = sub.add_parser("verify")
    v.add_argument("--network", choices=["mainnet", "testnet"], required=True)
    v.add_argument("--build", default="build/portable")
    v.add_argument("--checkpoint", action="store_true", help="also write the genesis checkpoint into checkpoints.cpp")
    a = ap.parse_args()
    apply(a) if a.cmd == "apply" else verify(a)


if __name__ == "__main__":
    main()
