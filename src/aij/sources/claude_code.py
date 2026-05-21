"""Claude Code source plugin — parses ~/.claude/projects/*.jsonl files."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from aij.sources.base import (
    ExtractedMessage,
    SessionData,
    SourcePlugin,
    iter_jsonl,
)
from aij.message_filters import (
    extract_text_and_tools,
    filter_message_text,
    merge_consecutive_assistant_messages,
)
from aij.date_utils import is_in_day


class ClaudeCodeSource(SourcePlugin):
    name = "claude_code"
    display_name = "Claude Code"

    def __init__(self, root: Optional[Path] = None):
        self._root = root or Path.home() / ".claude" / "projects"

    def detect(self) -> Optional[Path]:
        if self._root.exists():
            return self._root
        return None

    def find_files(self, date_str: str) -> List[Path]:
        if not self._root.exists():
            return []
        return sorted(self._root.rglob("*.jsonl"))

    def parse_file(self, path: Path, start: datetime, end: datetime) -> Optional[SessionData]:
        tz = start.tzinfo
        session = SessionData(source="claude_code", session_id=path.stem)

        for obj in iter_jsonl(path):
            obj_type = obj.get("type")
            if obj.get("sessionId"):
                session.session_id = obj.get("sessionId")
            if obj.get("cwd"):
                session.cwd = obj.get("cwd")
            if obj.get("gitBranch"):
                session.git_branch = obj.get("gitBranch")

            if obj_type == "system" and obj.get("subtype") == "away_summary":
                content = (obj.get("content") or "").strip()
                if content:
                    content = re.sub(r"\s*\(disable recaps in /config\)\s*$", "", content)
                    if content:
                        session.away_summaries.append(content)
                continue

            if obj_type == "ai-title":
                title = (obj.get("aiTitle") or "").strip()
                if title and not session.ai_title:
                    session.ai_title = title
                continue

            if obj_type == "last-prompt":
                prompt = (obj.get("lastPrompt") or "").strip()
                if prompt and not session.last_prompt:
                    session.last_prompt = prompt
                continue

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

        session.messages = merge_consecutive_assistant_messages(session.messages, tz)
        return session if session.messages or session.tools or session.away_summaries else None

    def configure(self, config: dict) -> None:
        path = config.get("path")
        if path:
            self._root = Path(path).expanduser()
