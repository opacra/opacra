#!/usr/bin/env python3
"""The seed alert must not report a young chain as "much too slow" (27 Oct 2026, testnet 3 launch).

Loads contrib/launch/opacra-alert with the node, clock and phone simulated, and checks the
block-rate handler: a chain younger than the window, or with no block 1 yet, raises no alert;
an old chain, or a node that does not answer, still does.

  python3 contrib/testnet/alert_rate_test.py [path to opacra-alert]
Standard library only. Exit code 0 when every check passes.
"""
import importlib.machinery
import importlib.util
import pathlib
import sys

path = sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path(__file__).resolve().parent.parent / "launch" / "opacra-alert")
loader = importlib.machinery.SourceFileLoader("opacra_alert", path)
spec = importlib.util.spec_from_loader("opacra_alert", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)

T = 1_800_000_000
sent = []


class FakeState(dict):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


store = FakeState()
m.State = lambda: store
m.now = lambda: T
m.log = lambda msg: None
m.send = lambda title, body, **k: sent.append(title)
m.C["RATE_PERSIST_MINUTES"] = "0"   # judge at once, no waiting period or cooldown
m.C["RATE_COOLDOWN_MINUTES"] = "0"


def case(name, rpc, expect_alert):
    sent.clear()
    store.clear()
    m.rpc = rpc
    m.on_block_rate("90", "93", "180")   # launch evening: 93 blocks in a 90-minute window
    ok = bool(sent) == expect_alert
    print(("PASS " if ok else "FAIL ") + name + ("  (sent: %s)" % ", ".join(sent) if sent else ""))
    return ok


def header(age):
    return lambda method, params=None: {"block_header": {"timestamp": T - age}}


def no_block(method, params=None):
    raise RuntimeError({"code": -2, "message": "no block at that height"})


def down(method, params=None):
    raise OSError("connection refused")


results = [
    case("chain 38 minutes old: no alert", header(38 * 60), False),
    case("no block 1 yet: no alert", no_block, False),
    case("chain 3 hours old: alert", header(3 * 3600), True),
    case("node not answering: alert as before", down, True),
]
print("ALL CHECKS PASSED" if all(results) else "SOME CHECKS FAILED")
sys.exit(0 if all(results) else 1)
