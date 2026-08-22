#!/usr/bin/env sh
# set-code.sh
# Rotate the installation code. Generates a fresh code (or accepts one you pass),
# stores only its salted SHA-256 in install/install-code.sha256, and prints the
# plaintext code ONCE so you can record it. The plaintext is never written to disk.
#
# Usage:
#   sh set-code.sh                 # generate a random TH2-XXXX-XXXX-XXXX code
#   sh set-code.sh MYCUSTOMCODE    # use a code you choose

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
HASH_FILE="$SCRIPT_DIR/install-code.sha256"

rand_from() {
  # $1 = alphabet, $2 = length
  tr -dc "$1" < /dev/urandom | head -c "$2"
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    printf '%s' "$1" | shasum -a 256 | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then
    printf '%s' "$1" | openssl dgst -sha256 | awk '{print $NF}'
  else
    echo "no sha256 tool found" >&2; exit 2
  fi
}

if [ $# -ge 1 ]; then
  CODE=$1
else
  A='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # no ambiguous chars (0/O/1/I)
  CODE="TH2-$(rand_from "$A" 4)-$(rand_from "$A" 4)-$(rand_from "$A" 4)"
fi

SALT=$(rand_from 'a-f0-9' 16)
HASH=$(sha256_of "${SALT}${CODE}")
printf '%s:%s\n' "$SALT" "$HASH" > "$HASH_FILE"

echo "New installation code set."
echo ""
echo "    $CODE"
echo ""
echo "Record it now - it is NOT stored anywhere (only its salted hash in"
echo "$(basename "$HASH_FILE")). Commit the hash file to distribute the new code."
