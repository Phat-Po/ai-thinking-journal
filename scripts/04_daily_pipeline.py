#!/usr/bin/env python3
"""
Task 04: Daily pipeline orchestrator.

Runs 01_extract → 02_session_summarize → 03_summarize in sequence.
Idempotent: skips steps whose output already exists unless --force is given.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ_LOCAL = timezone(timedelta(hours=8))
SCRIPTS_DIR = Path(__file__).parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full daily journal pipeline")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD). Default: today UTC+8.")
    parser.add_argument("--backend", default="openai", choices=["ollama", "openai"],
                        help="LLM backend for steps 02 and 03.")
    parser.add_argument("--model", default=None, help="Model name override.")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent.parent / "output"))
    parser.add_argument("--journal-root", default=os.getenv("AI_JOURNAL_ROOT", str(Path(__file__).parent.parent / "ai-journal")))
    parser.add_argument("--force", action="store_true", help="Re-run even if output exists.")
    parser.add_argument("--signal-only", action="store_true",
                        help="Use --signal-only extraction (skip Step 02, Step 03 reads signal data).")
    parser.add_argument("--dry-run", action="store_true", help="Print what would run.")
    return parser.parse_args()


def target_date(args_date: str) -> str:
    if args_date:
        datetime.strptime(args_date, "%Y-%m-%d")
        return args_date
    return datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")


def run_step(label: str, cmd: list, dry_run: bool) -> bool:
    print("\n=== %s ===" % label)
    if dry_run:
        print("  [dry-run] %s" % " ".join(cmd))
        return True
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("FAILED: %s (exit %d)" % (label, result.returncode), file=sys.stderr)
        return False
    return True


def main() -> None:
    args = parse_args()
    date_str = target_date(args.date)
    output_dir = Path(args.output_dir) / date_str

    signal_path = output_dir / "signal_conversations.md"
    conversations_path = output_dir / "filtered_conversations.md"
    session_summaries_path = output_dir / "session_summaries.md"
    journal_path = Path(args.journal_root) / "daily" / ("%s.md" % date_str)

    base_cmd = ["python3"]
    extra_args = []
    if args.backend:
        extra_args += ["--backend", args.backend]
    if args.model:
        extra_args += ["--model", args.model]
    extra_args += ["--output-dir", args.output_dir]

    # Step 01: Extract
    step01_cmd = base_cmd + [str(SCRIPTS_DIR / "01_extract.py"), "--date", date_str,
                             "--output-dir", args.output_dir]
    if args.signal_only:
        step01_cmd.append("--signal-only")
    check_path = signal_path if args.signal_only else conversations_path
    if not args.force and check_path.exists() and check_path.stat().st_size > 100:
        print("=== 01_extract === (skipped, output exists)")
    elif not run_step("01_extract", step01_cmd, args.dry_run):
        sys.exit(1)

    # Step 02: Session summarize (skipped in signal-only mode)
    if args.signal_only:
        print("=== 02_session_summarize === (skipped, signal-only mode)")
    else:
        step02_cmd = base_cmd + [str(SCRIPTS_DIR / "02_session_summarize.py"), "--date", date_str] + extra_args
        if not args.force and session_summaries_path.exists() and session_summaries_path.stat().st_size > 100:
            print("=== 02_session_summarize === (skipped, output exists)")
        elif not run_step("02_session_summarize", step02_cmd, args.dry_run):
            sys.exit(1)

    # Step 03: Daily summarize
    step03_cmd = base_cmd + [str(SCRIPTS_DIR / "03_summarize.py"), "--date", date_str] + extra_args
    step03_cmd += ["--journal-root", args.journal_root]
    if args.signal_only:
        step03_cmd.append("--signal-only")
    if not args.force and journal_path.exists() and journal_path.stat().st_size > 100:
        print("=== 03_summarize === (skipped, output exists)")
    elif not run_step("03_summarize", step03_cmd, args.dry_run):
        sys.exit(1)

    print("\n=== Done ===")
    if journal_path.exists():
        print("Journal: %s" % journal_path)
    elif args.dry_run:
        print("[dry-run] Would write: %s" % journal_path)


if __name__ == "__main__":
    main()
