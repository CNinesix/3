# Installation code (th2 USB)

The USB install is gated behind an **installation code**. The plaintext code is
never stored in the repo — only a salted SHA-256 hash lives in
`install-code.sha256` (format: `salt:sha256(salt+code)`).

## Files

| File | Purpose |
|------|---------|
| `install-code.sha256` | Salted hash of the current code (safe to commit). |
| `verify-code.sh` | Prompts for the code and checks it. Exit 0 = correct. |
| `set-code.sh` | Generates/sets a new code and prints it once. |

## Checking a code

```sh
sh install/verify-code.sh                     # prompts (hidden input)
INSTALL_CODE=TH2-XXXX-XXXX-XXXX sh install/verify-code.sh   # non-interactive
```

The USB entry point `vpn-mobile/autorun-usb.sh` calls this automatically and
refuses to run without the right code. Bypass only for testing with
`SKIP_CODE=1`.

## Rotating the code

```sh
sh install/set-code.sh                 # random TH2-XXXX-XXXX-XXXX
sh install/set-code.sh MYOWNCODE       # choose your own
```

It prints the new code **once** — record it immediately, it is not saved.
Commit the updated `install-code.sha256` to distribute the new code to the USB.

> Security note: this gate stops casual/accidental runs and keeps the code out
> of git in plaintext. It is not strong protection against someone who has the
> USB and the hash file and runs an offline brute force — use a long,
> unguessable code if that matters.
