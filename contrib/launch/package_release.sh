#!/usr/bin/env bash
# Package a built tree: Linux binaries + launch kit, full source of the committed HEAD (with
# submodules and git history, ready to push to your own GitHub), and the Opacra patch series against Monero.
#   contrib/launch/package_release.sh [output-dir]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/dist}"
VERSION="$(grep -o 'DEF_MONERO_VERSION "[0-9.]*"' "$ROOT/src/version.cpp.in" | head -1 | cut -d'"' -f2)"
BASE_COMMIT="4f92268"   # Monero v0.18.5.1
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"   # absolute: later steps run from other folders (CI passes "dist")
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
# never ship Python byte-code caches (created when opacra-alert / opacra-audit were run or tested)
find "$STAGE/$BIN_DIR/launch-kit" -name __pycache__ -type d -prune -exec rm -rf {} +
# testers start here: one script does libraries, wallet and mining
mv "$STAGE/$BIN_DIR/launch-kit/start-testnet.sh" "$STAGE/$BIN_DIR/launch-kit/open-wallet.sh" "$STAGE/$BIN_DIR/"
cp LICENSE "$STAGE/$BIN_DIR/"
cat > "$STAGE/$BIN_DIR/README.txt" <<EOF
Opacra v$VERSION - Linux x86_64 binaries (built on Ubuntu 24.04, dynamically linked)

  start-testnet.sh    join the public testnet: installs libraries, creates your wallet, mines
  open-wallet.sh      your testnet wallet (balance, transfer)
  opacrad             full node / miner
  opacra-wallet-cli   command-line wallet
  opacra-wallet-rpc   wallet JSON-RPC server (same API as monero-wallet-rpc)
  launch-kit/         systemd unit, example config, seed node setup, alerts, chain audit, Dockerfile

Mining threads: start-testnet.sh uses a quarter of the CPU threads. To use N threads:
  MINE_THREADS=N ./start-testnet.sh
"No incoming connections" or "No other node has connected to this one yet" is normal on a
home connection behind a router: mining and syncing work as usual.
start-testnet.sh follows the project's emergency checkpoints (DNSSEC-signed records under
opacra.org and opacra.com, which must agree), used only to stop an attack and all listed on
opacra.org. To run without them, remove --enforce-dns-checkpointing from start-testnet.sh.
When the wallet says new coins have arrived, type  refresh  and enter your password when the
wallet asks for it (never after the [wallet ...]: prompt).

Upgrading from an earlier version: unpack the new version, then copy testnet-wallet,
testnet-wallet.keys and testnet-wallet.address.txt from the old folder into the new one
before running start-testnet.sh. The blockchain (~/.opacra) is not downloaded again.

Runtime packages on Ubuntu 24.04:
  sudo apt install libboost-chrono1.83.0t64 libboost-filesystem1.83.0 libboost-program-options1.83.0 \\
    libboost-serialization1.83.0 libboost-thread1.83.0 libhidapi-libusb0 libreadline8t64 libsodium23 \\
    libssl3t64 libunbound8 libusb-1.0-0 libzmq5
Other systems: build from source (README.md in the source archive).

This is a development build with the development chain identity. Do not use it for a
public launch; follow docs/LAUNCH_CHECKLIST.md.
EOF
(cd "$STAGE/$BIN_DIR" && sha256sum opacrad opacra-wallet-cli opacra-wallet-rpc > SHA256SUMS)
# owned by root in the archive, whoever built it
TAR_OWNER=(--owner=0 --group=0 --numeric-owner)
tar -C "$STAGE" "${TAR_OWNER[@]}" -czf "$OUT/$BIN_DIR.tar.gz" "$BIN_DIR"
rm -rf "$STAGE"

# 2. source: a clean clone of the committed tree (HEAD) with its history and submodules, so
#    nothing untracked, ignored or local can slip in. Commit before packaging.
SRC_DIR="opacra-v$VERSION-source"
SRC_STAGE="$(mktemp -d)"
git -C "$ROOT" diff --quiet HEAD -- || echo "Note: uncommitted changes are not in the source archives (HEAD only)" >&2
git clone -q --no-local "$ROOT" "$SRC_STAGE/$SRC_DIR"
(
  cd "$SRC_STAGE/$SRC_DIR"
  git checkout -q --detach "$(git -C "$ROOT" rev-parse HEAD)"
  # submodules from this checkout's own copies (no download), then back to their public URLs
  git submodule init -q
  git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | while read -r key path; do
    name="${key#submodule.}"; name="${name%.path}"
    git config "submodule.$name.url" "$ROOT/$path"
  done
  git -c protocol.file.allow=always submodule update -q
  git submodule sync -q
  git remote set-url origin https://github.com/opacra/opacra.git
)
tar -C "$SRC_STAGE" "${TAR_OWNER[@]}" -czf "$OUT/$SRC_DIR.tar.gz" "$SRC_DIR"

# 2b. the same source without git metadata, xz-compressed (smaller; builds the same)
tar -C "$SRC_STAGE" "${TAR_OWNER[@]}" --exclude='.git' -cJf "$OUT/$SRC_DIR-nogit.tar.xz" "$SRC_DIR"
rm -rf "$SRC_STAGE"

# 3. patch series against upstream Monero
PATCH_DIR="$(mktemp -d)/opacra-patches-vs-monero-v0.18.5.1"
mkdir -p "$PATCH_DIR"
git format-patch -q "$BASE_COMMIT"..HEAD -o "$PATCH_DIR"
git diff --stat "$BASE_COMMIT"..HEAD -- src > "$PATCH_DIR/DIFFSTAT-src.txt"
(cd "$(dirname "$PATCH_DIR")" && tar "${TAR_OWNER[@]}" -czf "$OUT/opacra-patches-vs-monero-v0.18.5.1.tar.gz" "$(basename "$PATCH_DIR")")

(cd "$OUT" && sha256sum ./*.tar.gz ./*.tar.xz > SHA256SUMS.txt)
ls -la "$OUT"
