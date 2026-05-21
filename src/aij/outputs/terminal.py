"""Terminal output plugin — prints journal entries to stdout."""

from __future__ import annotations

from aij.outputs.base import JournalEntry, OutputPlugin


class TerminalOutput(OutputPlugin):
    name = "terminal"
    display_name = "Terminal Display"

    def deliver(self, entry: JournalEntry) -> bool:
        print(entry.frontmatter)
        print(entry.title)
        print()
        print(entry.body)
        return True
