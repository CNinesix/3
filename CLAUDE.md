# CLAUDE.md

Guidance for AI assistants (and humans) working in this repository.

## What this repository is

This is **not a software project** — there is no build, no test suite, and no
runtime code to compile. It is a small set of **plain-text registry/data files**
that are served raw (e.g. via `raw.githubusercontent.com`) and consumed by
external client scripts/bots. Working here almost always means **editing the
contents of these data files**, not writing code.

Treat every file as a flat, line-oriented data store. Preserve the exact
on-disk format — a stray character can break the downstream parsers that read
these files.

## Repository layout

| File         | Purpose |
|--------------|---------|
| `authbot`    | Registry of authorized bot/server entries. One record per line. |
| `authws`     | Registry of "ws" entries with a status/expiry field. One record per line. |
| `versi`      | A single version string (currently `3.0`) used by clients for update/version checks. |
| `LICENSE`    | GNU GPL v3. |
| `.gitignore` | Minimal ignore file. |

There are no subdirectories, no package manifests, and no CI configuration.

## File formats

These formats are inferred from the existing data and the commit history.
**Match them exactly**, including the leading marker, the single-space
separators, and the trailing newline at end of file.

### `authbot`
Each line:

```
### <Name> <IP> <flag>
```

- Literal prefix `### ` (three hashes + one space).
- `<Name>`: identifier with no spaces (e.g. `SinyoRmx`, `Lapak6`).
- `<IP>`: IPv4 address.
- `<flag>`: a boolean, currently always `true`.
- Fields are separated by single spaces.

Example:
```
### SinyoRmx 34.101.100.8 true
```

### `authws`
Each line:

```
#& <Name> <Status> <Value>
```

- Literal prefix `#& ` (hash + ampersand + space).
- `<Name>`: identifier, may contain a space in practice (e.g. `Tes Lifetime`,
  `Non Lifetime`) — follow the pattern of the surrounding lines rather than
  assuming a fixed column count.
- `<Status>/<Value>`: either a `Lifetime`/`Non Lifetime` marker followed by an
  IP, or an expiry date in `YYYY-MM-DD` form.

Examples:
```
#& Tes Lifetime 103.157.27.191
#& Vina 2021-09-06
```

### `versi`
A single line containing only the version number, e.g.:
```
3.0
```
Bump this when clients should detect a new release. Keep it to just the
number — no label, no trailing blank lines beyond the existing format.

## Conventions

- **No blank lines, no comments, no reordering** unless explicitly requested.
  New entries are normally **appended at the top** of the file (the history
  shows new `authbot` records inserted as the first line), or in place when an
  existing record's IP changes.
- **Preserve exact spacing and prefixes.** Do not "tidy up" alignment, sort the
  list, or normalize names.
- **Keep the trailing newline.** Files end with a newline; don't strip it.
- **One logical change per commit.** The history is a stream of small,
  single-file edits.

## Commit & branch workflow

The established commit-message convention is a short, file-scoped imperative:

- `Update authbot`
- `Update authws`
- `Update versi`

Match this style. Commit the single file you changed.

Branching / pushing for AI assistants in this environment:

1. Develop on the designated feature branch (do **not** commit directly to `main`).
2. Make the focused edit, then commit with a message matching the convention above.
3. Push with `git push -u origin <branch-name>`; retry on transient network
   errors with exponential backoff.
4. Do **not** open a pull request unless explicitly asked.

## Working checklist for common tasks

- **Add an authbot entry:** prepend `### <Name> <IP> true` as the first line of
  `authbot`. Verify the IP is a valid IPv4 and the name has no spaces.
- **Update an IP:** edit the existing line in place; change only the IP field.
- **Add an authws entry:** append/insert `#& <Name> <Status> <Value>` matching
  the surrounding lines' shape.
- **Release a new version:** set the new number in `versi`.

After any edit, run `git diff` and confirm only the intended line(s) changed and
that whitespace/prefixes are intact.
