# ai-thinking-journal

Automated daily thinking journal from AI coding assistant conversations.

Extracts conversation transcripts from Claude Code, Codex CLI, and other AI coding tools, then generates structured daily/weekly/monthly journal entries via LLM.

## Install

```bash
pip install ai-thinking-journal
```

## Quickstart

```bash
# Interactive setup
aij init

# Generate today's journal
aij run

# Generate for a specific date
aij run --date 2026-05-17

# Dry run (preview only)
aij run --dry-run
```

## Commands

- `aij init` — Interactive setup wizard
- `aij run` — Generate journal entry
- `aij config` — View/edit configuration
- `aij status` — Show sources, summarizer, outputs

## Configuration

Config file: `~/.aij/config.toml`

```toml
[general]
timezone = "Asia/Taipei"
journal_root = "~/ai-journal"

[summarizer]
backend = "openai"  # "openai" | "ollama"

[outputs.markdown]
enabled = true
```

## License

MIT
