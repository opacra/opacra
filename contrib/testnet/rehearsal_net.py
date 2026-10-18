#!/usr/bin/env python3
"""Private network for the attack-and-recovery rehearsal (see attack_rehearsal.py).

Nodes run Opacra's real mainnet rules on 127.0.0.1 only, each with its own data folder
under $DATA. Commands (one per call, so each step can be inspected):

  rehearsal_net.py start NAME P2P RPC [--ip 127.0.0.N] [--peer IP:P2P ...] [--notify] [--miner-mem] [--offline]
  rehearsal_net.py stop NAME
  rehearsal_net.py mine NAME ADDRESS THREADS | stopmine NAME
  rehearsal_net.py info NAME [NAME ...]
  rehearsal_net.py hash NAME HEIGHT
  rehearsal_net.py checkpoint NAME HEIGHT HASH     (writes NAME's checkpoints.json)
  rehearsal_net.py alerts-server PORT              (records ntfy-style POSTs to $DATA/alerts.jsonl)

DNS checkpoints are left enabled (the mainnet domains have no records), because Opacra
only reads checkpoints.json while checkpoint updates are enabled.
"""
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rpc import Daemon  # noqa: E402

BIN = pathlib.Path(os.environ.get("BIN", HERE.parent.parent / "build" / "portable" / "bin"))
DATA = pathlib.Path(os.environ["DATA"])
PORTS = DATA / "ports.json"


def ports():
    return json.loads(PORTS.read_text()) if PORTS.exists() else {}


def daemon(name):
    e = ports()[name]
    return Daemon(e["rpc"], host=e.get("ip", "127.0.0.1"))


def start(name, p2p, rpc, peers, notify, miner_mem, offline=False, ip="127.0.0.1"):
    d = DATA / name
    d.mkdir(parents=True, exist_ok=True)
    args = [str(BIN / "opacrad"), "--data-dir", str(d),
            "--p2p-bind-ip", ip, "--p2p-bind-port", str(p2p),
            "--rpc-bind-ip", ip, "--confirm-external-bind", "--rpc-bind-port", str(rpc), "--zmq-rpc-bind-port", str(rpc + 1),
            "--no-igd", "--allow-local-ip", "--check-updates", "disabled", "--log-level", "1",
            "--non-interactive", "--out-peers", "8"]
    # an isolated node gets an exclusive peer that does not exist, so it connects to nobody
    # peers are "IP:PORT"; each node has its own loopback address, so a ban hits one node only
    for p in (peers or ["127.0.0.1:1"]):
        args += ["--add-exclusive-node", p]
    if offline:
        args += ["--offline"]  # counts as synchronized, so it can mine with no peers
    if notify:
        args += ["--reorg-notify", "%s reorg %%s %%h %%n %%d" % (DATA / "alert-wrapper.sh")]
    env = dict(os.environ)
    env.pop("HTTPS_PROXY", None), env.pop("HTTP_PROXY", None)
    if miner_mem:
        env["MONERO_RANDOMX_FULL_MEM"] = "1"
    log = open(d / "stdout.log", "ab")
    p = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    (d / "pid").write_text(str(p.pid))
    pr = ports()
    pr[name] = {"p2p": p2p, "rpc": rpc, "ip": ip}
    PORTS.write_text(json.dumps(pr))
    Daemon(rpc, host=ip).wait_ready(timeout=180)
    print("%s up: pid %d, %s p2p %d rpc %d, peers %s" % (name, p.pid, ip, p2p, rpc, peers or "none"))


def stop(name):
    pidf = DATA / name / "pid"
    if not pidf.exists():
        print(name, "not running")
        return
    pid = int(pidf.read_text())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(120):
        try:
            os.kill(pid, 0)
            time.sleep(1)
        except ProcessLookupError:
            break
    pidf.unlink()
    print(name, "stopped")


def info(names):
    for n in names:
        try:
            i = daemon(n).info()
            print("%-9s height %5d  diff %8d  cumdiff %12d  peers %d  top %s" % (
                n, i["height"], i["difficulty"], int(i.get("cumulative_difficulty", 0)),
                i["outgoing_connections_count"] + i["incoming_connections_count"], i["top_block_hash"][:16]))
        except Exception as e:  # noqa: BLE001
            print("%-9s down (%s)" % (n, e))


def alerts_server(port):
    out = DATA / "alerts.jsonl"

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8", "replace")
            rec = {"t": time.strftime("%H:%M:%S"), "path": self.path, "title": self.headers.get("Title", ""),
                   "priority": self.headers.get("Priority", ""), "body": body}
            with open(out, "a") as f:
                f.write(json.dumps(rec) + "\n")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):
            pass

    HTTPServer(("127.0.0.1", port), H).serve_forever()


def main(a):
    cmd = a[0]
    if cmd == "start":
        name, p2p, rpc = a[1], int(a[2]), int(a[3])
        peers = [a[i + 1] for i, x in enumerate(a) if x == "--peer"]
        ip = a[a.index("--ip") + 1] if "--ip" in a else "127.0.0.1"
        start(name, p2p, rpc, peers, "--notify" in a, "--miner-mem" in a, "--offline" in a, ip)
    elif cmd == "stop":
        stop(a[1])
    elif cmd == "mine":
        r = daemon(a[1]).other("start_mining", miner_address=a[2], threads_count=int(a[3]),
                               do_background_mining=False, ignore_battery=True)
        print(a[1], "mining:", r.get("status"))
    elif cmd == "stopmine":
        print(a[1], "stop mining:", daemon(a[1]).other("stop_mining").get("status"))
    elif cmd == "info":
        info(a[1:])
    elif cmd == "hash":
        print(daemon(a[1]).header(int(a[2]))["hash"])
    elif cmd == "checkpoint":
        (DATA / a[1] / "checkpoints.json").write_text(json.dumps(
            {"hashlines": [{"height": int(a[2]), "hash": a[3]}]}))
        print("checkpoint for", a[1], "at", a[2], a[3][:16])
    elif cmd == "alerts-server":
        alerts_server(int(a[1]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
