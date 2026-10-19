#!/usr/bin/env bash
# Test the Windows testnet launcher's address check on real Windows, from WSL:
#   contrib/windows/test-launcher.sh
# Takes "Start Opacra testnet.bat" exactly as build-windows.sh writes it (with CRLF line
# ends), swaps the node for an echo so nothing is started, and runs it with cmd.exe in a
# scratch folder under Windows' TEMP for three address files: a good one, one carrying a
# command (Te12&echo PWNED>pwned.txt), and an empty one. Prints PASS/FAIL for each.
# Needs WSL (cmd.exe on the PATH). Wine can't be used: its findstr gives wrong answers.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
command -v cmd.exe >/dev/null || { echo "cmd.exe not found: run this in WSL on Windows" >&2; exit 1; }
WINTMP=$(cmd.exe /c 'echo %TEMP%' 2>/dev/null | tr -d '\r')
DIR="$(wslpath "$WINTMP")/opacra-launcher-test"
rm -rf "$DIR"; mkdir -p "$DIR"
awk '/^cat > "\$STAGE\/Start Opacra testnet.bat" <<.BAT.$/{f=1; next} f && /^BAT$/{exit} f' \
  "$ROOT/contrib/windows/build-windows.sh" |
  sed -e 's/^opacrad\.exe /echo NODE-ARGS /' -e 's/$/\r/' > "$DIR/launcher.bat"
grep -q "NODE-ARGS" "$DIR/launcher.bat" || { echo "could not find the node line in the launcher" >&2; exit 1; }

FAILS=0
run() {  # name, address file contents, expect "start" or "refuse"
  rm -f "$DIR/pwned.txt"
  printf '%s\r\n' "$2" > "$DIR/testnet-wallet.address.txt"
  out=$(cd "$DIR" && echo | timeout 60 cmd.exe /c launcher.bat 2>&1 | tr -d '\r' || true)
  started=no; echo "$out" | grep -q "NODE-ARGS" && started=yes
  pwned=no; [ -e "$DIR/pwned.txt" ] && pwned=yes
  if [ "$3" = start ]; then
    ok=$([ $started = yes ] && echo "$out" | grep -q -- "--start-mining \"$2\"" && echo yes || echo no)
  else
    ok=$([ $started = no ] && [ $pwned = no ] && echo yes || echo no)
  fi
  [ $ok = yes ] || FAILS=$((FAILS + 1))
  printf '%s %-34s node started: %-3s  injected command ran: %s\n' "$([ $ok = yes ] && echo PASS || echo FAIL)" "$1" "$started" "$pwned"
}
run "good address" "TeGood123abcXYZ" start
run "address with a command in it" "Te12&echo PWNED>pwned.txt" refuse
run "empty address file" "" refuse
rm -rf "$DIR"
[ $FAILS -eq 0 ] && echo "ALL CHECKS PASSED" || { echo "$FAILS CHECK(S) FAILED"; exit 1; }
