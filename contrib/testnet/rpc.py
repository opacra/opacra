"""Tiny JSON-RPC helpers for opacrad / opacra-wallet-rpc (stdlib only)."""
import http.client
import json
import os
import time
import urllib.parse
import urllib.request

ATOMIC = 10 ** 12


class RPCError(Exception):
    pass


def _post(url, payload, timeout=120):
    data = json.dumps(payload).encode()
    src = os.environ.get("OPACRA_RPC_SOURCE_IP")
    if src:
        # connect from a chosen loopback address (rehearsals: a node that blocks a misbehaving
        # 127.0.0.1 peer would otherwise block this client too)
        u = urllib.parse.urlsplit(url)
        c = http.client.HTTPConnection(u.hostname, u.port, timeout=timeout, source_address=(src, 0))
        c.request("POST", u.path, body=data, headers={"Content-Type": "application/json"})
        r = c.getresponse()
        return json.loads(r.read().decode())
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    # never route localhost RPC through a proxy
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


class Daemon:
    def __init__(self, port, host="127.0.0.1"):
        self.base = f"http://{host}:{port}"

    def rpc(self, method, **params):
        r = _post(self.base + "/json_rpc", {"jsonrpc": "2.0", "id": "0", "method": method, "params": params})
        if "error" in r:
            raise RPCError(f"{method}: {r['error']}")
        return r["result"]

    def other(self, path, **params):
        return _post(self.base + "/" + path, params)

    def info(self):
        return self.rpc("get_info")

    def height(self):
        return self.info()["height"]

    def header(self, height):
        return self.rpc("get_block_header_by_height", height=height)["block_header"]

    def headers(self, start, end):
        out = []
        while start <= end:
            stop = min(end, start + 999)
            out += self.rpc("get_block_headers_range", start_height=start, end_height=stop)["headers"]
            start = stop + 1
        return out

    def wait_ready(self, timeout=120):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                return self.info()
            except Exception:
                time.sleep(1)
        raise RPCError("daemon did not come up at " + self.base)


class Wallet:
    def __init__(self, port, host="127.0.0.1"):
        self.base = f"http://{host}:{port}"

    def rpc(self, method, timeout=300, **params):
        r = _post(self.base + "/json_rpc", {"jsonrpc": "2.0", "id": "0", "method": method, "params": params}, timeout=timeout)
        if "error" in r:
            raise RPCError(f"{method}: {r['error']}")
        return r["result"]

    def wait_ready(self, timeout=120):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                return self.rpc("get_version")
            except RPCError:
                return True
            except Exception:
                time.sleep(1)
        raise RPCError("wallet rpc did not come up at " + self.base)
