"""Codex CLI source plugin — parses ~/.codex/sessions/**/*.jsonl files."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aij.sources.base import (
    ExtractedMessage,
    SessionData,
    SourcePlugin,
    iter_jsonl,
)
from aij.message_filters import (
    extract_text_and_tools,
    filter_message_text,
    is_codex_bootstrap_message,
    merge_consecutive_assistant_messages,
)
from aij.date_utils import is_in_day


def _codex_content_text(content: Any) -> str:
    text, _tools = extract_text_and_tools(content)
    return text


def _extract_codex_developer_context(text: str) -> Tuple[List[str], List[str]]:
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


def _git_branch_from_meta(meta_git: Any) -> str:
    if isinstance(meta_git, dict):
        branch = meta_git.get("branch")
        if isinstance(branch, str):
            return branch
    return ""


class CodexCliSource(SourcePlugin):
    name = "codex"
    display_name = "Codex CLI"

    def __init__(self, root: Optional[Path] = None):
        self._root = root or Path.home() / ".codex"

    def detect(self) -> Optional[Path]:
        if self._root.exists():
            return self._root
        return None

    def find_files(self, date_str: str) -> List[Path]:
        if not self._root.exists():
            return []
        yyyy, mm, dd = date_str.split("-")
        candidates = []
        sessions_day = self._root / "sessions" / yyyy / mm / dd
        if sessions_day.exists():
            candidates.extend(sorted(sessions_day.glob("*.jsonl")))
        archived = self._root / "archived_sessions"
        if archived.exists():
            candidates.extend(sorted(archived.glob("*.jsonl")))
        return candidates

    def parse_file(self, path: Path, start: datetime, end: datetime) -> Optional[SessionData]:
        tz = start.tzinfo
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
                session.git_branch = _git_branch_from_meta(payload.get("git")) or session.git_branch
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
                text = _codex_content_text(payload.get("content", ""))
                if role == "developer":
                    skills, plugins = _extract_codex_developer_context(text)
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

        session.messages = merge_consecutive_assistant_messages(session.messages, tz)
        return session if session.messages or session.tools else None

    def configure(self, config: dict) -> None:
        path = config.get("path")
        if path:
            self._root = Path(path).expanduser()
