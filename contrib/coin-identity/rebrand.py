#!/usr/bin/env python3
"""
rebrand.py - rename the coin in user-visible strings and binary names.

Only the *contents of C/C++ string literals* and CMake OUTPUT_NAME values are
touched: identifiers, comments, macro names and consensus code are never
modified, so re-running the script cannot change consensus behaviour.

Usage
  python3 rebrand.py --from Monero --to Tacita --ticker-from XMR --ticker-to TCA [--root .] [--dry-run]

The first run was  Monero -> Tacita.  To rename Tacita later, run e.g.
  python3 rebrand.py --from Tacita --to Umbra --ticker-from TCA --ticker-to UMB
and then regenerate the chain identity (coinid.py) before launch.
"""
import argparse
import pathlib
import re
import sys

SOURCE_EXT = {".cpp", ".h", ".hpp", ".inl", ".in", ".c"}
# Hardware-wallet code must keep matching the device firmware, the LMDB helpers use
# MONERO_FIELD in diagnostics, mnemonic word lists must never change ("monero" is an
# Esperanto seed word), and dns_checks is a Monero-infrastructure debug tool.
# ALL-CAPS names (environment variables such as MONERO_RANDOMX_FULL_MEM) are kept.
EXCLUDE_DIRS = ("src/device", "src/device_trezor", "src/lmdb", "src/mnemonics", "src/debug_utilities/dns_checks.cpp")


def string_literal_spans(text):
    """Yield (start, end) of the *contents* of ordinary C/C++ string literals.
    Skips comments, char literals and raw strings (left untouched)."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "#" and (i == 0 or text.rfind("\n", 0, i) >= text.rfind("", 0, 0)) and re.match(r"#\s*include", text[i:i + 20]) \
                and text[text.rfind("\n", 0, i) + 1:i].strip() == "":
            j = text.find("\n", i)      # leave #include "..." paths alone
            i = n if j < 0 else j
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c == "R" and i + 1 < n and text[i + 1] == '"' and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
            m = re.match(r'R"([^()\\ ]{0,16})\(', text[i:])
            if not m:
                i += 1
                continue
            close = ")" + m.group(1) + '"'
            j = text.find(close, i + m.end())
            i = n if j < 0 else j + len(close)
        elif c == "'":
            j = i + 1
            while j < n and text[j] != "'":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\n":
                    break
                j += 2 if text[j] == "\\" else 1
            yield i + 1, j
            i = j + 1
        else:
            i += 1


def build_rules(frm, to, tick_from, tick_to):
    lf, lt = frm.lower(), to.lower()
    rules = []
    if frm == "Monero":
        rules += [
            ("BitMonero", to), ("bitmonero", lt), ("MoneroPulse", "DNS"),
            ("millinero", "milli" + lt[:3]), ("micronero", "micro" + lt[:3]),
            ("nanonero", "nano" + lt[:3]), ("piconero", "pico" + lt[:3]),
        ]
    rules += [
        ("oa1:" + tick_from.lower(), "oa1:" + tick_to.lower()),
        (tick_from, tick_to),
        (frm, to), (lf, lt),
    ]
    return rules


def apply_rules(s, rules):
    for a, b in rules:
        s = s.replace(a, b)
    return s


def rebrand_source(text, rules):
    out, last, changed = [], 0, 0
    for a, b in string_literal_spans(text):
        lit = text[a:b]
        new = apply_rules(lit, rules)
        if new != lit:
            changed += 1
        out.append(text[last:a])
        out.append(new)
        last = b
    out.append(text[last:])
    return "".join(out), changed


def rebrand_cmake(text, frm, to):
    pat = re.compile(r'(OUTPUT_NAME\s+")([^"]*)(")')
    lf, lt = frm.lower(), to.lower()
    return pat.sub(lambda m: m.group(1) + m.group(2).replace(lf, lt) + m.group(3), text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--ticker-from", required=True)
    ap.add_argument("--ticker-to", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    root = pathlib.Path(a.root).resolve()
    rules = build_rules(a.frm, a.to, a.ticker_from, a.ticker_to)
    total_files = total_lits = 0
    for path in sorted((root / "src").rglob("*")):
        rel = path.relative_to(root).as_posix()
        if not path.is_file() or any(rel.startswith(e) for e in EXCLUDE_DIRS):
            continue
        if path.suffix in SOURCE_EXT:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
            new, n = rebrand_source(text, rules)
        elif path.name == "CMakeLists.txt":
            text = path.read_text(encoding="utf-8")
            new, n = rebrand_cmake(text, a.frm, a.to), 0
            n = int(new != text)
        else:
            continue
        if new != text:
            total_files += 1
            total_lits += n
            print(f"{rel}: {n}")
            if not a.dry_run:
                path.write_text(new, encoding="utf-8", errors="surrogateescape")
    print(f"\n{total_files} files, {total_lits} string literals changed{' (dry run)' if a.dry_run else ''}")


if __name__ == "__main__":
    sys.exit(main())
