#!/usr/bin/env bash
# Builds the Opacra XMRig (RandomOPCA, rx/opca) for Linux and Windows on Ubuntu 24.04 / WSL:
#   contrib/xmrig/build-xmrig.sh          # from the repository root
# Writes dist/opacra-xmrig-<xmrig version>-<opacra version>-linux-x64.tar.gz
#    and dist/opacra-xmrig-<xmrig version>-<opacra version>-win-x64.zip
# Source: XMRig v6.26.0 from GitHub with contrib/xmrig/opacra-xmrig.patch applied. The
# Windows build is cross-compiled with MinGW, with libuv built from source; it leaves out
# hwloc (NUMA tuning for multi-socket servers) and TLS (encrypted pool connections), which
# solo mining against your own node doesn't use. CPU mining only: RandomX is a CPU algorithm.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
XMRIG_TAG=v6.26.0
# pinned commits: a moved tag upstream would otherwise change what we build and sign
XMRIG_COMMIT=b2ca72480c58d197e18c885d9fc1a0c8d517e60a
UV_TAG=v1.51.0
UV_COMMIT=5152db2cbfeb5582e9c27c5ea1dba2cd9e10759b
OPACRA_VERSION="$(grep -o 'DEF_MONERO_VERSION "[0-9.]*"' src/version.cpp.in | head -1 | cut -d'"' -f2)"
JOBS="${JOBS:-$(nproc)}"
WORK="$ROOT/build/xmrig"
LOG="$WORK/build.log"
mkdir -p "$WORK" dist
exec > >(tee -a "$LOG") 2>&1
echo "== Opacra XMRig ($XMRIG_TAG + opacra-xmrig.patch) for Opacra v$OPACRA_VERSION, $JOBS jobs  ($(date))"

echo "== 1/4 build tools (asks for your Ubuntu password)"
sudo apt-get update -qq
sudo apt-get install -y -qq git build-essential cmake libuv1-dev libssl-dev libhwloc-dev zip \
  g++-mingw-w64-x86-64 gcc-mingw-w64-x86-64
sudo update-alternatives --set x86_64-w64-mingw32-g++ /usr/bin/x86_64-w64-mingw32-g++-posix
sudo update-alternatives --set x86_64-w64-mingw32-gcc /usr/bin/x86_64-w64-mingw32-gcc-posix

echo "== 2/4 source"
rm -rf "$WORK/src"
git clone -q --depth 1 --branch "$XMRIG_TAG" https://github.com/xmrig/xmrig "$WORK/src"
[ "$(git -C "$WORK/src" rev-parse HEAD)" = "$XMRIG_COMMIT" ] || { echo "XMRig $XMRIG_TAG is not commit $XMRIG_COMMIT: stopping" >&2; exit 1; }
git -C "$WORK/src" apply "$ROOT/contrib/xmrig/opacra-xmrig.patch"
# donation level 0 by default: Opacra's build doesn't send miners' hash power to XMRig's authors
sed -i 's/constexpr const int kDefaultDonateLevel = 1;/constexpr const int kDefaultDonateLevel = 0;/; s/constexpr const int kMinimumDonateLevel = 1;/constexpr const int kMinimumDonateLevel = 0;/' "$WORK/src/src/donate.h"
grep -q 'kDefaultDonateLevel = 0;' "$WORK/src/src/donate.h" && grep -q 'kMinimumDonateLevel = 0;' "$WORK/src/src/donate.h" || { echo "could not set the donation level to 0: stopping" >&2; exit 1; }
rm -rf "$WORK/libuv"
git clone -q --depth 1 --branch "$UV_TAG" https://github.com/libuv/libuv "$WORK/libuv"
[ "$(git -C "$WORK/libuv" rev-parse HEAD)" = "$UV_COMMIT" ] || { echo "libuv $UV_TAG is not commit $UV_COMMIT: stopping" >&2; exit 1; }

COMMON=(-DCMAKE_BUILD_TYPE=Release -DWITH_OPENCL=OFF -DWITH_CUDA=OFF -DWITH_KAWPOW=OFF -DWITH_GHOSTRIDER=OFF)

echo "== 3/4 Linux build  $(date +%H:%M)"
cmake -S "$WORK/src" -B "$WORK/linux" "${COMMON[@]}" >/dev/null
cmake --build "$WORK/linux" -j"$JOBS"
strip "$WORK/linux/xmrig"

echo "== 3/4 Windows build  $(date +%H:%M)"
# libuv for Windows, built with the same MinGW so the C runtimes match
cmake -S "$WORK/libuv" -B "$WORK/libuv-win" -DCMAKE_BUILD_TYPE=Release -DCMAKE_SYSTEM_NAME=Windows \
  -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc -DLIBUV_BUILD_SHARED=OFF -DLIBUV_BUILD_TESTS=OFF \
  -DCMAKE_INSTALL_PREFIX="$WORK/win-deps" >/dev/null
