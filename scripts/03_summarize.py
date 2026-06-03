#!/usr/bin/env python3
"""
Task 03: Daily thinking journal summarization.

Consumes output/YYYY-MM-DD/session_summaries.md (legacy) OR
signal_conversations.md (--signal-only) + stats.json and writes
ai-journal/daily/YYYY-MM-DD.md.
"""

from __future__ import annotations

import encodings.idna  # noqa: F401  preload codec; fixes launchd "unknown encoding: idna"
import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
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
    parser.add_argument("--signal-only", action="store_true",
                        help="Read signal_conversations.md instead of session_summaries.md.")
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
    return """You are writing a personal thinking journal for a solo developer/entrepreneur
who uses AI coding assistants (Claude Code and Codex CLI) daily.

Write as if journaling for yourself — casual, specific, honest. First person ("我").
NOT a corporate report. NOT a task list. A diary entry you'd actually want to re-read.

Given:
1. Per-session summaries from today (between <summaries> tags)
2. Usage statistics (between <stats> tags) — includes per-project duration and which AI tool was used

<rules>
- Write in the SAME LANGUAGE as the dominant language in the summaries
- Total body: under 800 Chinese characters (or equivalent). Be concise.
- Extract REAL decisions and insights — never invent
- If there's genuinely nothing to write: output "今天沒有使用 AI 工具"
- Do NOT output YAML frontmatter or the date title — those are handled separately
- `available_skills` and `available_plugins` are environment inventory only — they do NOT mean those skills/plugins were used today
- Focus on what the USER was thinking about and deciding, not just what the AI did
</rules>

<format>
Output exactly this structure:

**今天** — 2-3 sentences: what occupied the day, the most important decision, one thing learned.

**工具用量** — One line summarizing the stats: how many Claude Code sessions vs Codex sessions, total messages, total tools called. Example: "Claude Code 113 sessions / 301 msgs · Codex 10 sessions / 112 msgs"

### 项目时间线

For each meaningful project (skip trivial one-off queries), write a short paragraph:
- Start with the project name and which tool was used: "(via Claude Code)" or "(via Codex)" — ALWAYS include this label
- Include the time spent if available: "约 2 小时"
- 1-3 sentences: what was done, why, what happened. Write like telling a friend, not a status report.
- Merge multiple sessions of the same project into one entry
- Order by time spent (most time first)

### 待办 + 想法

- Max 5 items total
- Only genuinely actionable todos or real insights worth remembering
- One sentence each, concrete (include file names or specific steps)
- If nothing worth noting: write "无"
</format>

<example>
**今天** 主力在搞日记自动化 pipeline，从提取到生成跑通了全流程。顺便把 VIBE Dashboard 46 个乱 commit squash 成 5 个。学到：prompt 没写清楚语气，输出就变公文。

**工具用量** Claude Code 113 sessions / 301 msgs · Codex 10 sessions / 112 msgs · 总计约 28h

### 项目时间线

**日记自动化** (via Claude Code · 约 4h)
从零写了 extraction 脚本，发现用 JSONL 的 cwd 字段比文件名解码准确。消息筛选只保留用户输入 + 助手最后一段，token 从 33K 砍到 6K。launchd 定时任务配好了，半夜自动跑。

**VIBE Dashboard** (via Codex · 约 3h)
健康检查改成 SWR 轮询重试。launcher 从 bash 改成 AppleScript applet 才解决启动失败。最大工程是 squash 46 个 commit。

**thermal-printer** (via Claude Code · 约 40min)
加了 Bottle Neck Wall tab，修了打印后跳页 bug。

### 待办 + 想法

- `02_session_summarize.py` 的 prompt 还没改成中文优先
- Codex 版本太旧不支持 `--enable hooks`，得升级
- launchd 跑 .env 的 OPENAI_API_KEY 要确认能正常读取
</example>

<stats>
%s
</stats>

<summaries>
%s
</summaries>
""" % (json.dumps(stats, ensure_ascii=False, indent=2), summaries)


