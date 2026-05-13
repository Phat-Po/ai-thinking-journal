#!/usr/bin/env python3
"""
Task 01: Extraction POC (v3)
Scans today's Claude Code conversation files and extracts key messages
into a readable markdown file.

Mode: --mode smart (default) — all user msgs + last paragraph of each assistant msg.
      --mode full — all messages.
      --mode key — first user + last assistant only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

TZ_BEIJING = timezone(timedelta(hours=8))


class Message(NamedTuple):
    timestamp: str  # ISO 8601 in UTC
    role: str  # "User" or "Claude"
    text: str


class SessionResult(NamedTuple):
    project_name: str
    messages: List[Message]


def derive_project_name(cwd: str) -> str:
    if not cwd:
        return "unknown"
    return Path(cwd).name


def extract_text_from_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts).strip()
    return ""


def parse_jsonl(filepath: Path) -> Optional[SessionResult]:
    messages = []
    cwd = ""

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not cwd:
                cwd = obj.get("cwd", "")

            msg_type = obj.get("type")
            if msg_type not in ("user", "assistant"):
                continue

            timestamp = obj.get("timestamp", "")
            message = obj.get("message", {})
            content = message.get("content", "")

            text = extract_text_from_content(content)
            if not text:
                continue

            role = "User" if msg_type == "user" else "Claude"
            messages.append(Message(timestamp=timestamp, role=role, text=text))

    if not messages:
        return None

    project_name = derive_project_name(cwd)
    return SessionResult(project_name=project_name, messages=messages)


def is_noise(msg: Message) -> bool:
    """Filter out system notifications and boilerplate."""
    text = msg.text
    if text.startswith("<task-notification>"):
        return True
    if text.startswith("<system-reminder>"):
        return True
    return False


def last_paragraph(text: str) -> str:
    """Extract the last meaningful paragraph from assistant text."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return text.strip()
    # If only one paragraph, return it
    if len(paragraphs) == 1:
        return paragraphs[-1]
    # For multi-paragraph: take last 2 paragraphs (conclusion + context)
    # but cap at 500 chars to avoid bloating
    candidate = "\n\n".join(paragraphs[-2:])
    if len(candidate) <= 500:
        return candidate
    return paragraphs[-1]


def filter_smart(messages: List[Message]) -> List[Message]:
    """All user messages + last paragraph of each assistant message."""
    result = []
    for msg in messages:
        if is_noise(msg):
            continue
        if msg.role == "User":
            result.append(msg)
        else:
            trimmed = last_paragraph(msg.text)
            if trimmed:
                result.append(Message(
                    timestamp=msg.timestamp,
                    role=msg.role,
                    text=trimmed,
                ))
    return result


def filter_key_messages(messages: List[Message]) -> List[Message]:
    """Keep first user + last assistant message per session (lean summary)."""
    clean = [m for m in messages if not is_noise(m)]
    if len(clean) <= 2:
        return clean

    first_user = next((m for m in clean if m.role == "User"), None)
    last_assistant = next((m for m in reversed(clean) if m.role == "Claude"), None)

    result = []
    if first_user:
        result.append(first_user)
    if last_assistant and last_assistant is not first_user:
        result.append(last_assistant)
    return result


def get_today_start_beijing() -> datetime:
    """Get start of today in Beijing time."""
    now_beijing = datetime.now(TZ_BEIJING)
    return now_beijing.replace(hour=0, minute=0, second=0, microsecond=0)


def find_today_sessions() -> List[Tuple[Path, datetime]]:
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        print(f"Error: {claude_dir} not found", file=sys.stderr)
        sys.exit(1)

    today_start = get_today_start_beijing()
    sessions = []

    for project_dir in claude_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            mtime = datetime.fromtimestamp(
                jsonl_file.stat().st_mtime
            ).astimezone(TZ_BEIJING)
            if mtime >= today_start:
                sessions.append((jsonl_file, mtime))

    sessions.sort(key=lambda s: s[1])
    return sessions


def to_beijing_time(ts: str) -> str:
    """Convert ISO 8601 UTC timestamp to Beijing HH:MM."""
    if not ts:
        return "??:??"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt_bj = dt.astimezone(TZ_BEIJING)
        return dt_bj.strftime("%H:%M")
    except (ValueError, TypeError):
        return "??:??"


def generate_markdown(sessions: List[Tuple[Path, datetime]], mode: str) -> str:
    today_bj = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d")
    lines = [f"# Daily Thinking Log — {today_bj}\n"]

    for filepath, _mtime in sessions:
        result = parse_jsonl(filepath)
        if not result:
            continue

        start_time = result.messages[0].timestamp if result.messages else ""
        time_str = to_beijing_time(start_time) if start_time else "unknown"

        lines.append(f"## Session: {result.project_name}")
        lines.append(f"**Started**: {time_str}")
        lines.append("")

        if mode == "key":
            display_msgs = filter_key_messages(result.messages)
        elif mode == "smart":
            display_msgs = filter_smart(result.messages)
        else:
            display_msgs = result.messages

        for msg in display_msgs:
            time_str = to_beijing_time(msg.timestamp)
            lines.append(f"### {time_str} — {msg.role}")
            lines.append(msg.text)
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Extract today's Claude Code conversations")
    parser.add_argument(
        "--mode", choices=["smart", "key", "full"], default="smart",
        help="smart = all user + last paragraph of assistant (default); key = first+last only; full = all"
    )
    args = parser.parse_args()

    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    today_bj = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d")
    output_file = output_dir / f"{today_bj}-daily-thinking.md"

    sessions = find_today_sessions()
    if not sessions:
        print("No sessions found for today.")
        sys.exit(0)

    print(f"Found {len(sessions)} session(s) for today.")

    markdown = generate_markdown(sessions, args.mode)
    output_file.write_text(markdown, encoding="utf-8")
    print(f"Output written to: {output_file}")

    total_chars = len(markdown)
    print(f"Total size: {total_chars:,} characters (~{total_chars // 4:,} tokens)")
    print(f"Mode: {args.mode}")


if __name__ == "__main__":
    main()
