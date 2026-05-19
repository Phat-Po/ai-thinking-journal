# Handoff — Pipeline Resilience Fix (2026-05-18)

## URGENT: Pipeline broken since May 15. User has not received daily poster prompt for 3 days.

## What Happened (timeline)

1. **May 15 23:49** — Pipeline ran, extraction OK (25 sessions), `02_session_summarize.py` hit `BrokenPipeError` calling OpenAI API (transient network). Pipeline exit 1. Poster step never ran.
2. **May 16 00:00** — Skipped extraction (output existed). Summarization failed again. No poster.
3. **May 17 00:00** — Extraction ran but produced empty `filtered_conversations.md` (header only, 0 messages). Summarization: "No sessions found". No poster.
4. **May 18 00:00** — Same as May 17. Empty extraction → fail → no poster.

## Root Cause — 3 Bugs to Fix

### Bug 1: Empty extraction output poisons the pipeline

**File**: `scripts/01_extract.py`, function `main()` lines 564-567

`build_markdown()` returns just the header line when no messages pass filtering. The file gets written anyway. Then `04_daily_pipeline.py` line 74 skip logic (`if conversations_path.exists()`) treats it as "done" and skips extraction on all future runs.

**Fix**: After `build_markdown()`, check for `<!-- SESSION:` marker. If absent, write a `.EMPTY` sentinel instead of `filtered_conversations.md`.

```python
# In main(), replace lines 564-567:
conversations = build_markdown(date_str, sessions)
if "<!-- SESSION:" not in conversations:
    (output_root / "filtered_conversations.EMPTY").write_text(conversations, encoding="utf-8")
    print("WARNING: No sessions with messages found for %s" % date_str)
else:
    conversations_path.write_text(conversations, encoding="utf-8")
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

### Bug 2: Pipeline exit blocks poster step

**File**: `scripts/run_pipeline.sh`, lines 35-39

`exit 1` on daily pipeline failure aborts the entire script. Step 07 (poster, line 42) never runs, even though it's explicitly designed as non-blocking.

**Fix**: Remove `exit 1`. Log failure, continue to poster.

```bash
# Replace lines 35-39:
  python3 scripts/04_daily_pipeline.py --date "$YESTERDAY"
  daily_status=$?
  if [ $daily_status -ne 0 ]; then
    echo "ERROR: Daily pipeline failed (exit $daily_status) — continuing to poster step"
  fi
```

### Bug 3: Skip logic doesn't validate content

**File**: `scripts/04_daily_pipeline.py`, line 74

Skip logic only checks file existence, not whether the file has real content.

**Fix**: Add size/content check.

```python
# Replace line 74:
if not args.force and conversations_path.exists() and conversations_path.stat().st_size > 100:
```

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `scripts/01_extract.py` | 564-567 | Write `.EMPTY` sentinel instead of empty `filtered_conversations.md` |
| `scripts/04_daily_pipeline.py` | 74 | Add `st_size > 100` to skip condition |
| `scripts/run_pipeline.sh` | 35-39 | Remove `exit 1`, log failure, continue |

## Verification Steps

1. Delete `output/2026-05-17/` and re-run extraction — should create `.EMPTY` sentinel
2. Run `python3 scripts/04_daily_pipeline.py --date 2026-05-17` — should fail at step 02 but not crash hard
3. Run `bash scripts/run_pipeline.sh` — poster step should execute even if daily pipeline fails
4. Run full pipeline for a date with real data (e.g., 2026-05-14) with `--force` — all steps complete
5. Verify poster prompt arrives in Lark DM

## After Fix — Immediate User Need

User wants their daily poster prompt. Once pipeline is fixed, generate it:

```bash
cd "/Volumes/轻松打爆你/VIBE CODING/10_PROJECTS_ACTIVE/20260514__automation__daily-thinking-summary"
source .env
python3 scripts/07_daily_poster.py --date 2026-05-17
```

Requires `ai-journal/daily/2026-05-17.md` to exist. If it doesn't, the daily pipeline (steps 01-03) must succeed first.

## Project Context (preserved from previous handoff)

### Pipeline Flow

```
01_extract.py           → output/YYYY-MM-DD/filtered_conversations.md + stats.json
02_session_summarize.py → output/YYYY-MM-DD/session_summaries.md
03_summarize.py         → ai-journal/daily/YYYY-MM-DD.md
04_daily_pipeline.py    → orchestrator (runs 01→02→03, idempotent)
05_weekly.py            → ai-journal/weekly/YYYY-WNN.md (from 7 daily files)
06_monthly.py           → ai-journal/monthly/YYYY-MM.md (from weekly + daily YAML)
07_daily_poster.py      → ai-journal/posters/YYYY-MM-DD-prompt.md + Lark DM
run_pipeline.sh         → launchd wrapper (daily + conditional weekly/monthly + poster)
```

All scripts support `--date YYYY-MM-DD` and `--dry-run`. Steps 02, 03, 05, 06 support `--backend openai|ollama`.

### Automation

- `launchd/com.pohanlee.daily-thinking-summary.plist` — runs at midnight daily
- Installed: `launchctl list | grep daily-thinking`
- Logs: `logs/pipeline-YYYYMMDD-HHMMSS.log`

### Known Caveats

- Host `python3` is 3.8.1; all code is Python 3.8-compatible
- `output/` and `logs/` are git-ignored
- launchd won't run if Mac is asleep — runs on wake (StartCalendarInterval behavior)
- `.env` has `OPENAI_API_KEY` — never commit

### File Inventory

```
scripts/01_extract.py              — extraction (Claude Code + Codex JSONL → markdown + stats)
scripts/02_session_summarize.py    — per-session LLM summaries
scripts/03_summarize.py            — daily journal generation
scripts/04_daily_pipeline.py       — orchestrator: runs 01→02→03
scripts/05_weekly.py               — weekly rollup
scripts/06_monthly.py              — monthly rollup
scripts/07_daily_poster.py         — poster prompt → OpenAI → Lark DM
scripts/run_pipeline.sh            — launchd wrapper
launchd/com.pohanlee.daily-thinking-summary.plist — macOS scheduling
ai-journal/daily/*.md              — daily journals
ai-journal/posters/                — poster prompts + generated covers
skills/journal-xhsposter/          — poster skill definition
```

### What Remains (from previous handoff)

- Monthly rollup not yet tested with real data
- Obsidian vault integration
- Git sync option for cloud backup
- Prompt versioning
