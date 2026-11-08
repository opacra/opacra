#!/usr/bin/env bash
# Opens the mainnet wallet created by start-mainnet.sh.
set -euo pipefail
cd "$(dirname "$0")"
[ -f mainnet-wallet.keys ] || { echo "No wallet yet: run ./start-mainnet.sh first."; exit 1; }
echo " Type your wallet password. If it asks about background mining, type N: the node is"
echo " already mining. Useful commands: balance, address, transfer ADDRESS AMOUNT, exit."
echo " When it says new coins have arrived, type  refresh  and enter your password when the"
echo " wallet asks for it. Never type the password after the [wallet ...]: prompt."
echo
exec ./opacra-wallet-cli --wallet-file mainnet-wallet
