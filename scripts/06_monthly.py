#!/usr/bin/env python3
"""
Task 06: Monthly thinking rollup.

Reads weekly rollups + daily YAML metadata and generates
ai-journal/monthly/YYYY-MM.md via LLM.
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

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate monthly thinking rollup")
    parser.add_argument("--month", default=None,
                        help="Target month (YYYY-MM). Default: current month UTC+8.")
    parser.add_argument("--backend", default=os.getenv("LLM_BACKEND", "openai"),
                        choices=["ollama", "openai"], help="LLM backend.")
    parser.add_argument("--model", default=None, help="Model name override.")
    parser.add_argument("--journal-root",
                        default=os.getenv("AI_JOURNAL_ROOT",
                                          str(Path(__file__).parent.parent / "ai-journal")))
    parser.add_argument("--dry-run", action="store_true", help="Print prompt only.")
    return parser.parse_args()


def target_month(args_month: Optional[str]) -> str:
    if args_month:
        datetime.strptime(args_month, "%Y-%m")
        return args_month
    return datetime.now(TZ_LOCAL).strftime("%Y-%m")


def find_weekly_files(journal_root: str, year: int, month: int) -> List[Tuple[str, Path]]:
    """Find weekly files that overlap with the given month."""
    weekly_dir = Path(journal_root) / "weekly"
    if not weekly_dir.exists():
        return []

    results = []
    for path in sorted(weekly_dir.glob("*.md")):
        name = path.stem  # e.g. 2026-W20
        match = re.match(r"(\d{4})-W(\d{2})", name)
        if not match:
            continue
        # Read frontmatter to get date_range
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        date_range = fm.get("date_range", "")
        # Check if any date in range falls in our month
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", date_range)
        for d in dates:
            parts = d.split("-")
            if int(parts[0]) == year and int(parts[1]) == month:
                results.append((name, path))
                break
    return results


def find_daily_files(journal_root: str, year: int, month: int) -> List[Tuple[str, Path]]:
    """Find daily files for the given month."""
    daily_dir = Path(journal_root) / "daily"
    if not daily_dir.exists():
        return []

    results = []
    prefix = "%d-%02d-" % (year, month)
    for path in sorted(daily_dir.glob("%s*.md" % prefix)):
        date_str = path.stem  # 2026-05-14
        results.append((date_str, path))
    return results


def extract_session_count(text: str, source: str) -> int:
    """Extract session count from nested YAML frontmatter using regex."""
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


def extract_daily_metadata(files: List[Tuple[str, Path]]) -> List[Dict[str, Any]]:
    """Extract metadata from daily files using regex on raw text."""
    entries = []
    for date_str, path in files:
        text = path.read_text(encoding="utf-8")
        entry = {
            "_date": date_str,
            "sessions": {},
            "projects": [],
        }
        for source in ("claude_code", "codex"):
            entry["sessions"][source] = extract_session_count(text, source)
        entry["projects"] = extract_projects(text)
        entries.append(entry)
    return entries


def aggregate_monthly_stats(daily_meta: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate stats from daily metadata for the monthly report."""
    agg = {
        "total_days": len(daily_meta),
        "total_sessions": {"claude_code": 0, "codex": 0},
        "top_projects": {},
    }
    for entry in daily_meta:
        for source in ("claude_code", "codex"):
            agg["total_sessions"][source] += entry["sessions"].get(source, 0)
        for name in entry["projects"]:
            agg["top_projects"][name] = agg["top_projects"].get(name, 0) + 1
    return agg


def build_monthly_frontmatter(month_label: str, date_range: str,
                              agg: Dict[str, Any]) -> str:
    lines = [
        "---",
        'date_range: "%s"' % date_range,
        "type: monthly",
        "month: \"%s\"" % month_label,
        "total_days: %d" % agg["total_days"],
        "total_sessions: %s" % json.dumps(agg["total_sessions"]),
        "top_projects:",
    ]
    for name, count in sorted(agg["top_projects"].items(), key=lambda x: -x[1]):
        lines.append("  - {name: \"%s\", active_days: %d}" % (name, count))
    if not agg["top_projects"]:
        lines.append("  []")
    lines.append("---")
    return "\n".join(lines) + "\n"


