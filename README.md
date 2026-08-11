# Claude × Kimi Exchange Platform

A small platform where **Claude** (Anthropic) and **Kimi** (Moonshot AI) exchange
prompts and results to complete a task together. Each agent keeps its own
conversation history; the orchestrator relays plain-text messages between them
and saves the full transcript.

## Collaboration modes

| Mode | Flow |
|---|---|
| `review` (default) | Claude drafts → Kimi reviews with `VERDICT: APPROVE/REVISE` → Claude revises → … until approved or rounds run out |
| `collab` | Claude and Kimi take turns building on a shared transcript until one declares `FINAL ANSWER:` |
| `debate` | Both answer independently, rebut each other for N rounds, then Claude writes a synthesis |

## Setup

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...
export MOONSHOT_API_KEY=sk-...        # from platform.moonshot.ai
```

Optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `CLAUDE_MODEL` | `claude-opus-5` | Claude model ID |
| `KIMI_MODEL` | `kimi-k2-0905-preview` | Kimi model ID |
| `KIMI_BASE_URL` | `https://api.moonshot.ai/v1` | Use `https://api.moonshot.cn/v1` for the CN platform |

## Usage

```bash
# Author/reviewer loop (default)
python -m claude_kimi "Write a Python function that merges overlapping intervals, with tests."

# Turn-by-turn collaboration
python -m claude_kimi "Design a REST API for a todo app" --mode collab --rounds 3

# Debate + synthesis
python -m claude_kimi "Is microservices architecture right for a 5-person startup?" --mode debate --rounds 2
```

Every run prints each turn live and saves the transcript to
`transcripts/<mode>-<timestamp>.md` (plus a `.json` with the raw turns).

## How it works

- `claude_kimi/agents.py` — `ClaudeAgent` (official `anthropic` SDK, adaptive
  thinking, streaming) and `KimiAgent` (Moonshot's OpenAI-compatible API).
- `claude_kimi/exchange.py` — the orchestrator: routes messages between the two
  agents according to the chosen mode and detects termination tokens
  (`VERDICT: APPROVE`, `FINAL ANSWER:`).
- `claude_kimi/__main__.py` — CLI.

Extending it is straightforward: add a new mode by writing a `_run_<mode>`
method on `Exchange`, or swap in different models via the environment variables.
