#!/usr/bin/env python3
"""Turn a functional_test.py report.json into docs/TEST_REPORT.md and a chart.

  python3 contrib/testnet/make_report.py ~/tacita-localnet/report.json
"""
import json
import pathlib
import statistics as st
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
report = json.loads(pathlib.Path(sys.argv[1]).read_text())
hs = report["headers"]

# ---- chart: two panels on the same x (block height); never a dual axis
SURFACE, INK, QUIET, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
heights = [h["h"] for h in hs]
diffs = [h["d"] for h in hs]
solve = [b["t"] - a["t"] for a, b in zip(hs, hs[1:])]
solve_h = heights[1:]
roll = [st.mean(solve[max(0, i - 19):i + 1]) for i in range(len(solve))]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.4), sharex=True, facecolor=SURFACE)
for ax in (ax1, ax2):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(QUIET)
    ax.tick_params(colors=QUIET, length=0)

ax1.plot(heights, diffs, color=SERIES, linewidth=2)
ax1.set_title("Difficulty found the network's hash rate within about 15 blocks", loc="left",
              color=INK, fontsize=12, fontweight="bold", pad=22)
ax1.text(0, 1.02, "Block difficulty (LWMA-1, N = 60)", transform=ax1.transAxes, color=QUIET, fontsize=9.5)
ax1.set_ylim(0, max(diffs) * 1.15)
ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: "0" if v == 0 else f"{v/1000:.0f}k"))

ax2.scatter(solve_h, solve, s=10, color=QUIET, alpha=0.35, linewidths=0, label="Each block")
ax2.plot(solve_h, roll, color=SERIES, linewidth=2, label="20-block average")
ax2.axhline(30, color=QUIET, linestyle=(0, (4, 4)), linewidth=1)
ax2.text(1.01, 30, "30 s\ntarget", transform=ax2.get_yaxis_transform(), color=QUIET, fontsize=9, ha="left", va="center")
split = report.get("reorg", {}).get("split_height")
if split:
    for ax in (ax1, ax2):
        ax.axvspan(split, heights[-1] + 0.5, color=GRID, alpha=0.6, linewidth=0)
    ax1.text(split + 0.5, ax1.get_ylim()[1] * 0.97, "split test:\nhalf hash rate", color=QUIET, fontsize=8.5, ha="left", va="top")
mean_after = report.get("final_stats_after_startup", {}).get("mean_solvetime")
ax2.set_title(f"Blocks averaged {mean_after:.1f} s after the startup phase", loc="left",
              color=INK, fontsize=12, fontweight="bold", pad=22)
ax2.text(0, 1.02, "Seconds between blocks", transform=ax2.transAxes, color=QUIET, fontsize=9.5)
ax2.set_ylim(0, min(max(solve) * 1.05, 240))
ax2.set_xlabel("Block height", color=QUIET)
leg = ax2.legend(loc="upper left", frameon=False, fontsize=9, ncol=2)
for t in leg.get_texts():
    t.set_color(QUIET)
fig.tight_layout(h_pad=2.5, rect=(0, 0, 0.96, 1))
img = ROOT / "docs" / "images" / "test-network.png"
img.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(img, dpi=150, facecolor=SURFACE)

# ---- markdown
checks = report["checks"]
passed = sum(c["ok"] for c in checks)
tx = report.get("tx", {})
fs = report.get("final_stats_after_startup", {})
lines = [
    "# Test report: private 3-node network",
    "",
    f"Run {report['started']} to {report.get('finished', '?')} with `contrib/testnet/functional_test.py` on a 2-vCPU cloud VM "
    "(3 nodes on one machine, mainnet consensus rules, isolated from the internet).",
    "",
    f"**{passed} of {len(checks)} checks passed.**",
    "",
    "![Difficulty and block times on the test network](images/test-network.png)",
    "",
    "## Key numbers",
    "",
    "| Measure | Result |",
    "| --- | --- |",
    f"| Blocks mined | {report['replay']['blocks']} (heights 0 to {report['replay']['blocks'] - 1}) |",
    f"| Mean block time after the 30-block startup | {fs.get('mean_solvetime')} s (target 30 s) |",
    f"| Median block time after startup | {fs.get('median_solvetime')} s |",
    f"| Test transaction | {tx.get('inputs')} inputs, {tx.get('outputs')} outputs, {tx.get('weight_bytes')} bytes, fee {tx.get('fee', 0) / 1e12:.8f} TCA |",
    f"| Ring size of every input | {sorted(set(tx.get('ring_sizes', [])))} |",
    f"| Send to spendable (10 confirmations) | {report.get('seconds_to_spendable')} s |",
    f"| Chain split | node 2 isolated at height {report['reorg']['split_height']}; all nodes re-converged at heights {report['reorg']['converged_heights']} |",
    f"| Consensus replay | every block's difficulty and reward recomputed in Python; mismatches: {len(report['replay']['mismatches'])} |",
    "",
    "## Checks",
    "",
    "| Check | Result | Detail |",
    "| --- | --- | --- |",
]
for c in checks:
    lines.append(f"| {c['name']} | {'pass' if c['ok'] else '**FAIL**'} | {c['detail'].replace('|', '/')} |")
lines += [
    "",
    "## What this does not cover",
    "",
    "- Behaviour under real-world latency, many peers, or adversarial miners (use the public testnet).",
    "- Blocks above the median weight (the slow-start size cap is covered by `tests/tacita`).",
    "- Hardware wallets and the GUI (not part of this fork).",
    "",
    f"Genesis hash: `{report['genesis_hash']}`",
]
(ROOT / "docs" / "TEST_REPORT.md").write_text("\n".join(lines) + "\n")
print(f"wrote {ROOT / 'docs' / 'TEST_REPORT.md'} and {img}")
