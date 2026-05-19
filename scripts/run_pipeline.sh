#!/bin/bash
set -u

# Daily Thinking Summary — launchd wrapper
# Runs yesterday's daily pipeline, plus weekly/monthly rollups when a period closes.

# Ensure lark-cli (under nvm) is reachable when run from launchd's minimal PATH
export PATH="/Users/pohanlee/.nvm/versions/node/v20.20.2/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/pipeline-$(date +%Y%m%d-%H%M%S).log"

YESTERDAY="$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d yesterday +%Y-%m-%d)"
PREVIOUS_MONTH="$(date -v-1d +%Y-%m 2>/dev/null || date -d yesterday +%Y-%m)"

{
  echo "=== Pipeline started: $(date) ==="

  # Load .env if present
  if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    . "$PROJECT_DIR/.env"
    set +a
  fi

  cd "$PROJECT_DIR" || exit 1

  # Step 1: Daily pipeline (always summarize the completed previous day)
  echo "--- Daily pipeline ($YESTERDAY) ---"
  python3 scripts/04_daily_pipeline.py --date "$YESTERDAY"
  daily_status=$?
  if [ $daily_status -ne 0 ]; then
    echo "ERROR: Daily pipeline failed (exit $daily_status) — continuing to poster step"
  fi

  # Step 1b: Daily poster prompt (non-blocking — failure does not affect daily journal)
  echo "--- Daily poster ($YESTERDAY) ---"
  python3 scripts/07_daily_poster.py --date "$YESTERDAY" || echo "WARNING: poster step failed (non-blocking)"

  # Step 2: Weekly rollup (on Mondays, summarize the week that ended yesterday)
  DOW=$(date +%u)  # 1=Mon, 7=Sun
  if [ "$DOW" = "1" ]; then
    echo "--- Weekly rollup ($YESTERDAY) ---"
    python3 scripts/05_weekly.py --date "$YESTERDAY"
    weekly_status=$?
    if [ $weekly_status -ne 0 ]; then
      echo "WARNING: Weekly rollup failed (exit $weekly_status)"
    fi
  else
    echo "--- Weekly rollup skipped (not Monday, DOW=$DOW) ---"
  fi

  # Step 3: Monthly rollup (on the 1st, summarize the month that ended yesterday)
  TODAY_DAY=$(date +%d)
  if [ "$TODAY_DAY" = "01" ]; then
    echo "--- Monthly rollup ($PREVIOUS_MONTH) ---"
    python3 scripts/06_monthly.py --month "$PREVIOUS_MONTH"
    monthly_status=$?
    if [ $monthly_status -ne 0 ]; then
      echo "WARNING: Monthly rollup failed (exit $monthly_status)"
    fi
  else
    echo "--- Monthly rollup skipped (not first day of month) ---"
  fi

  echo "=== Pipeline finished: $(date) ==="

} > "$LOG_FILE" 2>&1
