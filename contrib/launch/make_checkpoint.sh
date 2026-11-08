#!/usr/bin/env bash
# Print ADD_CHECKPOINT2 lines for src/checkpoints/checkpoints.cpp from a synced node.
#   contrib/launch/make_checkpoint.sh 10000 20000 30000
# RPC defaults to 127.0.0.1:29961 (override with RPC=host:port).
set -euo pipefail
# Prints the node's network first; with NETWORK=mainnet|testnet it stops if the node is on
# another one (an emergency record must come from the network it is published for).
RPC=${RPC:-127.0.0.1:29961}
net=$(curl -s --noproxy '*' "http://$RPC/json_rpc" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' |
  python3 -c 'import sys,json; print(json.load(sys.stdin)["result"].get("nettype", "?"))')
echo "    // $net, from $RPC"
if [ -n "${NETWORK:-}" ] && [ "$net" != "$NETWORK" ]; then
  echo "The node at $RPC is on $net, not $NETWORK: stopping." >&2
  exit 1
fi
for h in "$@"; do
  curl -s --noproxy '*' "http://$RPC/json_rpc" -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"get_block_header_by_height\",\"params\":{\"height\":$h}}" |
  python3 -c 'import sys,json; b=json.load(sys.stdin)["result"]["block_header"]; print("    ADD_CHECKPOINT2(%d, \"%s\", \"0x%x\");" % (b["height"], b["hash"], b["cumulative_difficulty"]))'
done