def build_prompt_signal(signal_data: str, stats: Dict[str, Any]) -> str:
    return """You are writing a personal thinking journal for a solo developer/entrepreneur
who uses AI coding assistants (Claude Code and Codex CLI) daily.

Write as if journaling for yourself — casual, specific, honest. First person ("我").
NOT a corporate report. NOT a task list. A diary entry you'd actually want to re-read.

Given:
1. Signal data from today's AI conversations (between <signal> tags) — grouped by project, each session has a Recap (what the AI did) and the user's last Prompt
2. Usage statistics (between <stats> tags) — includes per-project duration and which AI tool was used

<rules>
- Write in the SAME LANGUAGE as the dominant language in the signal data
- Total body: under 800 Chinese characters (or equivalent). Be concise.
- Extract REAL decisions and insights — never invent
- If there's genuinely nothing to write: output "今天沒有使用 AI 工具"
- Do NOT output YAML frontmatter or the date title — those are handled separately
- `available_skills` and `available_plugins` are environment inventory only — they do NOT mean those skills/plugins were used today
- Focus on what the USER was thinking about and deciding, not just what the AI did
- The Recap tells you what happened; the Prompt tells you what the user cared about
</rules>

<format>
Output exactly this structure:

**今天** — 2-3 sentences: what occupied the day, the most important decision, one thing learned.

**工具用量** — One line summarizing the stats: how many Claude Code sessions vs Codex sessions, total messages, total tools called. Example: "Claude Code 113 sessions / 301 msgs · Codex 10 sessions / 112 msgs"

### 项目时间线

For each meaningful project (skip trivial one-off queries), write a short paragraph:
- Start with the project name and which tool was used: "(via Claude Code)" or "(via Codex)" — ALWAYS include this label
- Include the time spent if available: "约 2 小时"
- 1-3 sentences: what was done, why, what happened. Write like telling a friend, not a status report.
- Merge multiple sessions of the same project into one entry
- Order by time spent (most time first)

### 待办 + 想法

- Max 5 items total
- Only genuinely actionable todos or real insights worth remembering
- One sentence each, concrete (include file names or specific steps)
- If nothing worth noting: write "无"
</format>

<example>
**今天** 主力在搞日记自动化 pipeline，从提取到生成跑通了全流程。顺便把 VIBE Dashboard 46 个乱 commit squash 成 5 个。学到：prompt 没写清楚语气，输出就变公文。

**工具用量** Claude Code 113 sessions / 301 msgs · Codex 10 sessions / 112 msgs · 总计约 28h

### 项目时间线

**日记自动化** (via Claude Code · 约 4h)
从零写了 extraction 脚本，发现用 JSONL 的 cwd 字段比文件名解码准确。消息筛选只保留用户输入 + 助手最后一段，token 从 33K 砍到 6K。launchd 定时任务配好了，半夜自动跑。

**VIBE Dashboard** (via Codex · 约 3h)
健康检查改成 SWR 轮询重试。launcher 从 bash 改成 AppleScript applet 才解决启动失败。最大工程是 squash 46 个 commit。

**thermal-printer** (via Claude Code · 约 40min)
加了 Bottle Neck Wall tab，修了打印后跳页 bug。

### 待办 + 想法

- `02_session_summarize.py` 的 prompt 还没改成中文优先
- Codex 版本太旧不支持 `--enable hooks`，得升级
- launchd 跑 .env 的 OPENAI_API_KEY 要确认能正常读取
</example>

<stats>
%s
</stats>

<signal>
%s
</signal>
""" % (json.dumps(stats, ensure_ascii=False, indent=2), signal_data)


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


def call_openai(prompt: str, model: str, max_retries: int = 3) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("Error: OPENAI_API_KEY not set.", file=sys.stderr)
        sys.exit(1)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }).encode("utf-8")

    last_exc = None
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            OPENAI_URL, data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=240) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except (http.client.RemoteDisconnected, TimeoutError, urllib.error.URLError, OSError) as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = 5 * (3 ** (attempt - 1))  # 5s, 15s, 45s
                print("WARNING: OpenAI attempt %d/%d failed (%s: %s), retrying in %ds..."
                      % (attempt, max_retries, type(exc).__name__, exc, delay), file=sys.stderr)
                time.sleep(delay)
            else:
                print("ERROR: OpenAI all %d attempts failed. Last error: %s" % (max_retries, exc), file=sys.stderr)
    raise last_exc


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
    stats_path = extraction_dir / "stats.json"

    if args.signal_only:
        signal_path = extraction_dir / "signal_conversations.md"
        if not signal_path.exists() or not stats_path.exists():
            print("Error: signal artifacts not found for %s" % date_str, file=sys.stderr)
            print("Run 01_extract.py --signal-only --date %s first." % date_str, file=sys.stderr)
            sys.exit(1)
        signal_data = signal_path.read_text(encoding="utf-8")
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        prompt = build_prompt_signal(signal_data, stats)
    else:
        summaries_path = extraction_dir / "session_summaries.md"
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
