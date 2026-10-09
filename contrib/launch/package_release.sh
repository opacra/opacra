#!/usr/bin/env bash
# Package a built tree: Linux binaries + launch kit, full source (with submodules and git
# history, ready to push to your own GitHub), and the Opacra patch series against Monero.
#   contrib/launch/package_release.sh [output-dir]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/dist}"
VERSION="$(grep -o 'DEF_MONERO_VERSION "[0-9.]*"' "$ROOT/src/version.cpp.in" | head -1 | cut -d'"' -f2)"
BASE_COMMIT="4f92268"   # Monero v0.18.5.1
mkdir -p "$OUT"
cd "$ROOT"

# 1. binaries (dynamically linked, built on Ubuntu 24.04 x86_64). They must come from a
#    portable build (cmake -DARCH=x86-64); the default -march=native build only runs
#    reliably on the CPU it was compiled on.
BUILD_DIR="${BUILD_DIR:-build/portable}"
grep -Eq '^ARCH:[A-Z]+=x86-64$' "$BUILD_DIR/CMakeCache.txt" || { echo "$BUILD_DIR is not a portable (-DARCH=x86-64) build" >&2; exit 1; }
BIN_DIR="opacra-v$VERSION-linux-x64"
STAGE="$(mktemp -d)"
mkdir -p "$STAGE/$BIN_DIR"
cp "$BUILD_DIR/bin/opacrad" "$BUILD_DIR/bin/opacra-wallet-cli" "$BUILD_DIR/bin/opacra-wallet-rpc" "$STAGE/$BIN_DIR/"
strip "$STAGE/$BIN_DIR/"* 2>/dev/null || true
cp -r contrib/launch "$STAGE/$BIN_DIR/launch-kit"
rm -f "$STAGE/$BIN_DIR/launch-kit/package_release.sh"
cp LICENSE "$STAGE/$BIN_DIR/"
cat > "$STAGE/$BIN_DIR/README.txt" <<EOF
Opacra v$VERSION - Linux x86_64 binaries (built on Ubuntu 24.04, dynamically linked)

  opacrad             full node / miner
  opacra-wallet-cli   command-line wallet
  opacra-wallet-rpc   wallet JSON-RPC server (same API as monero-wallet-rpc)
  launch-kit/         systemd unit, example config, seed node setup, Dockerfile

Runtime packages on Ubuntu 24.04:
  sudo apt install libboost-chrono1.83.0t64 libboost-filesystem1.83.0 libboost-program-options1.83.0 \\
    libboost-serialization1.83.0 libboost-thread1.83.0 libhidapi-libusb0 libreadline8t64 libsodium23 \\
    libssl3t64 libunbound8 libusb-1.0-0 libzmq5
Other systems: build from source (README.md in the source archive).

This is a development build with the development chain identity. Do not use it for a
public launch; follow docs/LAUNCH_CHECKLIST.md.
EOF
(cd "$STAGE/$BIN_DIR" && sha256sum opacrad opacra-wallet-cli opacra-wallet-rpc > SHA256SUMS)
tar -C "$STAGE" -czf "$OUT/$BIN_DIR.tar.gz" "$BIN_DIR"
rm -rf "$STAGE"

# 2. source with submodules and git history (no build output). The Windows build leaves
#    gigabytes of downloaded and built libraries in contrib/depends; leave those out too.
SRC_DIR="opacra-v$VERSION-source"
R="$(basename "$ROOT")"
DEPENDS_EXCLUDES=()
for d in SDKs work built sources config.site 'x86_64*' 'i686*' 'mips*' 'arm*' 'aarch64*'; do
  DEPENDS_EXCLUDES+=(--exclude="$R/contrib/depends/$d")
done
tar -C "$(dirname "$ROOT")" --exclude="$(basename "$ROOT")/build" --exclude="$(basename "$ROOT")/dist" \
    --exclude='__pycache__' "${DEPENDS_EXCLUDES[@]}" --transform "s,^$(basename "$ROOT"),$SRC_DIR," \
    -czf "$OUT/$SRC_DIR.tar.gz" "$(basename "$ROOT")"

# 2b. the same source without git metadata, xz-compressed (smaller; builds the same)
tar -C "$(dirname "$ROOT")" --exclude="$(basename "$ROOT")/build" --exclude="$(basename "$ROOT")/dist" \
    --exclude='__pycache__' --exclude='.git' "${DEPENDS_EXCLUDES[@]}" --transform "s,^$(basename "$ROOT"),$SRC_DIR," \
    -cJf "$OUT/$SRC_DIR-nogit.tar.xz" "$(basename "$ROOT")"

# 3. patch series against upstream Monero
PATCH_DIR="$(mktemp -d)/opacra-patches-vs-monero-v0.18.5.1"
mkdir -p "$PATCH_DIR"
git format-patch -q "$BASE_COMMIT"..HEAD -o "$PATCH_DIR"
git diff --stat "$BASE_COMMIT"..HEAD -- src > "$PATCH_DIR/DIFFSTAT-src.txt"
(cd "$(dirname "$PATCH_DIR")" && tar -czf "$OUT/opacra-patches-vs-monero-v0.18.5.1.tar.gz" "$(basename "$PATCH_DIR")")

(cd "$OUT" && sha256sum ./*.tar.gz ./*.tar.xz > SHA256SUMS.txt)
ls -la "$OUT"
