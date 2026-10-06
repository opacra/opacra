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
# Double-click launchers: opacrad.exe started by double-click joins mainnet, which has not launched
cat > "$STAGE/Start testnet node.bat" <<'BAT'
@echo off
cd /d "%~dp0"
title Opacra testnet node
echo Opacra testnet node. Leave this window open; type  status  and press Enter to check it.
echo.
opacrad.exe --testnet
pause
BAT
cat > "$STAGE/Start testnet wallet.bat" <<'BAT'
@echo off
cd /d "%~dp0"
title Opacra testnet wallet
if exist mywallet.keys (
  opacra-wallet-cli.exe --testnet --wallet-file mywallet
) else (
  echo No wallet yet: creating one called mywallet.
  echo.
  opacra-wallet-cli.exe --testnet --generate-new-wallet mywallet
)
pause
BAT
cat > "$STAGE/README.txt" <<TXT
Opacra v$VERSION for Windows (64-bit)

  Start testnet node.bat     double-click: runs a testnet node (and miner)
  Start testnet wallet.bat   double-click: opens your testnet wallet, or creates one
  opacrad.exe                full node and miner
  opacra-wallet-cli.exe      command-line wallet
  opacra-wallet-rpc.exe      wallet JSON-RPC server

Join the public testnet (testnet coins have no value):

  1. Unzip this folder.
  2. Double-click "Start testnet node". Allow it through Windows Firewall if asked.
     Leave the window open. It finds the network by itself; type  status  and press
     Enter until it shows 100.0%.
  3. Double-click "Start testnet wallet". The first time it creates a wallet called
     mywallet: choose a password, pick a language (1 = English), and answer  N  when
     it asks about background mining. Keep the 25 words it shows somewhere safe: they
     restore the wallet. Never share them.
  4. In the wallet, mine with 2 CPU threads:   start_mining 2
     and check your earnings with:             balance
     Mined coins unlock after 60 blocks (about 30 minutes).
     If the wallet says "Password needed (output received)", type  refresh  and enter
     your password: it is asking to unlock newly received coins.

Do not start opacrad.exe by double-clicking it: without --testnet it joins mainnet,
which has not launched yet.

Windows may warn that the program is from an unknown publisher: the files are not
code-signed. Check the download against the signed checksums on https://opacra.org.
Block explorer: https://explorer.opacra.org
TXT
# Windows line endings for the files people open in Notepad or run as batch files
sed -i 's/$/\r/' "$STAGE/README.txt" "$STAGE/Start testnet node.bat" "$STAGE/Start testnet wallet.bat"
(cd "$STAGE" && sha256sum *.exe > SHA256SUMS)
(cd "$(dirname "$STAGE")" && rm -f "$ROOT/dist/$NAME.zip" && zip -qr "$ROOT/dist/$NAME.zip" "$NAME")
(cd dist && sha256sum "$NAME.zip" | tee "$NAME.zip.sha256")
echo "== done: dist/$NAME.zip  ($(date))"
