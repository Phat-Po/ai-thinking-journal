#!/bin/bash
set -u

# Daily Thinking Summary — launchd wrapper
# Runs daily pipeline, plus weekly (Sunday) and monthly (last day of month).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/pipeline-$(date +%Y%m%d-%H%M%S).log"

{
  echo "=== Pipeline started: $(date) ==="

  # Load .env if present
  if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    . "$PROJECT_DIR/.env"
    set +a
  fi

  cd "$PROJECT_DIR" || exit 1

  # Step 1: Daily pipeline (always)
  echo "--- Daily pipeline ---"
  python3 scripts/04_daily_pipeline.py
  daily_status=$?
  if [ $daily_status -ne 0 ]; then
    echo "ERROR: Daily pipeline failed (exit $daily_status)"
    exit 1
  fi

  # Step 2: Weekly rollup (on Sundays)
  DOW=$(date +%u)  # 1=Mon, 7=Sun
  if [ "$DOW" = "7" ]; then
    echo "--- Weekly rollup ---"
    python3 scripts/05_weekly.py
    weekly_status=$?
    if [ $weekly_status -ne 0 ]; then
      echo "WARNING: Weekly rollup failed (exit $weekly_status)"
    fi
  else
    echo "--- Weekly rollup skipped (not Sunday, DOW=$DOW) ---"
  fi

  # Step 3: Monthly rollup (on last day of month)
  TOMORROW_DAY=$(date -v+1d +%d 2>/dev/null || date -d tomorrow +%d 2>/dev/null)
  if [ "$TOMORROW_DAY" = "01" ]; then
    echo "--- Monthly rollup ---"
    python3 scripts/06_monthly.py
    monthly_status=$?
    if [ $monthly_status -ne 0 ]; then
      echo "WARNING: Monthly rollup failed (exit $monthly_status)"
    fi
  else
    echo "--- Monthly rollup skipped (not last day of month) ---"
  fi

  echo "=== Pipeline finished: $(date) ==="

} > "$LOG_FILE" 2>&1
