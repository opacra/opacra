#!/usr/bin/env bash
# Opacra mainnet in one command: installs the runtime libraries if they are missing,
# creates your wallet the first time, then runs a node that mines to it.
#   ./start-mainnet.sh            (from the unpacked release folder)
#   MINE_THREADS=N ./start-mainnet.sh          mine with N threads
#   ENFORCE_CHECKPOINTS=1 ./start-mainnet.sh   follow the project's emergency checkpoints (opacra.org
#                                              asks for it during an attack; the default only warns)
set -euo pipefail
cd "$(dirname "$0")"

if ! ./opacrad --version >/dev/null 2>&1; then
  echo "Installing the libraries Opacra needs (asks for your password)..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq libboost-chrono1.83.0t64 libboost-filesystem1.83.0 \
    libboost-program-options1.83.0 libboost-serialization1.83.0 libboost-thread1.83.0 \
    libhidapi-libusb0 libreadline8t64 libsodium23 libssl3t64 libunbound8 libusb-1.0-0 libzmq5
fi

if [ ! -f mainnet-wallet.address.txt ]; then
  echo
  echo " Welcome to Opacra. First, a wallet for the coins you mine."
  echo " Choose a password and type it twice. Then write down the 25 words it shows, on"
  echo " paper: they are the only way to restore this wallet and its coins. Never share them;"
  echo " nobody from Opacra will ever ask for them."
  echo
  ./opacra-wallet-cli --offline --generate-new-wallet mainnet-wallet \
    --mnemonic-language English --create-address-file --command address
  [ -f mainnet-wallet.address.txt ] || { echo "The wallet was not created; run ./start-mainnet.sh again."; exit 1; }
  echo
  read -r -p " Wallet ready. Written the 25 words down on paper? Press Enter to start mining. " _
fi

ADDR=$(cat mainnet-wallet.address.txt)
# only a mainnet address: letters and digits, starting with P (a testnet wallet copied here would mine to nothing)
case "$ADDR" in
  P*) ;;
  *) echo " mainnet-wallet.address.txt does not hold an Opacra mainnet address (it starts with P)."
     echo " Did you copy a testnet wallet? Testnet coins never become mainnet coins."; exit 1 ;;
esac
case "$ADDR" in *[!0-9A-Za-z]*) echo " mainnet-wallet.address.txt holds something other than an address."; exit 1 ;; esac
# a quarter of the CPU threads keeps the machine cool and usable; MINE_THREADS=N overrides it
THREADS=${MINE_THREADS:-$(( $(nproc) / 4 ))}
case "$THREADS" in ''|*[!0-9]*) THREADS=1 ;; esac
[ "$THREADS" -ge 1 ] || THREADS=1
echo
echo " Opacra mainnet: joining the network and mining with $THREADS threads to your wallet"
echo " $ADDR"
echo
echo " Leave this terminal open while you mine; type  exit  to stop. Mining starts once the"
echo " node has caught up, usually within a few minutes. Type  status  to check. To see"
echo " your coins, open a second terminal in this folder and run  ./open-mainnet-wallet.sh"
echo " To mine with N threads instead:  MINE_THREADS=N ./start-mainnet.sh"
echo
# Emergency checkpoints (DNSSEC-signed, both domains must agree) are followed by the seeds, pools
# and exchanges. Home nodes only warn unless ENFORCE_CHECKPOINTS=1: during an attack opacra.org
# asks miners to restart with it. A wrong record costs no blocks: once withdrawn, the node returns.
CHECKPOINTS=()
if [ "${ENFORCE_CHECKPOINTS:-0}" = 1 ]; then
  CHECKPOINTS=(--enforce-dns-checkpointing)
  echo " Following the project's emergency checkpoints (ENFORCE_CHECKPOINTS=1)."
else
  echo " Emergency checkpoints: this node only warns. To follow them:  ENFORCE_CHECKPOINTS=1 ./start-mainnet.sh"
fi
echo
exec ./opacrad "${CHECKPOINTS[@]}" --start-mining "$ADDR" --mining-threads "$THREADS"
