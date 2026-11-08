#!/usr/bin/env python3
"""Difficulty fuzz test: the node's real next_difficulty() against the Python model.

Generates random honest and hostile block histories (timestamps that stall, repeat, run
backwards, jump far ahead or sit at the edges of uint64; difficulties from 1 to near
2^127; window lengths from 0 to past N+1), runs each through
build/*/bin/opacra_difficulty_fuzz (the C++ consensus function) and through
opacra_params.lwma_next_difficulty (independent model), and reports any difference.

  make opacra_difficulty_fuzz            # in the build directory
  python3 contrib/sim/difficulty_fuzz.py [--cases 200000] [--seed 1] [--bin PATH]

Exit code 0 = every case agrees. Histories the node can never see (cumulative difficulty
going down) are not generated; timestamps are unrestricted, because the function must
agree with the model on any input even though the node also enforces time rules.
"""
import argparse
import pathlib
import random
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import opacra_params as P  # noqa: E402

U64 = (1 << 64) - 1
T = P.T


def find_bin():
    for d in ("portable", "release", "debug"):
        p = HERE.parent.parent / "build" / d / "bin" / "opacra_difficulty_fuzz"
        if p.exists():
            return p
    sys.exit("opacra_difficulty_fuzz not built: run  make opacra_difficulty_fuzz  in the build directory")


def gen_timestamps(rng, n, kind):
    t = rng.choice([1_791_000_000, 0, 1, rng.randrange(1 << 40), U64 - 10_000_000])
    out = []
    for _ in range(n):
        if kind == "honest":
            step = max(1, int(rng.expovariate(1 / T)))
        elif kind == "stall":
            step = rng.choice([0, 0, 0, 1])
        elif kind == "backwards":
            step = rng.randint(-20 * T, 3 * T)
        elif kind == "jumps":
            step = rng.choice([1, T, 6 * T, 6 * T + 1, 3600, 86_400, rng.randrange(1 << 32)])
        elif kind == "selfish":          # alternate max-future and min-past stamps
            step = rng.choice([180, -170])
        else:                             # "chaos"
            step = rng.randint(-(1 << 20), 1 << 20)
        t = min(max(t + step, 0), U64 - 100_000)   # stay where the node's +1 cannot wrap
        out.append(t)
    return out


def gen_cumulative(rng, n, kind):
    base = rng.choice([0, 1, 10_000, rng.randrange(1 << 64), rng.randrange(1 << 100), (1 << 127)])
    out, c = [], base
    for _ in range(n):
        if kind == "steady":
            d = rng.randint(9_000, 11_000)
        elif kind == "spiky":
            d = rng.choice([1, 10_000, 10_000_000, rng.randrange(1 << 48)])
        elif kind == "flat":              # zero work between blocks
            d = rng.choice([0, 0, 1])
        else:                              # "huge"
            d = rng.randrange(1 << 96)
        c = min(c + d, (1 << 128) - 1)
        out.append(c)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bin", type=pathlib.Path)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    exe = a.bin or find_bin()

    cases = []
    tkinds = ["honest", "stall", "backwards", "jumps", "selfish", "chaos"]
    ckinds = ["steady", "spiky", "flat", "huge"]
    for _ in range(a.cases):
        n = rng.choice([0, 1, 2, 11, 12, 13, 60, 61, 62, rng.randint(0, 90)])
        tk, ck = rng.choice(tkinds), rng.choice(ckinds)
        cases.append((tk, ck, gen_timestamps(rng, n, tk), gen_cumulative(rng, n, ck)))

    stdin = "".join(f"{T} {len(ts)} {' '.join(map(str, ts))} {' '.join(map(str, cs))}\n"
                    for _, _, ts, cs in cases)
    res = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, check=True)
    got = res.stdout.split("\n")[:-1]
    if len(got) != len(cases):
        sys.exit(f"harness returned {len(got)} results for {len(cases)} cases")

    bad, counts = [], {}
    for (tk, ck, ts, cs), out in zip(cases, got):
        want = P.lwma_next_difficulty(ts, cs)
        counts[tk] = counts.get(tk, 0) + 1
        if out != str(want) or int(out) < 1:
            bad.append((tk, ck, len(ts), out, want))

    print(f"{len(cases)} cases (seed {a.seed}), by timestamp pattern: "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    if bad:
        print(f"FAIL: {len(bad)} cases differ, first 10 (pattern, difficulty, length, node, model):")
        for b in bad[:10]:
            print("  ", b)
        return 1
    print("PASS: the node and the model agree on every case; every result is at least 1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
