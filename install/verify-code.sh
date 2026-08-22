#!/usr/bin/env sh
# verify-code.sh
# Gate the th2 USB installation behind an installation code.
#
# The plaintext code is NOT stored. install/install-code.sha256 holds
# "salt:sha256(salt+code)". This script hashes what the user types and compares.
#
# Usage:
#   sh verify-code.sh                # prompt for the code interactively
#   INSTALL_CODE=TH2-.... sh verify-code.sh   # non-interactive (e.g. autorun)
#
# Exit status: 0 = code correct, 1 = wrong/missing, 2 = setup problem.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
HASH_FILE="$SCRIPT_DIR/install-code.sha256"

[ -f "$HASH_FILE" ] || { echo "no installation code configured ($HASH_FILE missing)" >&2; exit 2; }

sha256_of() {
  # portable sha256 -> hex only
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    printf '%s' "$1" | shasum -a 256 | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then
    printf '%s' "$1" | openssl dgst -sha256 | awk '{print $NF}'
  else
    echo "no sha256 tool (sha256sum/shasum/openssl) found" >&2; exit 2
  fi
}

stored=$(cat "$HASH_FILE")
salt=${stored%%:*}
want=${stored#*:}
[ -n "$salt" ] && [ -n "$want" ] && [ "$salt" != "$want" ] || { echo "malformed $HASH_FILE" >&2; exit 2; }

attempts=3
i=0
while [ "$i" -lt "$attempts" ]; do
  i=$((i + 1))
  if [ -n "${INSTALL_CODE:-}" ]; then
    code=$INSTALL_CODE
  else
    printf 'Enter installation code: '
    # read silently if we have a tty
    if [ -t 0 ]; then stty -echo 2>/dev/null || true; fi
    read -r code
    if [ -t 0 ]; then stty echo 2>/dev/null || true; echo; fi
  fi

  got=$(sha256_of "${salt}${code}")
  if [ "$got" = "$want" ]; then
    echo "Installation code accepted."
    exit 0
  fi

  echo "Incorrect installation code ($i/$attempts)." >&2
  # a code passed via env that is wrong should not loop forever
  [ -n "${INSTALL_CODE:-}" ] && break
done

echo "Installation blocked: wrong installation code." >&2
exit 1
