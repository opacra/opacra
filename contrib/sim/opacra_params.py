#!/usr/bin/env python3
"""
Reference implementations of Opacra's consensus arithmetic, bit-for-bit
identical to the C++ (src/cryptonote_basic/difficulty.cpp and
cryptonote_basic_impl.cpp).  Used to

  * simulate difficulty behaviour (LWMA-1) under hashrate shocks,
  * print the emission schedule,
  * verify a live chain: every block's difficulty and reward is recomputed
    from its predecessors and compared with what the nodes accepted.
"""
import math
import random

# ---- consensus constants (keep in sync with src/cryptonote_config.h) ----
T = 30                              # DIFFICULTY_TARGET_V2
N = 60                              # DIFFICULTY_WINDOW
STARTUP_BLOCKS = 12                 # DIFFICULTY_STARTUP_BLOCKS
STARTUP_GUESS = 10000               # DIFFICULTY_STARTUP_GUESS
COIN = 10 ** 12
MONEY_SUPPLY = 10_000_000 * COIN
EMISSION_SPEED_FACTOR = 22          # EMISSION_SPEED_FACTOR_PER_BLOCK
TAIL = 50_000_000_000               # TAIL_EMISSION_REWARD (0.05)
SLOW_START = 20160                  # SLOW_START_BLOCKS
BLOCKS_PER_YEAR = 365.25 * 86400 / T


def lwma_next_difficulty(timestamps, cum_diffs, target=T, window=N):
    """Timestamps / cumulative difficulties of the most recent blocks, oldest first,
    genesis excluded (exactly what Blockchain passes to next_difficulty)."""
    assert len(timestamps) == len(cum_diffs)
    timestamps = timestamps[-(window + 1):]
    cum_diffs = cum_diffs[-(window + 1):]
    length = len(timestamps)
    if length == 0:
        return 1
    if length < STARTUP_BLOCKS:
        return STARTUP_GUESS
    n = length - 1
    L = 0
    prev = timestamps[0]
    for i in range(1, n + 1):
        this = timestamps[i] if timestamps[i] > prev else prev + 1
        L += i * min(6 * target, this - prev)
        prev = this
    L = max(L, n * n * target // 20)
    total_work = cum_diffs[n] - cum_diffs[0]
    nxt = total_work * target * (n + 1) * 99 // (200 * L)
    return max(nxt, 1)


def base_reward(already_generated):
    already_generated = min(already_generated, MONEY_SUPPLY)
    r = (MONEY_SUPPLY - already_generated) >> EMISSION_SPEED_FACTOR
    return max(r, TAIL)


def slow_start(reward, height):
    if height == 0 or height >= SLOW_START:
        return reward
    return reward * height // SLOW_START


def block_reward(already_generated, height):
    """Reward for an empty-ish block (no size penalty) at `height`."""
    return slow_start(base_reward(already_generated), height)


# --------------------------------------------------------------------------- simulation
def simulate(hashrate_fn, blocks=3000, seed=1, start_time=0):
    """hashrate_fn(height) -> hashes/second.  Returns list of (height, ts, diff, solvetime)."""
    rnd = random.Random(seed)
    ts, cds = [], []          # excluding genesis
    t = start_time
    cum = 1                   # genesis cumulative difficulty
    out = []
    for h in range(1, blocks + 1):
        d = lwma_next_difficulty(ts, cds)
        hr = hashrate_fn(h)
        solve = rnd.expovariate(hr / d)  # expected d / hr seconds
        t += solve
        ts.append(int(t))
        cum += d
        cds.append(cum)
        out.append((h, int(t), d, solve))
    return out


def emission_at(height):
    """Total generated (incl. genesis) before the block at `height`."""
    gen = base_reward(0)
    for h in range(1, height):
        gen = min(gen + block_reward(gen, h), 2 ** 64 - 1)
    return gen


def emission_table(years=(1, 2, 3, 4, 5, 10, 15, 20, 30)):
    """Coins emitted after N years (closed-form per block, exact integer loop for slow start)."""
    gen = base_reward(0)  # genesis output (burned)
    rows = []
    h = 1
    targets = {int(y * BLOCKS_PER_YEAR): y for y in years}
    last = max(targets)
    tail_start = None
    while h <= last:
        r = block_reward(gen, h)
        if tail_start is None and base_reward(gen) == TAIL:
            tail_start = h
        gen = min(gen + r, 2 ** 64 - 1)  # the daemon keeps counting past MONEY_SUPPLY (tail emission)
        if h in targets:
            rows.append((targets[h], gen))
        h += 1
    return rows, tail_start


if __name__ == "__main__":
    print("Genesis reward: %.12f OPCA" % (base_reward(0) / COIN))
    print("First full-reward block (%d): %.12f OPCA" % (SLOW_START, block_reward(emission_at(SLOW_START), SLOW_START) / COIN))
    print("Reward at height 1 (slow start): %.9f OPCA" % (block_reward(base_reward(0), 1) / COIN))
    print("Half-life of remaining main supply: %.2f years" % (2 ** EMISSION_SPEED_FACTOR * math.log(2) / BLOCKS_PER_YEAR))
