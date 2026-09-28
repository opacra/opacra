#!/usr/bin/env bash
# Print ADD_CHECKPOINT2 lines for src/checkpoints/checkpoints.cpp from a synced node.
#   contrib/launch/make_checkpoint.sh 10000 20000 30000
# RPC defaults to 127.0.0.1:29961 (override with RPC=host:port).
set -euo pipefail
RPC=${RPC:-127.0.0.1:29961}
for h in "$@"; do
  curl -s --noproxy '*' "http://$RPC/json_rpc" -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":\"0\",\"method\":\"get_block_header_by_height\",\"params\":{\"height\":$h}}" |
  python3 -c 'import sys,json; b=json.load(sys.stdin)["result"]["block_header"]; print("    ADD_CHECKPOINT2(%d, \"%s\", \"0x%x\");" % (b["height"], b["hash"], b["cumulative_difficulty"]))'
done
