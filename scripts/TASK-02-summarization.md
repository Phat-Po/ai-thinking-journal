# Task 02: Daily Summarization

**Goal**: Generate an Obsidian-compatible daily thinking journal from extracted daily conversations and statistics.

**Status**: Complete for daily pipeline

## Input

```text
output/YYYY-MM-DD/
  filtered_conversations.md
  stats.json
```

## Output

```text
ai-journal/daily/YYYY-MM-DD.md
```

The generated file contains YAML frontmatter plus the LLM-generated daily sections defined in `ai-thinking-journal-product-spec.md`.

## Model

- Default: `qwen3-coder:480b-cloud`
- Override: `SUMMARY_MODEL` env var or `--model`
- API: local Ollama chat endpoint at `http://localhost:11434/api/chat`

## Usage

```bash
python3 scripts/02_summarize.py
python3 scripts/02_summarize.py --date 2026-05-14
python3 scripts/02_summarize.py --date 2026-05-14 --dry-run
python3 scripts/02_summarize.py --model qwen3-coder:480b-cloud
```

## Acceptance Criteria

- [x] Reads `filtered_conversations.md` and `stats.json`.
- [x] Uses the product-spec daily summary prompt.
- [x] Generates YAML metadata from `stats.json`.
- [x] Writes `ai-journal/daily/YYYY-MM-DD.md`.
- [x] Supports dry-run prompt inspection.
