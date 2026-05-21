"""Cursor IDE source plugin — parses ~/.cursor/ai-tracking/ai-code-tracking.db."""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from aij.sources.base import ExtractedMessage, SessionData, SourcePlugin


class CursorSource(SourcePlugin):
    name = "cursor"
    display_name = "Cursor IDE (experimental)"

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path

    def detect(self) -> Optional[Path]:
        path = self._db_path or Path.home() / ".cursor" / "ai-tracking" / "ai-code-tracking.db"
        if path.exists():
            return path
        return None

    def find_files(self, date_str: str) -> List[Path]:
        detected = self.detect()
        return [detected] if detected else []

    def parse_file(self, path: Path, start: datetime, end: datetime) -> Optional[SessionData]:
        session = SessionData(source="cursor", session_id="cursor-db")

        try:
            uri = "file:%s?mode=ro" % path
            conn = sqlite3.connect(uri, uri=True)
        except Exception as exc:
            print("Warning: cannot open Cursor DB: %s" % exc, file=sys.stderr)
            return None

        try:
            cursor = conn.cursor()

            # Discover tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            if not tables:
                return None

            # Try to find a conversations/messages table
            conversation_table = None
            for candidate in ("conversations", "messages", "chat_messages", "interactions"):
                if candidate in tables:
                    conversation_table = candidate
                    break

            if not conversation_table:
                # Fall back to first table
                conversation_table = tables[0]

            # Get column names
            cursor.execute("PRAGMA table_info(%s)" % conversation_table)
            columns = [row[1] for row in cursor.fetchall()]

            # Try to find relevant columns
            text_col = None
            for candidate in ("content", "text", "message", "body", "input", "output"):
                if candidate in columns:
                    text_col = candidate
                    break

            time_col = None
            for candidate in ("created_at", "timestamp", "date", "time", "inserted_at"):
                if candidate in columns:
                    time_col = candidate
                    break

            role_col = None
            for candidate in ("role", "type", "sender", "source"):
                if candidate in columns:
                    role_col = candidate
                    break

            if not text_col:
                print("Warning: Cursor DB table '%s' has no recognizable text column" % conversation_table,
                      file=sys.stderr)
                return None

            # Build query
            select_cols = [text_col]
            if role_col:
                select_cols.append(role_col)
            if time_col:
                select_cols.append(time_col)

            query = "SELECT %s FROM %s" % (", ".join(select_cols), conversation_table)
            if time_col:
                start_iso = start.strftime("%Y-%m-%dT%H:%M:%S")
                end_iso = end.strftime("%Y-%m-%dT%H:%M:%S")
                query += " WHERE %s >= '%s' AND %s < '%s'" % (time_col, start_iso, time_col, end_iso)

            try:
                cursor.execute(query)
            except Exception as exc:
                print("Warning: Cursor DB query failed: %s" % exc, file=sys.stderr)
                return None

            for row in cursor.fetchall():
                text = (row[0] or "").strip()
                if not text:
                    continue

                role = "assistant"
                if role_col and len(row) > 1:
                    raw_role = str(row[1]).lower()
                    if raw_role in ("user", "human"):
                        role = "user"

                timestamp = ""
                if time_col:
                    idx = select_cols.index(time_col)
                    if idx < len(row):
                        timestamp = str(row[idx] or "")

                session.messages.append(ExtractedMessage(
                    source="cursor",
                    role=role,
                    timestamp=timestamp,
                    session_id=session.session_id,
                    cwd="",
                    git_branch="",
                    text=text[:500],
                ))

            return session if session.messages else None

        except Exception as exc:
            print("Warning: Cursor DB parse error: %s" % exc, file=sys.stderr)
            return None
        finally:
            conn.close()

    def configure(self, config: dict) -> None:
        path = config.get("tracking_db") or config.get("path")
        if path:
            self._db_path = Path(path).expanduser()
