"""Terminal output plugin — styled preview of journal entries."""

from __future__ import annotations

import click

from aij.outputs.base import JournalEntry, OutputPlugin


class TerminalOutput(OutputPlugin):
    name = "terminal"
    display_name = "Terminal Display"

    def deliver(self, entry: JournalEntry) -> bool:
        click.echo()
        click.echo(click.style("  ── %s ──" % entry.title.lstrip("# "), bold=True))
        click.echo()

        # Show first meaningful section (skip YAML frontmatter)
        lines = entry.body.split("\n")
        preview_lines = []
        in_preview = False
        for line in lines:
            if line.startswith("## "):
                in_preview = True
            if in_preview:
                preview_lines.append(line)
            if len(preview_lines) >= 15:
                break

        if preview_lines:
            for line in preview_lines:
                if line.startswith("## "):
                    click.echo(click.style("  " + line, bold=True))
                elif line.startswith("### "):
                    click.echo(click.style("  " + line, bold=True))
                elif line.startswith("- "):
                    click.echo(click.style("  •", fg="cyan") + " " + line[2:])
                else:
                    click.echo("  " + line)
            click.echo()
            total_words = len(entry.body.split())
            click.echo(click.style("  ... (%d words total)" % total_words, dim=True))
        else:
            # Fallback: show first 5 lines
            for line in lines[:5]:
                click.echo("  " + line)

        click.echo()
        return True
