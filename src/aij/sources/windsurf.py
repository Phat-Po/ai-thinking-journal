"""Windsurf source plugin — stub, not yet implemented."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from aij.sources.base import SessionData, SourcePlugin


class WindsurfSource(SourcePlugin):
    name = "windsurf"
    display_name = "Windsurf (not implemented)"

    def detect(self) -> Optional[Path]:
        return None

    def find_files(self, date_str: str) -> List[Path]:
        return []

    def parse_file(self, path: Path, start: datetime, end: datetime) -> Optional[SessionData]:
        raise NotImplementedError("Windsurf source not yet implemented")