def build_prompt(weekly_entries: str, daily_stats: str, month_label: str, date_range: str) -> str:
    return """You are writing a monthly thinking review for a solo entrepreneur who builds
e-commerce businesses and AI automation tools.

This is a personal journal, not a corporate report.
Write as if the person is looking back at their month — reflecting on what happened,
what they learned, and where they're headed.
Casual, specific, honest. Use first person ("我") when natural.
Avoid phrases like "顯著提升" "深入優化" "形成完整生態" — nobody talks like that in their own journal.

Given:
1. Weekly reviews from this month (between <weekly_reviews> tags)
2. Aggregated daily metadata/stats (between <daily_stats> tags)

Produce a monthly review.

<rules>
- Write in the SAME LANGUAGE as the weekly reviews
- Focus on the NARRATIVE — what was this month about?
- If a section has nothing: write "無"
- Do NOT output YAML frontmatter or the title — those are handled separately
- Be reflective. This is for the person to read months later
  and understand who they were and what they were thinking.
</rules>

<section_guide>
## 本月覆盤
2-3 paragraphs. What was the month's story? Write like journaling at month-end.
BAD: "本月在自動化工具開發與電商運營方面取得顯著進展，完成多個核心功能模塊的設計與實現"
GOOD: "這個月主要在搞每天自動寫思考日記這件事。一開始想用雲端 API，後來發現太貴，改成本地 Ollama 跑，折騰了一個禮拜才穩定下來。"

## 項目進展地圖
Table format: project name, start state → end state, key milestone.
Be concrete about what changed, not vague "progress was made".

## 決策品質回顧
Look at decisions from the weekly reviews. How many turned out well?
Which ones need revisiting? Be honest with yourself.
BAD: "本月決策整體方向正確，有效平衡了成本與效率"
GOOD: "改用本地 Ollama 這個決定到目前為止是對的，但 gpt-4.1-mini 的輸出品質確實比本地模型好，之後可能要混合用"

## AI 工具使用演變
How did tool usage patterns shift this month? Any new habits or preferences?
What does it say about how you work?

## 下月關注重點
Based on what happened this month, what should next month focus on?
Write like planning your own priorities.
</section_guide>

<weekly_reviews>
%s
</weekly_reviews>

<daily_stats>
%s
</daily_stats>

Month: %s (%s)
""" % (weekly_entries, daily_stats, month_label, date_range)


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
    month_str = target_month(args.month)
    backend = args.backend
    if args.model:
        model = args.model
    elif backend == "openai":
        model = os.getenv("SUMMARY_MODEL", DEFAULT_OPENAI_MODEL)
    else:
        model = os.getenv("SUMMARY_MODEL", DEFAULT_OLLAMA_MODEL)

    year, month = [int(x) for x in month_str.split("-")]
    journal_root = Path(args.journal_root)

    # Find weekly files
    weekly_files = find_weekly_files(str(journal_root), year, month)
    if not weekly_files:
        print("Error: No weekly rollup files found for %s." % month_str, file=sys.stderr)
        print("Run 05_weekly.py for each week in this month first.", file=sys.stderr)
        sys.exit(1)

    # Find daily files for metadata
    daily_files = find_daily_files(str(journal_root), year, month)
    daily_meta = extract_daily_metadata(daily_files)
    agg = aggregate_monthly_stats(daily_meta)

    # Date range
    first_day = "%s-01" % month_str
    if month == 12:
        last_day = "%s-12-31" % year
    else:
        last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
    date_range = "%s ~ %s" % (first_day, last_day)

    print("Month: %s (%s)" % (month_str, date_range))
    print("Weekly files: %d | Daily files: %d" % (len(weekly_files), len(daily_files)))

    # Read weekly entries
    weekly_entries = []
    for name, path in weekly_files:
        text = path.read_text(encoding="utf-8")
        weekly_entries.append("### %s\n\n%s" % (name, text))
    weekly_text = "\n\n---\n\n".join(weekly_entries)

    # Build daily stats summary (metadata only, no body)
    daily_stats_lines = []
    for entry in daily_meta:
        date = entry.get("_date", "?")
        daily_stats_lines.append("- %s: sessions=%s/%s" % (
            date,
            entry.get("claude_code_sessions", "?"),
            entry.get("codex_sessions", "?"),
        ))
    daily_stats = "\n".join(daily_stats_lines)

    prompt = build_prompt(weekly_text, daily_stats, month_str, date_range)

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

    monthly_dir = journal_root / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)
    output_path = monthly_dir / ("%s.md" % month_str)

    content = build_monthly_frontmatter(month_str, date_range, agg)
    content += "\n# %s 月報\n\n%s\n" % (month_str, summary)
    output_path.write_text(content, encoding="utf-8")
    print("Output: %s" % output_path)


if __name__ == "__main__":
    main()
