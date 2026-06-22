# llmwatch

**Landing page:** [https://avinashpeyyety.github.io/llmwatch/](https://avinashpeyyety.github.io/llmwatch/)

Mac terminal dashboard for:

- **RAM + swap** usage
- **Storage** per volume
- **Top processes** by memory and disk read/write
- **Local Ollama LLMs** — loaded context, live tok/s, prompt speed
- **API sessions (Aider)** — xAI and other cloud models: tokens sent/received, session cost, generating status

## Install

```bash
git clone https://github.com/avinashpeyyety/llmwatch.git
cd llmwatch
./scripts/install.sh
```

Ensure `~/.local/bin` is on your `PATH`, then:

```bash
llmwatch
```

## Usage

```bash
llmwatch                  # default 1s refresh
llmwatch --refresh 0.5    # faster updates
llmwatch --processes 20   # show more processes
```

Press **Ctrl+C** to quit.

## How tok/s works

`llmwatch` tails Ollama’s log (`/opt/homebrew/var/log/ollama.log` by default) and parses lines like:

```
slot print_timing: ... tg = 18.19 t/s
```

That gives **live generation speed** while a model is running. When idle, it shows the **last completed** generation speed.

Context comes from `GET /api/ps` (`context_length`) plus active prompt tokens from the log.

## API session stats (Aider + xAI)

When you run `aider-xai` (or any non-Ollama model via the global `aider` launcher), Aider writes a per-session manifest and analytics log under `~/.config/aider/sessions/`. llmwatch shows:

- **Active session** — one running Aider API session (model, status, tokens, cost)
- **Month to date (MTD)** — aggregated messages, tokens, and cost for the current calendar month

Ended or suspended sessions are cleaned up automatically and no longer appear in the panel.

Requires the global launcher from [aider-local](../aider-local) — plain `aider.real` does not emit session files.

## Requirements

- macOS
- Python 3.10+
- Ollama (optional, for LLM panel)