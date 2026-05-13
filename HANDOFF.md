# Handoff - Daily Thinking Summary Pipeline

## Current Status

Task 01 (Extraction) - complete, HTML comment separators + dedup logic
Task 02 (Session Summarization) - complete, per-session LLM summaries via OpenAI or Ollama
Task 03 (Daily Summarization) - complete, consumes session summaries instead of raw conversations
Task 04 (Automation / Weekly / Monthly) - not started

Latest commit: `7e1c82a` — working tree clean.

## Pipeline Flow (3-step)

```
01_extract.py        → output/YYYY-MM-DD/filtered_conversations.md + stats.json
02_session_summarize.py → output/YYYY-MM-DD/session_summaries.md
03_summarize.py      → ai-journal/daily/YYYY-MM-DD.md
```

All three scripts support `--date YYYY-MM-DD` and `--dry-run`.
Steps 02 and 03 support `--backend openai|ollama` (default: openai).
OpenAI uses `gpt-4.1-mini` by default; Ollama uses `qwen3-coder:480b-cloud`.
Cost: ~$0.04/day with gpt-4.1-mini.

## What Was Done This Session

### Bug 1: Heading conflict fix
- Session separators: `## source - project` → `<!-- SESSION: source - project (HH:MM-HH:MM) -->`
- Message headers: `### HH:MM - role` → `<!-- MSG: HH:MM - role -->`
- Content markdown headings no longer conflict with structural markers.

### Bug 2: Dedup skill/template content
- Messages >500 chars with identical first-500-char hash → `[重复内容已省略 — 见上方 session]`
- Messages matching skill frontmatter pattern → `[引用了 skill 文件内容]`
- Logic in place; no dedup triggered on 2026-05-14 data (no duplicates that day).

### Architecture: Per-session pre-summarization
- New `scripts/02_session_summarize.py` splits filtered_conversations.md by `<!-- SESSION: -->` markers.
- Each session gets a 3-5 bullet LLM summary (~68K input tokens → ~3K output tokens).
- Old `scripts/02_summarize.py` renamed to `scripts/03_summarize.py`.
- `03_summarize.py` now reads `session_summaries.md` (~4KB) instead of raw conversations (~170KB).
- Daily summary prompt updated for session-summary input.

### OpenAI backend added
- Both 02 and 03 scripts support `--backend openai|ollama`.
- Default changed to openai because Ollama cloud models had network issues (`ollama.com` unreachable).
- API key read from `OPENAI_API_KEY` env var (never hardcoded).

## Verified Commands

```bash
python3 -m py_compile scripts/01_extract.py scripts/02_session_summarize.py scripts/03_summarize.py
python3 scripts/01_extract.py --date 2026-05-14
python3 scripts/02_session_summarize.py --date 2026-05-14
python3 scripts/03_summarize.py --date 2026-05-14
```

Full pipeline output verified: `ai-journal/daily/2026-05-14.md` — quality good.

## Known Caveats

- Host `python3` is 3.8.1; all code is Python 3.8-compatible.
- Generated `output/` artifacts are ignored by git.
- Ollama cloud models (`*-cloud`) require internet via ollama.com; local models work offline.
- `TASK-03-automation.md` references old filenames (`03_daily_pipeline.py`, `04_weekly.py`, `05_monthly.py`) — needs updating to match current naming.

## What Remains: Task 04 (per TASK-03-automation.md)

1. **Daily orchestration script** — wrapper that runs 01→02→03 in sequence, idempotent.
2. **macOS scheduling** — launchd plist for nightly execution with logging.
3. **Weekly rollup** — read 7 daily markdown files → `ai-journal/weekly/YYYY-WNN.md`.
4. **Monthly rollup** — read weekly + daily YAML metadata → `ai-journal/monthly/YYYY-MM.md`.
5. **No git push** without explicit operator approval.

Acceptance criteria are in `scripts/TASK-03-automation.md`.

## File Inventory

```
scripts/01_extract.py              — extraction (Claude Code + Codex JSONL → markdown + stats)
scripts/02_session_summarize.py    — per-session LLM summaries
scripts/03_summarize.py            — daily journal generation from session summaries
scripts/TASK-01-extraction-poc.md  — task 01 spec (done)
scripts/TASK-02-summarization.md   — task 02 spec (done)
scripts/TASK-03-automation.md      — task 03/04 spec (not started, filenames outdated)
ai-thinking-journal-product-spec.md — product spec
ai-journal/daily/2026-05-14.md     — verified sample output
HANDOFF.md                         — this file
STATUS.md                          — chronological event log
INVESTIGATION.md                   — initial feasibility investigation
```
