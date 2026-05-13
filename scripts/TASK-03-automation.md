# Task 03: Automation & Output

**Goal**: Nightly launchd job that runs extraction + summarization and writes to Obsidian vault.

**Status**: Blocked by Task 01, 02

## Output Template

```yaml
---
date: YYYY-MM-DD
tags: [daily-thinking, ai-journal]
source: [claude-code, codex]
sessions: N
total_tokens: N
---
```

## LaunchAgent Plist

- Label: `com.pohanlee.daily-thinking-summary`
- Run at: 23:30 daily
- Script: `~/.claude/scripts/daily-thinking-summary.py`
- Log: `~/Library/Logs/daily-thinking-summary.log`

## Obsidian Output Path

Configurable via `.env`:
```
OBSIDIAN_VAULT_PATH=/path/to/vault
OUTPUT_FOLDER=daily-thinking
FILENAME_FORMAT={date}-daily-thinking.md
```

## Acceptance Criteria

- [ ] launchd job fires at 23:30
- [ ] Output appears in Obsidian vault
- [ ] Idempotent — running twice doesn't duplicate
- [ ] Logs success/failure to log file
