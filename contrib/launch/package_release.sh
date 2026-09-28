#!/usr/bin/env bash
# Package a built tree: Linux binaries + launch kit, full source (with submodules and git
# history, ready to push to your own GitHub), and the Tacita patch series against Monero.
#   contrib/launch/package_release.sh [output-dir]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/dist}"
VERSION="$(grep -o 'DEF_MONERO_VERSION "[^"]*"' "$ROOT/src/version.cpp.in" | cut -d'"' -f2)"
BASE_COMMIT="4f92268"   # Monero v0.18.5.1
mkdir -p "$OUT"
cd "$ROOT"

# 1. binaries (dynamically linked, built on Ubuntu 24.04 x86_64)
BIN_DIR="tacita-v$VERSION-linux-x64"
STAGE="$(mktemp -d)"
mkdir -p "$STAGE/$BIN_DIR"
cp build/release/bin/tacitad build/release/bin/tacita-wallet-cli build/release/bin/tacita-wallet-rpc "$STAGE/$BIN_DIR/"
strip "$STAGE/$BIN_DIR/"* 2>/dev/null || true
cp -r contrib/launch "$STAGE/$BIN_DIR/launch-kit"
rm -f "$STAGE/$BIN_DIR/launch-kit/package_release.sh"
cp LICENSE "$STAGE/$BIN_DIR/"
cat > "$STAGE/$BIN_DIR/README.txt" <<EOF
Tacita v$VERSION - Linux x86_64 binaries (built on Ubuntu 24.04, dynamically linked)

  tacitad             full node / miner
  tacita-wallet-cli   command-line wallet
  tacita-wallet-rpc   wallet JSON-RPC server (same API as monero-wallet-rpc)
  launch-kit/         systemd unit, example config, seed node setup, Dockerfile

Runtime packages on Ubuntu 24.04:
  sudo apt install libboost-chrono1.83.0t64 libboost-filesystem1.83.0 libboost-program-options1.83.0 \\
    libboost-serialization1.83.0 libboost-thread1.83.0 libhidapi-libusb0 libreadline8t64 libsodium23 \\
    libssl3t64 libunbound8 libusb-1.0-0 libzmq5
Other systems: build from source (README.md in the source archive).

This is a development build with the development chain identity. Do not use it for a
public launch; follow docs/LAUNCH_CHECKLIST.md.
EOF
(cd "$STAGE" && sha256sum "$BIN_DIR"/tacitad "$BIN_DIR"/tacita-wallet-cli "$BIN_DIR"/tacita-wallet-rpc > "$BIN_DIR/SHA256SUMS")
tar -C "$STAGE" -czf "$OUT/$BIN_DIR.tar.gz" "$BIN_DIR"
rm -rf "$STAGE"

# 2. source with submodules and git history (no build output)
SRC_DIR="tacita-v$VERSION-source"
tar -C "$(dirname "$ROOT")" --exclude="$(basename "$ROOT")/build" --exclude="$(basename "$ROOT")/dist" \
    --exclude='__pycache__' --transform "s,^$(basename "$ROOT"),$SRC_DIR," \
    -czf "$OUT/$SRC_DIR.tar.gz" "$(basename "$ROOT")"

# 3. patch series against upstream Monero
PATCH_DIR="$(mktemp -d)/tacita-patches-vs-monero-v0.18.5.1"
mkdir -p "$PATCH_DIR"
git format-patch -q "$BASE_COMMIT"..HEAD -o "$PATCH_DIR"
git diff --stat "$BASE_COMMIT"..HEAD -- src > "$PATCH_DIR/DIFFSTAT-src.txt"
(cd "$(dirname "$PATCH_DIR")" && tar -czf "$OUT/tacita-patches-vs-monero-v0.18.5.1.tar.gz" "$(basename "$PATCH_DIR")")

(cd "$OUT" && sha256sum ./*.tar.gz > SHA256SUMS.txt)
ls -la "$OUT"
