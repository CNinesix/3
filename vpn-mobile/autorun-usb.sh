#!/usr/bin/env sh
# autorun-usb.sh
# Entry point for the "usb auto install th2" flow, extended to also set up the
# mobile VPN. Drop this whole `vpn-mobile/` folder onto the USB stick next to
# the th2 installer. Running this script (on a PC, or in Termux on the phone)
# regenerates the mobile VPN configs from the repo's server lists and prints
# import instructions.
#
# Usage:
#   sh autorun-usb.sh
#
# It is safe to run repeatedly; it only writes into vpn-mobile/dist/.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

echo "=============================================="
echo " USB auto install (th2) - mobile VPN setup"
echo "=============================================="
echo ""

# Gate the install behind the installation code (skip with SKIP_CODE=1).
VERIFY="$SCRIPT_DIR/../install/verify-code.sh"
if [ "${SKIP_CODE:-0}" != "1" ] && [ -f "$VERIFY" ]; then
  if ! sh "$VERIFY"; then
    echo "Aborting: installation code required." >&2
    exit 1
  fi
  echo ""
fi

# Detect Termux (Android) so we can give phone-specific instructions.
IS_TERMUX=0
if [ -n "${PREFIX:-}" ] && [ -d "/data/data/com.termux" ]; then
  IS_TERMUX=1
fi

echo "[1/2] Generating mobile VPN config from repo server lists..."
sh "$SCRIPT_DIR/generate-mobile-config.sh" "$SCRIPT_DIR/dist"

echo ""
echo "[2/2] How to use it on your phone:"
echo "-----------------------------------------------"
if [ "$IS_TERMUX" -eq 1 ]; then
  echo " * You're on Termux. The files are in:"
  echo "     $SCRIPT_DIR/dist"
  echo " * Copy them to shared storage so other apps can see them:"
  echo "     termux-setup-storage   # (first time only)"
  echo "     cp -f \"$SCRIPT_DIR/dist/\"* ~/storage/shared/Download/"
  echo " * Open your tunnel app (HTTP Injector / HTTP Custom / NapsternetV)"
  echo "   and Import config from the Download folder."
else
  echo " * Copy vpn-mobile/dist/* from this USB to your phone (Download folder)."
  echo " * In your mobile SSH/SSL-tunnel app choose Import config and pick"
  echo "   http-injector-import.txt (or the .json for apps that read JSON)."
fi
echo ""
echo " Before connecting, edit the file (or re-run with env vars) so that"
echo " VPN_USER / VPN_PASS / VPN_SNI hold your real account details:"
echo ""
echo "     VPN_USER=me VPN_PASS=secret VPN_SNI=bug.example.com \\"
echo "         sh \"$SCRIPT_DIR/generate-mobile-config.sh\""
echo ""
echo "Done. See vpn-mobile/README.md for the full walkthrough."
