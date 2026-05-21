"""Source plugin ABC and data models."""

from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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
    away_summaries: List[str] = field(default_factory=list)
    ai_title: str = ""
    last_prompt: str = ""
    available_skills: List[str] = field(default_factory=list)
    available_plugins: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def project_name(self) -> str:
        if not self.cwd:
            return "unknown"
        return Path(self.cwd).name or "unknown"


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


class SourcePlugin(ABC):
    name: str = ""
    display_name: str = ""

    @abstractmethod
    def detect(self) -> Optional[Path]:
        """Return root path if this source exists on the system, else None."""
        ...

    @abstractmethod
    def find_files(self, date_str: str) -> List[Path]:
        """Return all session files relevant to given date (YYYY-MM-DD)."""
        ...

    @abstractmethod
    def parse_file(self, path: Path, start: datetime, end: datetime) -> Optional[SessionData]:
        """Parse a session file, returning only messages within [start, end).
        start/end are timezone-aware datetimes from date_utils.day_bounds()."""
        ...

    def configure(self, config: dict) -> None:
        """Accept source-specific config. Optional override."""
        pass
