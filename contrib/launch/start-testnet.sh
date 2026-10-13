#!/usr/bin/env bash
# Opacra testnet in one command: installs the runtime libraries if they are missing,
# creates your wallet the first time, then runs a node that mines to it.
#   ./start-testnet.sh            (from the unpacked release folder)
set -euo pipefail
cd "$(dirname "$0")"

if ! ./opacrad --version >/dev/null 2>&1; then
  echo "Installing the libraries Opacra needs (asks for your password)..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq libboost-chrono1.83.0t64 libboost-filesystem1.83.0 \
    libboost-program-options1.83.0 libboost-serialization1.83.0 libboost-thread1.83.0 \
    libhidapi-libusb0 libreadline8t64 libsodium23 libssl3t64 libunbound8 libusb-1.0-0 libzmq5
fi

if [ ! -f testnet-wallet.address.txt ]; then
  echo
  echo " Welcome to the Opacra testnet. First, a wallet for the coins you mine."
  echo " Choose a password and type it twice. Then write down the 25 words it shows:"
  echo " they are the only way to restore this wallet. Never share them."
  echo
  ./opacra-wallet-cli --testnet --offline --generate-new-wallet testnet-wallet \
    --mnemonic-language English --create-address-file --command address
  [ -f testnet-wallet.address.txt ] || { echo "The wallet was not created; run ./start-testnet.sh again."; exit 1; }
  echo
  read -r -p " Wallet ready. Written the 25 words down? Press Enter to start mining. " _
fi

ADDR=$(cat testnet-wallet.address.txt)
# a quarter of the CPU threads keeps the machine cool and usable; MINE_THREADS=N overrides it
THREADS=${MINE_THREADS:-$(( $(nproc) / 4 ))}
case "$THREADS" in ''|*[!0-9]*) THREADS=1 ;; esac
[ "$THREADS" -ge 1 ] || THREADS=1
echo
echo " Opacra testnet: joining the network and mining with $THREADS threads to your wallet"
echo " $ADDR"
echo
echo " Leave this terminal open while you mine; type  exit  to stop. Mining starts once the"
echo " node has caught up, usually within a few minutes. Type  status  to check. To see"
echo " your coins, open a second terminal in this folder and run  ./open-wallet.sh"
echo " To mine with N threads instead:  MINE_THREADS=N ./start-testnet.sh"
echo
exec ./opacrad --testnet --start-mining "$ADDR" --mining-threads "$THREADS"
