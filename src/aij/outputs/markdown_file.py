"""Markdown file output plugin — writes journal entries to journal_root/."""

from __future__ import annotations

from pathlib import Path

from aij.outputs.base import JournalEntry, OutputPlugin


class MarkdownFileOutput(OutputPlugin):
    name = "markdown"
    display_name = "Local Markdown (Obsidian-compatible)"

    def __init__(self, journal_root: str | Path | None = None):
        self._journal_root = Path(journal_root) if journal_root else Path.home() / "ai-journal"

    def deliver(self, entry: JournalEntry) -> bool:
        subdir = self._journal_root / entry.entry_type
        subdir.mkdir(parents=True, exist_ok=True)

        if entry.entry_type == "daily":
            filename = "%s.md" % entry.date_str
        elif entry.entry_type == "weekly":
            filename = "%s.md" % entry.date_str  # e.g. 2026-W20
        else:
            filename = "%s.md" % entry.date_str  # e.g. 2026-05

        output_path = subdir / filename
        content = entry.frontmatter + "\n" + entry.title + "\n\n" + entry.body + "\n"
        output_path.write_text(content, encoding="utf-8")
        print("Output: %s" % output_path)
        return True

    def configure(self, config: dict) -> None:
        if "journal_root" in config:
            self._journal_root = Path(config["journal_root"]).expanduser()
