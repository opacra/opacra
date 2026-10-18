# Sourced by seed-node-setup.sh and install-alerts.sh: where each network's node lives, so
# one server can run several networks side by side (testnet now, mainnet from launch day).
# Testnet keeps the original names, so seeds installed before 18 Oct 2026 upgrade in place.
case "$NETWORK" in
  testnet) SUFFIX="" ;;
  *)       SUFFIX="-$NETWORK" ;;
esac
SERVICE="opacrad$SUFFIX"                       # systemd service
NODECONF="/etc/opacra/opacra$SUFFIX.conf"      # node config
ALERTCONF="/etc/opacra/alert$SUFFIX.conf"      # alert config
ALERTUNIT="opacra-alert$SUFFIX"                # alert watchdog service and timer
if [ -z "$SUFFIX" ]; then
  DATADIR=/var/lib/opacra                      # the node adds its own testnet3/ folder
  LOGFILE=/var/lib/opacra/opacra.log
  STATEDIR=/var/lib/opacra/alert
else
  DATADIR="/var/lib/opacra/$NETWORK"
  LOGFILE="/var/lib/opacra/opacra$SUFFIX.log"
  STATEDIR="/var/lib/opacra/alert$SUFFIX"
fi
