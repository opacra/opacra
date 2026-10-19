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
# Double-click launchers. opacrad.exe started by double-click would join mainnet, which has
# not launched; "Start Opacra testnet" does everything a tester needs in one window.
cat > "$STAGE/Start Opacra testnet.bat" <<'BAT'
@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Opacra testnet
if exist testnet-wallet.address.txt goto start
echo.
echo  Welcome to the Opacra testnet. First, a wallet for the coins you mine.
echo  Choose a password and type it twice. Then write down the 25 words it shows:
echo  they are the only way to restore this wallet. Never share them.
echo.
opacra-wallet-cli.exe --testnet --offline --generate-new-wallet testnet-wallet --mnemonic-language English --create-address-file --command address
if not exist testnet-wallet.address.txt goto failed
echo.
echo  Wallet ready. Written the 25 words down? Press any key to start mining.
pause >nul
:start
rem The address file is checked before every use (it may have been copied from an older
rem folder): only letters and digits, so nothing in it can run as a command.
findstr /r /x "T[0-9A-Za-z]*" testnet-wallet.address.txt >nul || goto badaddress
set "ADDR="
set /p "ADDR=" < testnet-wallet.address.txt
rem To choose how many CPU threads mine, put a number after the = sign on the next line,
rem for example  set MINE_THREADS=4  . Leave it empty to use a quarter of this PC's threads.
set MINE_THREADS=
if "%MINE_THREADS%"=="" set /a MINE_THREADS=%NUMBER_OF_PROCESSORS%/4
set /a THREADS=%MINE_THREADS%
if %THREADS% LSS 1 set THREADS=1
cls
echo.
echo  Opacra testnet: joining the network and mining with %THREADS% threads to your wallet
echo  !ADDR!
echo.
echo  Leave this window open while you mine; close it to stop. Mining starts once the
echo  node has caught up, usually within a few minutes. Type  status  and press Enter
echo  to check. To see your coins, double-click "Open testnet wallet".
echo  To mine with more or fewer threads, see README.txt.
echo.
opacrad.exe --testnet --enforce-dns-checkpointing --start-mining "!ADDR!" --mining-threads %THREADS%
pause
exit /b
:badaddress
echo.
echo  testnet-wallet.address.txt does not hold an Opacra testnet address (letters and
echo  digits only, starting with T). Copy the right file from your old Opacra folder, then
echo  double-click "Start Opacra testnet" again.
pause
exit /b
:failed
echo.
echo  The wallet was not created. Close this window and double-click "Start Opacra testnet" again.
pause
BAT
cat > "$STAGE/Open testnet wallet.bat" <<'BAT'
@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Opacra testnet wallet
if exist testnet-wallet.keys goto open
echo  No wallet yet: double-click "Start Opacra testnet" first.
pause
exit /b
:open
echo  Type your wallet password. If it asks about background mining, type N: you are
echo  already mining in the other window. Useful commands: balance, address,
echo  transfer ADDRESS AMOUNT, exit. Keep "Start Opacra testnet" running alongside.
echo  When it says new coins have arrived, type  refresh  and enter your password when
echo  the wallet asks for it. Never type the password after the [wallet ...]: prompt.
echo.
opacra-wallet-cli.exe --testnet --wallet-file testnet-wallet
pause
BAT
cat > "$STAGE/README.txt" <<TXT
Opacra v$VERSION for Windows (64-bit)

Join the public testnet (testnet coins have no value):

  1. Unzip this folder.
  2. Double-click "Start Opacra testnet". Allow it through Windows Firewall if asked.
     The first time it creates your wallet: choose a password and write down the 25
     words it shows. Then it joins the network and mines. Leave the window open.
  3. To see your coins or send some, double-click "Open testnet wallet" and type
     balance   or   transfer ADDRESS AMOUNT
     Mined coins unlock after 60 blocks (about 30 minutes).
     When the wallet says new coins have arrived, type  refresh  and enter your
     password when the wallet asks for it (never after the [wallet ...]: prompt).

Mining threads: the miner uses a quarter of this PC's CPU threads, which keeps the
PC cool and usable. To change it, right-click "Start Opacra testnet", choose Edit
(or Show more options, Edit), and put a number after  set MINE_THREADS=  , for
example  set MINE_THREADS=4  . Save, then start it again. If the CPU runs hotter
than about 85 C, use fewer threads.

"No incoming connections" or "No other node has connected to this one yet": normal
on a home connection behind a router. Mining and syncing work as usual; nothing to do.

Emergency checkpoints: the miner follows the project's emergency checkpoints (published in
DNSSEC-signed records under opacra.org and opacra.com, which must agree). They are used only
to stop an attack, and every one is listed on opacra.org. To run without them, remove
--enforce-dns-checkpointing from "Start Opacra testnet".

Upgrading from an earlier version: unzip the new version into its own folder, then
copy these three files from your old folder into the new one before starting it:
  testnet-wallet   testnet-wallet.keys   testnet-wallet.address.txt
The blockchain is stored outside the folder, so it is not downloaded again.

Files:
  Start Opacra testnet.bat   wallet (first time), node and miner in one window
  Open testnet wallet.bat    your testnet wallet
  opacrad.exe                full node and miner
  opacra-wallet-cli.exe      command-line wallet
  opacra-wallet-rpc.exe      wallet JSON-RPC server

Do not start opacrad.exe by double-clicking it: without --testnet it joins mainnet,
which has not launched yet.

The programs are not code-signed yet. Windows may say it protected your PC: choose
More info, then Run anyway. On some newer Windows 11 PCs, Smart App Control blocks
unsigned programs completely ("Part of this app has been blocked"); the testnet cannot
run on such a PC until releases are signed. Check the download against the signed
checksums on https://opacra.org. Block explorer: https://explorer.opacra.org
TXT
# Windows line endings for the files people open in Notepad or run as batch files
sed -i 's/$/\r/' "$STAGE/README.txt" "$STAGE/Start Opacra testnet.bat" "$STAGE/Open testnet wallet.bat"
(cd "$STAGE" && sha256sum *.exe > SHA256SUMS)
(cd "$(dirname "$STAGE")" && rm -f "$ROOT/dist/$NAME.zip" && zip -qr "$ROOT/dist/$NAME.zip" "$NAME")
(cd dist && sha256sum "$NAME.zip" | tee "$NAME.zip.sha256")
echo "== done: dist/$NAME.zip  ($(date))"
