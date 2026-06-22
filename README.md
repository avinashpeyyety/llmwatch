# llmwatch

Mac terminal dashboard for:

- **RAM + swap** usage
- **Storage** per volume
- **Top processes** by memory and disk read/write
- **Local Ollama LLMs** — loaded context, live tok/s, prompt speed

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

## Requirements

- macOS
- Python 3.10+
- Ollama (optional, for LLM panel)