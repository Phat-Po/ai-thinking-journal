# Handoff - Daily Thinking Summary Pipeline

## Current Status

Task 01 (Extraction) - complete, HTML comment separators + dedup logic
Task 02 (Session Summarization) - complete, per-session LLM summaries via OpenAI or Ollama
Task 03 (Daily Summarization) - complete, consumes session summaries instead of raw conversations
Task 04 (Automation / Weekly / Monthly) - **complete**

Latest commit: `86d3f85` — tone fix applied.

## Pipeline Flow (5-step)

```
01_extract.py           → output/YYYY-MM-DD/filtered_conversations.md + stats.json
02_session_summarize.py → output/YYYY-MM-DD/session_summaries.md
03_summarize.py         → ai-journal/daily/YYYY-MM-DD.md
04_daily_pipeline.py    → orchestrator (runs 01→02→03, idempotent)
05_weekly.py            → ai-journal/weekly/YYYY-WNN.md (from 7 daily files)
06_monthly.py           → ai-journal/monthly/YYYY-MM.md (from weekly + daily YAML)
```

All scripts support `--date YYYY-MM-DD` (or `--month YYYY-MM` for monthly) and `--dry-run`.
Steps 02, 03, 05, 06 support `--backend openai|ollama` (default: openai).
OpenAI uses `gpt-4.1-mini` by default; Ollama uses `qwen3-coder:480b-cloud`.
Cost: ~$0.04/day with gpt-4.1-mini.

## Automation

`scripts/run_pipeline.sh` — launchd wrapper that:
1. Always runs daily pipeline (01→02→03)
2. On Sundays: also runs weekly rollup
3. On last day of month: also runs monthly rollup
4. Loads `.env` for API keys
5. Logs to `logs/pipeline-YYYYMMDD-HHMMSS.log`

`launchd/com.pohanlee.daily-thinking-summary.plist` — runs at midnight daily.

### To install (after review):
```bash
cp launchd/com.pohanlee.daily-thinking-summary.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.pohanlee.daily-thinking-summary.plist
```

### To check status:
```bash
launchctl list | grep daily-thinking
```

### Logs:
- Pipeline logs: `logs/pipeline-*.log`
- launchd stdout: `logs/launchd-stdout.log`
- launchd stderr: `logs/launchd-stderr.log`

## Tone

All LLM prompts (daily, weekly, monthly) follow diary-style writing:
- First person ("我"), casual, specific, honest
- Bad/good examples in every prompt to steer LLM away from corporate report style
- Section-specific writing guides with concrete anti-patterns

## Verified Commands

```bash
python3 -m py_compile scripts/01_extract.py scripts/02_session_summarize.py scripts/03_summarize.py scripts/04_daily_pipeline.py scripts/05_weekly.py scripts/06_monthly.py
python3 scripts/01_extract.py --date 2026-05-14
python3 scripts/02_session_summarize.py --date 2026-05-14
python3 scripts/03_summarize.py --date 2026-05-14
python3 scripts/04_daily_pipeline.py --date 2026-05-14
python3 scripts/05_weekly.py --date 2026-05-14 --dry-run
python3 scripts/06_monthly.py --month 2026-05 --dry-run
```

Full pipeline output verified: `ai-journal/daily/2026-05-14.md` — quality good.

## Known Caveats

- Host `python3` is 3.8.1; all code is Python 3.8-compatible.
- Generated `output/` and `logs/` artifacts are ignored by git.
- Ollama cloud models (`*-cloud`) require internet via ollama.com; local models work offline.
- Weekly/monthly rollups need at least one daily file to exist; they'll error gracefully if none found.
- launchd won't run if Mac is asleep at midnight — it runs when the Mac wakes up (StartCalendarInterval behavior).

## File Inventory

```
scripts/01_extract.py              — extraction (Claude Code + Codex JSONL → markdown + stats)
scripts/02_session_summarize.py    — per-session LLM summaries
scripts/03_summarize.py            — daily journal generation from session summaries
scripts/04_daily_pipeline.py       — orchestrator: runs 01→02→03, idempotent
scripts/05_weekly.py               — weekly rollup (7 daily → weekly journal)
scripts/06_monthly.py              — monthly rollup (weekly + daily YAML → monthly journal)
scripts/run_pipeline.sh            — launchd wrapper (daily + conditional weekly/monthly)
launchd/com.pohanlee.daily-thinking-summary.plist — macOS scheduling
scripts/TASK-01-extraction-poc.md  — task 01 spec (done)
scripts/TASK-02-summarization.md   — task 02 spec (done)
scripts/TASK-03-automation.md      — task 03/04 spec (done, filenames outdated)
ai-thinking-journal-product-spec.md — product spec
ai-journal/daily/2026-05-14.md     — verified sample output
HANDOFF.md                         — this file
STATUS.md                          — chronological event log
INVESTIGATION.md                   — initial feasibility investigation
```

## What Remains

Nothing in the current scope. Potential future work:
- Historical data backfill (Codex has 6 months of data)
- Obsidian vault integration (move output into actual vault)
- Git sync option for cloud backup
- Prompt versioning (track prompt changes over time)
