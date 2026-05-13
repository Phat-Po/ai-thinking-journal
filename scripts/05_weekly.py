#!/usr/bin/env python3
"""
Task 05: Weekly thinking rollup.

Reads 7 daily journal markdown files and generates
ai-journal/weekly/YYYY-WNN.md via LLM.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TZ_LOCAL = timezone(timedelta(hours=8))
OLLAMA_URL = "http://localhost:11434/api/chat"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OLLAMA_MODEL = "qwen3-coder:480b-cloud"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"

# Match YAML frontmatter between --- markers
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate weekly thinking rollup")
    parser.add_argument("--date", default=None,
                        help="Any date in the target week (YYYY-MM-DD). Default: today UTC+8.")
    parser.add_argument("--backend", default=os.getenv("LLM_BACKEND", "openai"),
                        choices=["ollama", "openai"], help="LLM backend.")
    parser.add_argument("--model", default=None, help="Model name override.")
    parser.add_argument("--journal-root",
                        default=os.getenv("AI_JOURNAL_ROOT",
                                          str(Path(__file__).parent.parent / "ai-journal")))
    parser.add_argument("--dry-run", action="store_true", help="Print prompt only.")
    return parser.parse_args()


def target_date(args_date: Optional[str]) -> str:
    if args_date:
        datetime.strptime(args_date, "%Y-%m-%d")
        return args_date
    return datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")


def iso_week(date_str: str) -> Tuple[int, int]:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    cal = d.isocalendar()
    return cal[0], cal[1]


def week_date_range(year: int, week: int) -> Tuple[str, str]:
    """Return (monday, sunday) as YYYY-MM-DD strings for the given ISO week."""
    jan4 = datetime(year, 1, 4).date()
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    monday = start_of_week1 + timedelta(weeks=week - 1)
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def find_daily_files(journal_root: str, date_str: str) -> List[Tuple[str, Path]]:
    """Find daily files for the ISO week containing date_str. Returns [(date_str, path), ...]."""
    year, week = iso_week(date_str)
    monday_str, sunday_str = week_date_range(year, week)
    daily_dir = Path(journal_root) / "daily"
    if not daily_dir.exists():
        return []

    results = []
    current = datetime.strptime(monday_str, "%Y-%m-%d").date()
    end = datetime.strptime(sunday_str, "%Y-%m-%d").date()
    while current <= end:
        ds = current.strftime("%Y-%m-%d")
        path = daily_dir / ("%s.md" % ds)
        if path.exists():
            results.append((ds, path))
        current += timedelta(days=1)
    return results


def parse_frontmatter(text: str) -> Dict[str, Any]:
    """Extract YAML frontmatter as a dict. Simple parser — no full YAML dependency."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"')
    return fm


def extract_session_count(text: str, source: str) -> int:
    """Extract session count from nested YAML frontmatter using regex."""
    # Match: source:\n    sessions: N
    pattern = r"%s:\s*\n\s+sessions:\s*(\d+)" % source
    match = re.search(pattern, text)
    if match:
        return int(match.group(1))
    return 0


def extract_projects(text: str) -> List[str]:
    """Extract project names from projects_touched in frontmatter."""
    projects = []
    for match in re.finditer(r'- \{name:\s*"([^"]+)"', text):
        name = match.group(1)
        if name not in projects:
            projects.append(name)
    return projects


def aggregate_stats(files: List[Tuple[str, Path]]) -> Dict[str, Any]:
    """Aggregate YAML metadata from daily files."""
    agg = {
        "week_days": len(files),
        "total_sessions": {"claude_code": 0, "codex": 0},
        "top_projects": {},  # name -> days active
    }
    for _date, path in files:
        text = path.read_text(encoding="utf-8")
        # Use regex on raw text — simpler and handles nested YAML
        for source in ("claude_code", "codex"):
            agg["total_sessions"][source] += extract_session_count(text, source)
        for name in extract_projects(text):
            agg["top_projects"][name] = agg["top_projects"].get(name, 0) + 1
    return agg


def build_weekly_frontmatter(date_range: str, week_label: str,
                             files: List[Tuple[str, Path]], agg: Dict[str, Any]) -> str:
    lines = [
        "---",
        'date_range: "%s"' % date_range,
        "type: weekly",
        "week: \"%s\"" % week_label,
        "total_sessions: %s" % json.dumps(agg["total_sessions"]),
        "total_days: %d" % len(files),
        "top_projects:",
    ]
    for name, count in sorted(agg["top_projects"].items(), key=lambda x: -x[1]):
        lines.append("  - {name: \"%s\", days: %d}" % (name, count))
    if not agg["top_projects"]:
        lines.append("  []")
    lines.append("---")
    return "\n".join(lines) + "\n"


