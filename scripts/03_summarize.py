#!/usr/bin/env python3
"""
Task 03: Daily thinking journal summarization.

Consumes output/YYYY-MM-DD/session_summaries.md + stats.json and writes
ai-journal/daily/YYYY-MM-DD.md.
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
from typing import Any, Dict, List

TZ_LOCAL = timezone(timedelta(hours=8))
OLLAMA_URL = "http://localhost:11434/api/chat"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OLLAMA_MODEL = "qwen3-coder:480b-cloud"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily AI thinking journal")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD). Default: today UTC+8.")
    parser.add_argument("--backend", default=os.getenv("LLM_BACKEND", "openai"),
                        choices=["ollama", "openai"], help="LLM backend.")
    parser.add_argument("--model", default=None, help="Model name override.")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent.parent / "output"))
    parser.add_argument("--journal-root",
                        default=os.getenv("AI_JOURNAL_ROOT", str(Path(__file__).parent.parent / "ai-journal")))
    parser.add_argument("--dry-run", action="store_true", help="Print prompt only.")
    return parser.parse_args()


def target_date(args_date: str) -> str:
    if args_date:
        datetime.strptime(args_date, "%Y-%m-%d")
        return args_date
    return datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")


def weekday_name(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")


def yaml_scalar(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    text = str(value).replace('"', '\\"')
    return '"%s"' % text


def yaml_inline_dict(data: Dict[str, Any]) -> str:
    parts = []
    for key, value in data.items():
        parts.append("%s: %s" % (key, yaml_scalar(value)))
    return "{" + ", ".join(parts) + "}"


def build_frontmatter(date_str: str, stats: Dict[str, Any]) -> str:
    lines: List[str] = [
        "---",
        'date: "%s"' % date_str,
        "type: daily",
        "weekday: %s" % weekday_name(date_str),
        "tools_used:",
    ]

    tools_used = stats.get("tools_used", {})
    for source in ("claude_code", "codex"):
        source_stats = tools_used.get(source, {})
        messages = source_stats.get("messages", {})
        tools = source_stats.get("tools", {})
        lines.append("  %s:" % source)
        lines.append("    sessions: %s" % int(source_stats.get("sessions", 0)))
        lines.append("    messages: %s" % yaml_inline_dict(messages))
        lines.append("    tools: %s" % yaml_inline_dict(tools))

    lines.append("projects_touched:")
    projects = stats.get("projects_touched", [])
    if projects:
        for project in projects:
            lines.append("  - %s" % yaml_inline_dict(project))
    else:
        lines.append("  []")

    lines.append("total_duration_estimate_min: %s" % int(stats.get("total_duration_estimate_min", 0)))
    lines.append("---")
    return "\n".join(lines) + "\n"


def build_prompt(summaries: str, stats: Dict[str, Any]) -> str:
    return """You are a thinking journal analyst for a solo entrepreneur who builds
e-commerce businesses and AI automation tools.

Given:
1. Per-session summaries from today (between <summaries> tags)
2. Tool usage statistics (between <stats> tags)

Produce a daily thinking journal entry.

<rules>
- Write in the SAME LANGUAGE as the dominant language in the summaries
- Each bullet: one sentence max, concrete and specific
- Extract REAL decisions and todos - never invent
- If a section has nothing: write "無"
- Do NOT output YAML frontmatter or the date title - those are handled separately
- The "工具使用觀察" section should note patterns in HOW different tools
  were used (exploration vs execution, which tool for which type of thinking),
  NOT just list what tools were called
- `available_skills` and `available_plugins` are environment inventory only.
  They do NOT mean those skills/plugins were used today.
- The "原始對話索引" section: re-organize session summaries by project,
  merge sessions that belong to the same project, keep 2-4 bullets each.
</rules>

<sections>
## 今日主題
## 關鍵決策
## 待辦事項
## 思考亮點
## 工具使用觀察
## 原始對話索引
</sections>

<stats>
%s
</stats>

<summaries>
%s
</summaries>
""" % (json.dumps(stats, ensure_ascii=False, indent=2), summaries)


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
    with urllib.request.urlopen(req, timeout=240) as resp:
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
    with urllib.request.urlopen(req, timeout=240) as resp:
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

    extraction_dir = Path(args.output_dir) / date_str
    summaries_path = extraction_dir / "session_summaries.md"
    stats_path = extraction_dir / "stats.json"
    if not summaries_path.exists() or not stats_path.exists():
        print("Error: artifacts not found for %s" % date_str, file=sys.stderr)
        print("Run 01_extract.py then 02_session_summarize.py --date %s first." % date_str, file=sys.stderr)
        sys.exit(1)

    summaries = summaries_path.read_text(encoding="utf-8")
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    prompt = build_prompt(summaries, stats)

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

    journal_daily_dir = Path(args.journal_root) / "daily"
    journal_daily_dir.mkdir(parents=True, exist_ok=True)
    output_path = journal_daily_dir / ("%s.md" % date_str)
    content = build_frontmatter(date_str, stats) + "\n# %s %s\n\n%s\n" % (
        date_str,
        weekday_name(date_str),
        summary,
    )
    output_path.write_text(content, encoding="utf-8")
    print("Output written to: %s" % output_path)


if __name__ == "__main__":
    main()
