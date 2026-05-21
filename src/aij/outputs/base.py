"""Output plugin ABC and JournalEntry dataclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class JournalEntry:
    date_str: str
    entry_type: str          # "daily" | "weekly" | "monthly"
    frontmatter: str         # YAML frontmatter string (with --- delimiters)
    body: str                # Markdown body (no frontmatter)
    title: str               # "2026-05-17 Sunday"
    image_path: Optional[Path] = None


class OutputPlugin(ABC):
    name: str = ""
    display_name: str = ""

    @abstractmethod
    def deliver(self, entry: JournalEntry) -> bool:
        """Deliver the journal entry. Returns True on success."""
        ...

    def configure(self, config: dict) -> None:
        pass