def build_prompt(daily_entries: str, date_range: str) -> str:
    return """You are writing a weekly thinking review for a solo entrepreneur who builds
e-commerce businesses and AI automation tools.

This is a personal journal, not a corporate report.
Write as if the person is flipping through their week's notes and reflecting.
Casual, specific, honest. Use first person ("我") when natural.
Avoid phrases like "有效推進" "系統性整合" "形成完整閉環" — nobody talks like that when reviewing their own week.

Given 7 daily journal entries (between <daily_entries> tags),
produce a weekly review that captures the arc of the week.

<rules>
- Write in the SAME LANGUAGE as the daily entries
- Focus on PROGRESS and PATTERNS, not activity lists
- If a section has nothing: write "無"
- Do NOT output YAML frontmatter or the date title — those are handled separately
- Be honest. If a week was scattered, say so.
</rules>

<section_guide>
## 本週三大推進
The 3 things that moved the needle most this week.
BAD: "完成每日摘要 pipeline 架構重構，實現多階段數據處理與自動化整合"
GOOD: "把每天的對話摘要拆成 session 預摘要再合併，終於不用一次塞 170K tokens 進去了"

## 未解決的問題
Things that are stuck, need rethinking, or were started but not finished.
Write like noting down something that's been bugging you.

## 本週決策回顧
Look back at decisions made this week. Tag each as [好決策] [待驗證] or [值得反思].
BAD: "決定使用本地模型替代雲端服務，有效降低成本並提升可控性"
GOOD: "[好決策] 改用 Ollama 本地跑，主要是離線也能用，而且一天省了幾塊美金"

## 工具使用趨勢
Patterns across the week — which tool for which type of work, any shifts.
NOT just "Claude Code 用了 X 次".

## 下週最重要的一件事
Based on momentum and blockers, what single thing would have the highest impact?
Write like you're telling yourself what to focus on Monday morning.
</section_guide>

<daily_entries>
%s
</daily_entries>

Date range: %s
""" % (daily_entries, date_range)


def call_ollama(prompt: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["message"]["content"].strip()
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def call_openai(prompt: str, model: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("Error: OPENAI_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def call_llm(prompt: str, model: str, backend: str) -> str:
    if backend == "openai":
        return call_openai(prompt, model)
    return call_ollama(prompt, model)


def main() -> None:
    args = parse_args()
    date_str = target_date(args.date)
    backend = args.backend
    if args.model:
        model = args.model
    elif backend == "openai":
        model = os.getenv("SUMMARY_MODEL", DEFAULT_OPENAI_MODEL)
    else:
        model = os.getenv("SUMMARY_MODEL", DEFAULT_OLLAMA_MODEL)

    journal_root = Path(args.journal_root)
    files = find_daily_files(str(journal_root), date_str)

    if not files:
        print("Error: No daily journal files found for the week containing %s." % date_str,
              file=sys.stderr)
        print("Expected files in: %s" % (journal_root / "daily"), file=sys.stderr)
        sys.exit(1)

    year, week = iso_week(date_str)
    monday_str, sunday_str = week_date_range(year, week)
    date_range = "%s ~ %s" % (monday_str, sunday_str)
    week_label = "%d-W%02d" % (year, week)

    print("Week: %s (%s)" % (week_label, date_range))
    print("Daily files found: %d" % len(files))

    # Read and concatenate daily entries
    entries = []
    for ds, path in files:
        text = path.read_text(encoding="utf-8")
        entries.append("### %s\n\n%s" % (ds, text))
    daily_entries = "\n\n---\n\n".join(entries)

    # Aggregate stats from frontmatter
    agg = aggregate_stats(files)

    prompt = build_prompt(daily_entries, date_range)

    if args.dry_run:
        print(prompt)
        return

    if backend == "ollama":
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        except Exception as exc:
            print("Error: Cannot reach Ollama: %s" % exc, file=sys.stderr)
            sys.exit(1)

    print("Backend: %s | Model: %s" % (backend, model))
    summary = call_llm(prompt, model, backend)

    weekly_dir = journal_root / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    output_path = weekly_dir / ("%s.md" % week_label)

    content = build_weekly_frontmatter(date_range, week_label, files, agg)
    content += "\n# %s 週刊\n\n%s\n" % (week_label, summary)
    output_path.write_text(content, encoding="utf-8")
    print("Output: %s" % output_path)


if __name__ == "__main__":
    main()