cmake --build "$WORK/libuv-win" -j"$JOBS" >/dev/null
cmake --install "$WORK/libuv-win" >/dev/null
# XMRig includes a few Windows headers with capital letters (written for Windows' case-insensitive
# file system); MinGW's are lower case. Small forwarding headers fix that without touching XMRig.
mkdir -p "$WORK/wincompat"
for h in Windows Shobjidl Objbase BaseTsd; do
  lower="$(echo "$h" | tr 'A-Z' 'a-z')"
  echo "#include <$lower.h>" > "$WORK/wincompat/$h.h"
done
cmake -S "$WORK/src" -B "$WORK/win" "${COMMON[@]}" -DWITH_HWLOC=OFF -DWITH_TLS=OFF \
  -DCMAKE_C_FLAGS="-I$WORK/wincompat" -DCMAKE_CXX_FLAGS="-I$WORK/wincompat" \
  -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc -DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++ \
  -DCMAKE_RC_COMPILER=x86_64-w64-mingw32-windres -DXMRIG_DEPS="$WORK/win-deps" >/dev/null
cmake --build "$WORK/win" -j"$JOBS"
# without TLS XMRig names its binary xmrig-notls.exe; ship it as xmrig.exe
[ -f "$WORK/win/xmrig-notls.exe" ] && mv -f "$WORK/win/xmrig-notls.exe" "$WORK/win/xmrig.exe"
x86_64-w64-mingw32-strip "$WORK/win/xmrig.exe"

echo "== 4/4 package  $(date +%H:%M)"
NAME="opacra-xmrig-${XMRIG_TAG#v}-opacra-$OPACRA_VERSION"
STAGE="$(mktemp -d)"
# Linux
mkdir -p "$STAGE/$NAME-linux-x64"
cp "$WORK/linux/xmrig" "$WORK/src/LICENSE" "$STAGE/$NAME-linux-x64/"
cat > "$STAGE/$NAME-linux-x64/README.txt" <<TXT
Opacra XMRig: XMRig ${XMRIG_TAG} with Opacra's RandomOPCA algorithm (rx/opca), for Opacra v$OPACRA_VERSION.
Source: XMRig ${XMRIG_TAG} + contrib/xmrig/opacra-xmrig.patch from the Opacra repository. Donation level 0.

Needs: sudo apt install libuv1t64 libhwloc15 libssl3t64

Solo mining against your own Opacra node (testnet RPC port 29971):
  ./xmrig -o 127.0.0.1:29971 --daemon -a rx/opca --coin opacra -u <your Te... address> -t 2

Download Opacra's miner only from https://opacra.org and check it against the signed checksums.
TXT
(cd "$STAGE" && tar -czf "$ROOT/dist/$NAME-linux-x64.tar.gz" "$NAME-linux-x64")
# Windows
mkdir -p "$STAGE/$NAME-win-x64"
cp "$WORK/win/xmrig.exe" "$WORK/src/LICENSE" "$STAGE/$NAME-win-x64/"
cat > "$STAGE/$NAME-win-x64/Start testnet mining.bat" <<'BAT'
@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Opacra XMRig (testnet)
rem The saved address is checked before every use: only letters and digits are accepted,
rem so nothing pasted with it can run as a command. No pipes here: they lose delayed expansion.
if exist address.txt goto check
:ask
set "ADDR="
set /p "ADDR=Paste your Opacra testnet wallet address, it starts with Te, and press Enter: "
> address.txt echo(!ADDR!
:check
findstr /r /x "T[0-9A-Za-z]*" address.txt >nul || (del address.txt & echo That is not an Opacra testnet address. & goto ask)
set "ADDR="
set /p "ADDR=" < address.txt
echo Mining to !ADDR! through your own node on this computer. Start the node first.
xmrig.exe -o 127.0.0.1:29971 --daemon -a rx/opca --coin opacra -u "!ADDR!"
pause
BAT
cat > "$STAGE/$NAME-win-x64/README.txt" <<TXT
Opacra XMRig: XMRig ${XMRIG_TAG} with Opacra's RandomOPCA algorithm (rx/opca), for Opacra v$OPACRA_VERSION.
Source: XMRig ${XMRIG_TAG} + contrib/xmrig/opacra-xmrig.patch from the Opacra repository. Donation level 0.

1. Start your Opacra testnet node first ("Start testnet node" in the Opacra download).
2. Double-click "Start testnet mining". The first time it asks for your wallet address.

Most mining programs, including genuine ones, are flagged by antivirus software. Download
Opacra's miner only from https://opacra.org and check it against the signed checksums.
The wallet's own "start_mining" command needs no extra program at all.
TXT
sed -i 's/$/\r/' "$STAGE/$NAME-win-x64/README.txt" "$STAGE/$NAME-win-x64/Start testnet mining.bat"
(cd "$STAGE" && rm -f "$ROOT/dist/$NAME-win-x64.zip" && zip -qr "$ROOT/dist/$NAME-win-x64.zip" "$NAME-win-x64")
rm -rf "$STAGE"
(cd dist && sha256sum "$NAME-linux-x64.tar.gz" "$NAME-win-x64.zip" | tee "$NAME.sha256")
echo "== done  ($(date))"
