#!/usr/bin/env python3
"""
Task 02: Per-session summarization.

Reads output/YYYY-MM-DD/filtered_conversations.md, splits by session,
calls Ollama for a 3-5 bullet summary per session, and writes
output/YYYY-MM-DD/session_summaries.md.
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
from typing import List, Tuple

TZ_LOCAL = timezone(timedelta(hours=8))
OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen3-coder:480b-cloud"

SESSION_RE = re.compile(r"^<!-- SESSION: (.+?) -->$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate per-session summaries via Ollama")
    parser.add_argument(
        "--date",
        default=None,
        help="Date to summarize (YYYY-MM-DD). Default: today in UTC+8.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("SUMMARY_MODEL", DEFAULT_MODEL),
        help="Ollama model name.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent / "output"),
        help="Directory containing extraction artifacts.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print prompts only; do not call Ollama.")
    return parser.parse_args()


def target_date(args_date):
    # type: (str) -> str
    if args_date:
        datetime.strptime(args_date, "%Y-%m-%d")
        return args_date
    return datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")


def split_sessions(text):
    # type: (str) -> List[Tuple[str, str]]
    matches = list(SESSION_RE.finditer(text))
    if not matches:
        return []
    sessions = []
    for i, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sessions.append((header, body))
    return sessions


def build_session_prompt(header, body):
    # type: (str, str) -> str
    return """Summarize this coding session in 3-5 bullet points.
Focus on: what task was being done, what decisions were made,
what was the outcome. Skip status updates and acknowledgments.
Output in the same language as the conversation.

Session: %s

%s""" % (header, body)


def call_ollama(prompt, model):
    # type: (str, str) -> str
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["message"]["content"].strip()
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def main():
    # type: () -> None
    args = parse_args()
    date_str = target_date(args.date)

    extraction_dir = Path(args.output_dir) / date_str
    conversations_path = extraction_dir / "filtered_conversations.md"
    if not conversations_path.exists():
        print("Error: %s not found." % conversations_path, file=sys.stderr)
        print("Run scripts/01_extract.py --date %s first." % date_str, file=sys.stderr)
        sys.exit(1)

    text = conversations_path.read_text(encoding="utf-8")
    sessions = split_sessions(text)

    if not sessions:
        print("No sessions found in %s" % conversations_path, file=sys.stderr)
        sys.exit(1)

    print("Date: %s" % date_str)
    print("Sessions to summarize: %d" % len(sessions))

    if not args.dry_run:
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        except Exception as exc:
            print("Error: Cannot reach Ollama: %s" % exc, file=sys.stderr)
            sys.exit(1)

    output_lines = ["# Session Summaries - %s" % date_str, ""]

    for i, (header, body) in enumerate(sessions):
        prompt = build_session_prompt(header, body)
        print("  [%d/%d] %s" % (i + 1, len(sessions), header))

        if args.dry_run:
            output_lines.append("## Session: %s" % header)
            output_lines.append("")
            output_lines.append("[dry-run: prompt length = %d chars]" % len(prompt))
            output_lines.append("")
            continue

        summary = call_ollama(prompt, args.model)
        output_lines.append("## Session: %s" % header)
        output_lines.append("")
        output_lines.append(summary)
        output_lines.append("")

    output_path = extraction_dir / "session_summaries.md"
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    print("Output: %s" % output_path)


if __name__ == "__main__":
    main()
