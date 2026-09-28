#!/usr/bin/env bash
# Run a private multi-node Tacita network on one machine (development / testing).
#
#   contrib/testnet/localnet.sh start      # start NODES daemons that only peer with each other
#   contrib/testnet/localnet.sh status
#   contrib/testnet/localnet.sh stop
#   contrib/testnet/localnet.sh wipe       # stop and delete all local chain data
#
# Environment:
#   BIN       directory with tacitad (default: build/release/bin)
#   DATA      data root (default: ~/tacita-localnet)
#   NODES     number of nodes (default 3)
#   NET_FLAG  "" (mainnet rules, isolated), "--testnet" or "--stagenet"
#   BASE_P2P  first P2P port (default 31000; node i uses BASE_P2P+10*i, RPC = P2P+1, ZMQ = P2P+2)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BIN=${BIN:-$HERE/../../build/release/bin}
DATA=${DATA:-$HOME/tacita-localnet}
NODES=${NODES:-3}
NET_FLAG=${NET_FLAG:-}
BASE_P2P=${BASE_P2P:-31000}

node_ports() { local i=$1; P2P=$((BASE_P2P + i * 10)); RPC=$((P2P + 1)); ZMQ=$((P2P + 2)); }

start_node() {
  local i=$1; shift
  node_ports "$i"
  local peers=()
  for j in $(seq 0 $((NODES - 1))); do
    [ "$j" -eq "$i" ] && continue
    peers+=(--add-exclusive-node "127.0.0.1:$((BASE_P2P + j * 10))")
  done
  mkdir -p "$DATA/node$i"
  "$BIN/tacitad" $NET_FLAG --data-dir "$DATA/node$i" \
    --p2p-bind-ip 127.0.0.1 --p2p-bind-port "$P2P" \
    --rpc-bind-ip 127.0.0.1 --rpc-bind-port "$RPC" --zmq-rpc-bind-port "$ZMQ" \
    --no-igd --allow-local-ip --disable-dns-checkpoints --check-updates disabled \
    --log-level 0 --non-interactive "${peers[@]}" "$@" \
    --detach --pidfile "$DATA/node$i/tacitad.pid" >/dev/null
  echo "node$i  p2p 127.0.0.1:$P2P  rpc 127.0.0.1:$RPC  data $DATA/node$i"
}

stop_node() {
  local i=$1 pidf="$DATA/node$1/tacitad.pid"
  if [ -f "$pidf" ] && kill -0 "$(cat "$pidf")" 2>/dev/null; then
    kill "$(cat "$pidf")"
    for _ in $(seq 1 60); do kill -0 "$(cat "$pidf")" 2>/dev/null || break; sleep 1; done
  fi
  rm -f "$pidf"
}

case "${1:-}" in
  start)
    for i in $(seq 0 $((NODES - 1))); do start_node "$i"; done ;;
  start-node)
    start_node "$2" "${@:3}" ;;
  stop-node)
    stop_node "$2" ;;
  stop)
    for i in $(seq 0 $((NODES - 1))); do stop_node "$i"; done ;;
  status)
    for i in $(seq 0 $((NODES - 1))); do
      node_ports "$i"
      printf "node%s: " "$i"
      curl -s --noproxy '*' -m 3 "http://127.0.0.1:$RPC/get_info" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("height", d["height"], "difficulty", d["difficulty"], "peers", d["outgoing_connections_count"]+d["incoming_connections_count"], "top", d["top_block_hash"][:16])' 2>/dev/null || echo "down"
    done ;;
  wipe)
    for i in $(seq 0 $((NODES - 1))); do stop_node "$i"; done
    rm -rf "$DATA" ;;
  *)
    sed -n '2,16p' "$0"; exit 1 ;;
esac
