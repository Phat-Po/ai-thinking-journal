# Task 03: Automation, Weekly, Monthly

**Goal**: Automate the daily journal and add weekly/monthly rollups.

**Status**: Not started after product-spec scope change

## Current Baseline

- `scripts/01_extract.py` now produces daily intermediate files.
- `scripts/02_summarize.py` now produces daily Obsidian markdown.
- Daily end-to-end flow has been verified manually.

## Required Scope

Task 03 is no longer only a launchd wrapper. Per `ai-thinking-journal-product-spec.md`, it now includes:

- Daily orchestration script: extract -> summarize -> `ai-journal/daily/YYYY-MM-DD.md`
- macOS scheduling via launchd or cron
- Weekly rollup: read seven daily markdown files and write `ai-journal/weekly/YYYY-WNN.md`
- Monthly rollup: read weekly markdown plus daily YAML metadata and write `ai-journal/monthly/YYYY-MM.md`
- Optional git sync must remain gated by explicit push approval

## Proposed Files

```text
scripts/03_daily_pipeline.py
scripts/04_weekly.py
scripts/05_monthly.py
launchd/com.pohanlee.ai-thinking-journal.plist
```

## Acceptance Criteria

- [ ] Daily pipeline is idempotent.
- [ ] launchd or cron writes logs for success/failure.
- [ ] Weekly rollup reads existing daily files and writes weekly markdown.
- [ ] Monthly rollup reads weekly files plus daily YAML metadata.
- [ ] No git push or deployment happens without explicit approval.
