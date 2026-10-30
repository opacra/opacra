#!/usr/bin/env bash
# Test the Windows testnet launcher's address check on real Windows, from WSL:
#   contrib/windows/test-launcher.sh
# Takes "Start Opacra testnet.bat" exactly as build-windows.sh writes it (with CRLF line
# ends), swaps the node for an echo so nothing is started, and runs it with cmd.exe in a
# scratch folder under Windows' TEMP for these address files: a good one, one carrying a
# command (Te12&echo PWNED>pwned.txt), an empty one, a two-line one whose first line is bad,
# and, as the wallet writes them, with no line ending: a full 97-character address, one carrying
# a command, and one with exclamation marks;
# then the emergency-checkpoint switch
# (off by default, with a startup line saying how to switch it on; on with
# set ENFORCE_CHECKPOINTS=1). Prints PASS/FAIL for each.
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
run() {  # name, address file contents, expect "start" or "refuse" [, "enforce" | "-"] [, "noeol"]
  cp "$DIR/launcher.bat" "$DIR/run.bat"
  if [ "${4:-}" = enforce ]; then
    sed -i 's/^set ENFORCE_CHECKPOINTS=0\r$/set ENFORCE_CHECKPOINTS=1\r/' "$DIR/run.bat"
    grep -q "^set ENFORCE_CHECKPOINTS=1" "$DIR/run.bat" || { echo "could not switch checkpoints on in the launcher" >&2; exit 1; }
  fi
  rm -f "$DIR/pwned.txt"; enforced=no
  # the wallet writes its address with no line ending ("noeol"); older tests used CRLF
  if [ "${5:-}" = noeol ]; then printf '%s' "$2"; else printf '%s\r\n' "$2"; fi > "$DIR/testnet-wallet.address.txt"
  out=$(cd "$DIR" && echo | timeout 60 cmd.exe /c run.bat 2>&1 | tr -d '\r' || true)
  started=no; echo "$out" | grep -q "NODE-ARGS" && started=yes
  pwned=no; [ -e "$DIR/pwned.txt" ] && pwned=yes
  # the launcher's scratch copy of the address must be gone afterwards, also when it was refused
  leftover=no; [ -e "$(wslpath "$WINTMP")/opacra-address-check.txt" ] && leftover=yes
  if [ "$3" = start ]; then
    ok=$([ $started = yes ] && echo "$out" | grep -q -- "--start-mining \"$2\"" && echo yes || echo no)
    enforced=no; echo "$out" | grep -q -- "--enforce-dns-checkpointing" && enforced=yes
    [ "$enforced" = "$([ "${4:-}" = enforce ] && echo yes || echo no)" ] || ok=no
    # the default (warn only) must tell the miner how to switch enforcement on
    if [ "${4:-}" != enforce ]; then echo "$out" | grep -q "set ENFORCE_CHECKPOINTS=1" || ok=no; fi
  else
    ok=$([ $started = no ] && [ $pwned = no ] && echo yes || echo no)
  fi
  [ $leftover = no ] || ok=no
  [ $ok = yes ] || FAILS=$((FAILS + 1))
  printf '%s %-34s node started: %-3s  injected command ran: %-3s  enforces: %-3s  temp file left: %s\n' "$([ $ok = yes ] && echo PASS || echo FAIL)" "$1" "$started" "$pwned" "${enforced:-no}" "$leftover"
}
run "good address" "TeGood123abcXYZ" start
run "address with a command in it" "Te12&echo PWNED>pwned.txt" refuse
run "empty address file" "" refuse
run "two lines, bad first line" "$(printf 'Te12&echo PWNED>pwned.txt\r\nTeGood123abcXYZ')" refuse
run "checkpoint switch on (=1)" "TeGood123abcXYZ" start enforce
# a real wallet's address file: 97 characters, no line ending
REAL=Te1kc2Tea6EB$(printf 'x%.0s' $(seq 1 85) | tr x A)
run "real address, no line ending" "$REAL" start - noeol
run "command in it, no line ending" "Te12&echo PWNED>pwned.txt" refuse - noeol
run "exclamation marks, no line ending" "Te12!OS!x" refuse - noeol
rm -rf "$DIR"
[ $FAILS -eq 0 ] && echo "ALL CHECKS PASSED" || { echo "$FAILS CHECK(S) FAILED"; exit 1; }
