#!/usr/bin/env python3
"""
Task 01: Daily conversation extraction.

Extracts one local day of Claude Code and Codex CLI conversations into:
- output/YYYY-MM-DD/filtered_conversations.md
- output/YYYY-MM-DD/stats.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

TZ_LOCAL = timezone(timedelta(hours=8))


@dataclass
class ExtractedMessage:
    source: str
    role: str
    timestamp: str
    session_id: str
    cwd: str
    git_branch: str
    text: str


@dataclass
class SessionData:
    source: str
    session_id: str
    cwd: str = ""
    git_branch: str = ""
    messages: List[ExtractedMessage] = field(default_factory=list)
    tools: Counter = field(default_factory=Counter)
    available_skills: List[str] = field(default_factory=list)
    available_plugins: List[str] = field(default_factory=list)

    @property
    def project_name(self) -> str:
        return derive_project_name(self.cwd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract daily Claude Code + Codex conversations")
    parser.add_argument(
        "--date",
        default=None,
        help="Local date to extract (YYYY-MM-DD). Default: today in UTC+8.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent / "output"),
        help="Directory for extraction artifacts.",
    )
    return parser.parse_args()


def target_date(args_date: Optional[str]) -> str:
    if args_date:
        datetime.strptime(args_date, "%Y-%m-%d")
        return args_date
    return datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")


def day_bounds(date_str: str) -> Tuple[datetime, datetime]:
    start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TZ_LOCAL)
    return start, start + timedelta(days=1)


def parse_timestamp(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def is_in_day(ts: str, start: datetime, end: datetime) -> bool:
    parsed = parse_timestamp(ts)
    if not parsed:
        return False
    local = parsed.astimezone(TZ_LOCAL)
    return start <= local < end


def local_time(ts: str) -> str:
    parsed = parse_timestamp(ts)
    if not parsed:
        return "??:??"
    return parsed.astimezone(TZ_LOCAL).strftime("%H:%M")


def derive_project_name(cwd: str) -> str:
    if not cwd:
        return "unknown"
    return Path(cwd).name or "unknown"


def extract_text_and_tools(content: Any) -> Tuple[str, List[str]]:
    if isinstance(content, str):
        return content.strip(), []
    if not isinstance(content, list):
        return "", []

    texts = []
    tools = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type in ("text", "input_text", "output_text", "summary_text"):
            value = block.get("text")
            if isinstance(value, str):
                texts.append(value)
        elif block_type == "tool_use":
            name = block.get("name")
            if isinstance(name, str) and name:
                tools.append(name)
    return "\n".join(texts).strip(), tools


def is_codex_bootstrap_message(text: str) -> bool:
    return (
        "AGENTS.md instructions for" in text
        or "<INSTRUCTIONS>" in text
        or "</INSTRUCTIONS>" in text
    )


def is_slash_command_noise(text: str) -> bool:
    stripped = text.strip()
    return (
        "<local-command-caveat>" in text
        or "<command-name>" in text
        or "<local-command-stdout>" in text
        or stripped.startswith("<command-")
    )


def strip_system_reminders(text: str) -> str:
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
    text = re.sub(r"<system-reminder>.*", "", text, flags=re.DOTALL)
    return text.strip()


def is_noise_text(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("<task-notification>") or is_slash_command_noise(text)


def first_and_last_paragraph(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        return text.strip()
    if paragraphs[0] == paragraphs[-1]:
        return paragraphs[0]
    return paragraphs[0] + "\n\n" + paragraphs[-1]


def filter_message_text(role: str, text: str) -> str:
    if not text:
        return ""
    text = strip_system_reminders(text)
    if not text or is_noise_text(text):
        return ""
    if role == "assistant":
        return first_and_last_paragraph(text)
    return text.strip()


def merge_consecutive_assistant_messages(messages: List[ExtractedMessage]) -> List[ExtractedMessage]:
    merged: List[ExtractedMessage] = []
    for message in messages:
        minute = local_time(message.timestamp)
        if (
            merged
            and message.role == "assistant"
            and merged[-1].role == "assistant"
            and message.session_id == merged[-1].session_id
            and minute == local_time(merged[-1].timestamp)
        ):
            previous = merged[-1]
            merged[-1] = ExtractedMessage(
                source=previous.source,
                role=previous.role,
                timestamp=previous.timestamp,
                session_id=previous.session_id,
                cwd=previous.cwd,
                git_branch=previous.git_branch,
                text=previous.text.rstrip() + "\n\n" + message.text.lstrip(),
            )
        else:
            merged.append(message)
    return merged


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError as exc:
        print("Warning: cannot read %s: %s" % (path, exc), file=sys.stderr)


def parse_claude_file(path: Path, start: datetime, end: datetime) -> Optional[SessionData]:
    session = SessionData(source="claude_code", session_id=path.stem)

    for obj in iter_jsonl(path):
        obj_type = obj.get("type")
        if obj.get("sessionId"):
            session.session_id = obj.get("sessionId")
        if obj.get("cwd"):
            session.cwd = obj.get("cwd")
        if obj.get("gitBranch"):
            session.git_branch = obj.get("gitBranch")

        if obj_type not in ("user", "assistant"):
            continue

        timestamp = obj.get("timestamp", "")
        if not is_in_day(timestamp, start, end):
            continue

        message = obj.get("message") or {}
        text, tools = extract_text_and_tools(message.get("content", ""))
        session.tools.update(tools)

        role = "user" if obj_type == "user" else "assistant"
        filtered = filter_message_text(role, text)
        if not filtered:
            continue

        session.messages.append(ExtractedMessage(
            source=session.source,
            role=role,
            timestamp=timestamp,
            session_id=session.session_id,
            cwd=session.cwd,
            git_branch=session.git_branch,
            text=filtered,
        ))

    session.messages = merge_consecutive_assistant_messages(session.messages)
    return session if session.messages or session.tools else None


def codex_content_text(content: Any) -> str:
    text, _tools = extract_text_and_tools(content)
    return text


def extract_codex_developer_context(text: str) -> Tuple[List[str], List[str]]:
    skills: List[str] = []
    plugins: List[str] = []
    capture = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("### Available skills"):
            capture = "skills"
            continue
        if stripped.startswith("### Available plugins"):
            capture = "plugins"
            continue
        if stripped.startswith("### ") or stripped.startswith("## "):
            capture = None
        if capture and stripped.startswith("- "):
            item = stripped[2:]
            backtick_match = re.search(r"`([^`]+)`", item)
            if backtick_match:
                name = backtick_match.group(1).strip()
            elif ": " in item:
                name = item.split(": ", 1)[0].strip("` ")
            else:
                name = item.split(" — ", 1)[0].split(" - ", 1)[0].split(":", 1)[0].strip("` ")
            if capture == "skills" and name and name not in skills:
                skills.append(name)
            elif capture == "plugins" and name and name not in plugins:
                plugins.append(name)
    return skills, plugins


def extract_reasoning_summary(payload: Dict[str, Any]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, str):
        return summary.strip()
    if isinstance(summary, list):
        texts = []
        for item in summary:
            if isinstance(item, dict):
                value = item.get("text") or item.get("summary_text")
                if isinstance(value, str):
                    texts.append(value)
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts).strip()
    return ""


def git_branch_from_meta(meta_git: Any) -> str:
    if isinstance(meta_git, dict):
        branch = meta_git.get("branch")
        if isinstance(branch, str):
            return branch
    return ""


def parse_codex_file(path: Path, start: datetime, end: datetime) -> Optional[SessionData]:
    session = SessionData(source="codex", session_id=path.stem)
    last_timestamp = ""

    for obj in iter_jsonl(path):
        timestamp = obj.get("timestamp", "") or last_timestamp
        if timestamp:
            last_timestamp = timestamp

        if obj.get("type") == "session_meta":
            payload = obj.get("payload") or {}
            session.session_id = payload.get("id") or session.session_id
            session.cwd = payload.get("cwd") or session.cwd
            session.git_branch = git_branch_from_meta(payload.get("git")) or session.git_branch
            continue

        if obj.get("type") != "response_item":
            continue

        payload = obj.get("payload") or {}
        payload_type = payload.get("type")
        if payload_type == "function_call":
            name = payload.get("name")
            if isinstance(name, str) and name:
                session.tools.update([name])
            continue

        if not is_in_day(timestamp, start, end):
            continue

        if payload_type == "message":
            role = payload.get("role", "")
            if role not in ("user", "assistant", "developer"):
                continue
            text = codex_content_text(payload.get("content", ""))
            if role == "developer":
                skills, plugins = extract_codex_developer_context(text)
                for skill in skills:
                    if skill not in session.available_skills:
                        session.available_skills.append(skill)
                for plugin in plugins:
                    if plugin not in session.available_plugins:
                        session.available_plugins.append(plugin)
                continue
            if role == "user" and is_codex_bootstrap_message(text):
                continue
            filtered = filter_message_text(role, text)
            if not filtered:
                continue
            session.messages.append(ExtractedMessage(
                source=session.source,
                role=role,
                timestamp=timestamp,
                session_id=session.session_id,
                cwd=session.cwd,
                git_branch=session.git_branch,
                text=filtered,
            ))
        elif payload_type == "reasoning":
            continue

    session.messages = merge_consecutive_assistant_messages(session.messages)
    return session if session.messages or session.tools else None


def find_claude_files() -> List[Path]:
    root = Path.home() / ".claude" / "projects"
    if not root.exists():
        return []
    return sorted(root.rglob("*.jsonl"))


def find_codex_files(date_str: str) -> List[Path]:
    root = Path.home() / ".codex"
    yyyy, mm, dd = date_str.split("-")
    candidates = []
    sessions_day = root / "sessions" / yyyy / mm / dd
    if sessions_day.exists():
        candidates.extend(sorted(sessions_day.glob("*.jsonl")))
    archived = root / "archived_sessions"
    if archived.exists():
        candidates.extend(sorted(archived.glob("*.jsonl")))
    return candidates


def sort_sessions(sessions: List[SessionData]) -> List[SessionData]:
    def key(session: SessionData) -> str:
        if session.messages:
            return session.messages[0].timestamp
        return ""
    return sorted(sessions, key=key)


def build_stats(date_str: str, sessions: List[SessionData]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "date": date_str,
        "tools_used": {
            "claude_code": {"sessions": 0, "messages": {"user": 0, "assistant": 0}, "tools": {}},
            "codex": {
                "sessions": 0,
                "messages": {"user": 0, "assistant": 0},
                "tools": {},
                "available_skills": [],
                "available_plugins": [],
            },
        },
        "projects_touched": [],
        "total_duration_estimate_min": 0,
    }

    project_sessions: Dict[Tuple[str, str], set] = defaultdict(set)

    for source in ("claude_code", "codex"):
        source_sessions = [s for s in sessions if s.source == source]
        stats["tools_used"][source]["sessions"] = len(source_sessions)

        tools = Counter()
        available_skills = []
        available_plugins = []
        for session in source_sessions:
            tools.update(session.tools)
            for skill in session.available_skills:
                if skill not in available_skills:
                    available_skills.append(skill)
            for plugin in session.available_plugins:
                if plugin not in available_plugins:
                    available_plugins.append(plugin)
            project_sessions[(session.project_name, source)].add(session.session_id)
            timestamps = [parse_timestamp(m.timestamp) for m in session.messages]
            timestamps = [t for t in timestamps if t is not None]
            if timestamps:
                duration = max(timestamps) - min(timestamps)
                stats["total_duration_estimate_min"] += int(duration.total_seconds() // 60)
            for message in session.messages:
                if message.role not in stats["tools_used"][source]["messages"]:
                    stats["tools_used"][source]["messages"][message.role] = 0
                stats["tools_used"][source]["messages"][message.role] += 1

        stats["tools_used"][source]["tools"] = dict(sorted(tools.items()))
        if source == "codex":
            stats["tools_used"][source]["available_skills"] = sorted(available_skills)
            stats["tools_used"][source]["available_plugins"] = sorted(available_plugins)

    projects = []
    for (name, source), session_ids in sorted(project_sessions.items()):
        projects.append({"name": name, "source": source, "sessions": len(session_ids)})
    stats["projects_touched"] = projects
    return stats


SKILL_FRONTMATTER_RE = re.compile(
    r"^---\s*\nname:\s*.+\ndescription:\s*.+\nmetadata:\s*\n\s+type:\s*",
    re.MULTILINE,
)


def _text_hash(text: str) -> str:
    return hashlib.md5(text[:500].encode("utf-8")).hexdigest()


def _looks_like_skill_content(text: str) -> bool:
    return bool(SKILL_FRONTMATTER_RE.search(text))


def dedup_message_text(text: str, seen: Set[str]) -> str:
    if len(text) < 500:
        return text
    if _looks_like_skill_content(text):
        return "[引用了 skill 文件内容]"
    h = _text_hash(text)
    if h in seen:
        return "[重复内容已省略 — 见上方 session]"
    seen.add(h)
    return text


def build_markdown(date_str: str, sessions: List[SessionData]) -> str:
    lines = ["# Filtered Conversations - %s" % date_str, ""]
    seen_texts = set()  # type: Set[str]
    for session in sort_sessions(sessions):
        if not session.messages:
            continue
        first_ts = local_time(session.messages[0].timestamp)
        last_ts = local_time(session.messages[-1].timestamp)
        lines.append("<!-- SESSION: %s - %s (%s-%s) -->" % (
            session.source, session.project_name, first_ts, last_ts,
        ))
        lines.append("")
        lines.append("- session_id: `%s`" % session.session_id)
        lines.append("- cwd: `%s`" % (session.cwd or "unknown"))
        if session.git_branch:
            lines.append("- git_branch: `%s`" % session.git_branch)
        lines.append("")
        for message in session.messages:
            lines.append("<!-- MSG: %s - %s -->" % (local_time(message.timestamp), message.role))
            lines.append("")
            text = dedup_message_text(message.text, seen_texts)
            lines.append(text)
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    date_str = target_date(args.date)
    start, end = day_bounds(date_str)

    sessions = []
    for path in find_claude_files():
        parsed = parse_claude_file(path, start, end)
        if parsed:
            sessions.append(parsed)
    for path in find_codex_files(date_str):
        parsed = parse_codex_file(path, start, end)
        if parsed:
            sessions.append(parsed)

    output_root = Path(args.output_dir) / date_str
    output_root.mkdir(parents=True, exist_ok=True)
    conversations_path = output_root / "filtered_conversations.md"
    stats_path = output_root / "stats.json"

    conversations = build_markdown(date_str, sessions)
    stats = build_stats(date_str, sessions)

    conversations_path.write_text(conversations, encoding="utf-8")
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Date: %s" % date_str)
    print("Sessions: claude_code=%s codex=%s" % (
        stats["tools_used"]["claude_code"]["sessions"],
        stats["tools_used"]["codex"]["sessions"],
    ))
    print("Output: %s" % conversations_path)
    print("Stats: %s" % stats_path)


if __name__ == "__main__":
    main()
