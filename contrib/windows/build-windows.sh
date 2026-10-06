#!/usr/bin/env bash
# Builds Opacra for 64-bit Windows on Ubuntu 24.04 (WSL is fine) and packages
#   dist/opacra-v<version>-win-x64.zip  (opacrad.exe, opacra-wallet-cli.exe, opacra-wallet-rpc.exe)
#
#   contrib/windows/build-windows.sh            # from the repository root
#
# The first run downloads and builds about ten libraries for Windows (Boost, OpenSSL,
# ZeroMQ, libsodium, Unbound, ...) into contrib/depends: about 1-2 hours on 8-12 threads.
# Later runs reuse them and only rebuild Opacra. Everything is linked statically, so the
# .exe files need nothing else installed on Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
HOST=x86_64-w64-mingw32
JOBS="${JOBS:-$(nproc)}"
VERSION="$(grep -o 'DEF_MONERO_VERSION "[0-9.]*"' src/version.cpp.in | head -1 | cut -d'"' -f2)"
LOG="$ROOT/build/windows-build.log"
mkdir -p build dist
exec > >(tee -a "$LOG") 2>&1
echo "== Opacra v$VERSION for Windows, $JOBS jobs, log: $LOG  ($(date))"

echo "== 1/4 build tools (asks for your Ubuntu password)"
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential cmake git pkg-config autoconf automake libtool gperf \
  curl bzip2 xz-utils python3 zip g++-mingw-w64-x86-64 gcc-mingw-w64-x86-64
# Monero needs the POSIX threading flavour of MinGW
sudo update-alternatives --set x86_64-w64-mingw32-g++ /usr/bin/x86_64-w64-mingw32-g++-posix
sudo update-alternatives --set x86_64-w64-mingw32-gcc /usr/bin/x86_64-w64-mingw32-gcc-posix

echo "== 2/4 Windows libraries (contrib/depends; slow the first time)  $(date +%H:%M)"
make -C contrib/depends HOST="$HOST" -j"$JOBS"

echo "== 3/4 Opacra  $(date +%H:%M)"
BUILD="build/$HOST/release"
cmake -S . -B "$BUILD" \
  -DCMAKE_TOOLCHAIN_FILE="$ROOT/contrib/depends/$HOST/share/toolchain.cmake" \
  -DUSE_DEVICE_TREZOR=OFF -DBUILD_TESTS=OFF
cmake --build "$BUILD" --target daemon simplewallet wallet_rpc_server -j"$JOBS"

echo "== 4/4 package  $(date +%H:%M)"
NAME="opacra-v$VERSION-win-x64"
STAGE="$(mktemp -d)/$NAME"
mkdir -p "$STAGE"
for b in opacrad opacra-wallet-cli opacra-wallet-rpc; do
  cp "$BUILD/bin/$b.exe" "$STAGE/"
  x86_64-w64-mingw32-strip "$STAGE/$b.exe"
done
cp LICENSE "$STAGE/"
cat > "$STAGE/README.txt" <<TXT
Opacra v$VERSION for Windows (64-bit)

  opacrad.exe            full node and miner
  opacra-wallet-cli.exe  command-line wallet
  opacra-wallet-rpc.exe  wallet JSON-RPC server

Join the public testnet (testnet coins have no value):

  1. Unzip this folder, open it, click the address bar, type  powershell  and press Enter.
  2. Start a node and leave the window open:
       .\opacrad.exe --testnet
     Allow it through Windows Firewall if asked. It finds the network by itself.
  3. In a second PowerShell window in the same folder, create a wallet:
       .\opacra-wallet-cli.exe --testnet --generate-new-wallet mywallet
  4. In the wallet, mine with 2 CPU threads:   start_mining 2
     and check your earnings with:             balance

Windows may warn that the program is from an unknown publisher: the files are not
code-signed. Check the download against the signed checksums on https://opacra.org.
Block explorer: https://explorer.opacra.org
TXT
(cd "$STAGE" && sha256sum *.exe > SHA256SUMS)
(cd "$(dirname "$STAGE")" && rm -f "$ROOT/dist/$NAME.zip" && zip -qr "$ROOT/dist/$NAME.zip" "$NAME")
(cd dist && sha256sum "$NAME.zip" | tee "$NAME.zip.sha256")
echo "== done: dist/$NAME.zip  ($(date))"
