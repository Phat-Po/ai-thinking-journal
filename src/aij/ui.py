"""Shared terminal UI helpers — colors, spinners, styled output.

Uses click.style() only. No Rich dependency.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Optional

import click


# ── Colors ──────────────────────────────────────────────────────────────

GREEN = "green"
YELLOW = "yellow"
RED = "red"
CYAN = "cyan"
MAGENTA = "magenta"
DIM = {"dim": True}
BOLD = {"bold": True}


# ── Icons ───────────────────────────────────────────────────────────────

CHECK = click.style("  ✓ ", fg=GREEN)
WARN = click.style("  ⚠ ", fg=YELLOW)
CROSS = click.style("  ✗ ", fg=RED)
ARROW = click.style("  → ", fg=CYAN)
DOT = click.style("  • ", fg="white")


# ── Output helpers ──────────────────────────────────────────────────────

def success(msg: str) -> None:
    click.echo(CHECK + msg)


def warn(msg: str) -> None:
    click.echo(WARN + msg, err=True)


def error(msg: str) -> None:
    click.echo(CROSS + msg, err=True)


def info(msg: str) -> None:
    click.echo(DOT + msg)


def arrow(msg: str) -> None:
    click.echo(ARROW + msg)


def step(n: int, total: int, label: str) -> None:
    header = click.style("  Step %d/%d " % (n, total), **BOLD)
    click.echo(header + label)


def banner(title: str, subtitle: str = "") -> None:
    width = max(len(title), len(subtitle)) + 4
    top = "  ╭" + "─" * width + "╮"
    bot = "  ╰" + "─" * width + "╯"
    click.echo(click.style(top, **DIM))
    line_title = "  │ " + title.center(width - 2) + " │"
    click.echo(click.style(line_title, **BOLD))
    if subtitle:
        line_sub = "  │ " + subtitle.center(width - 2) + " │"
        click.echo(click.style(line_sub, **DIM))
    click.echo(click.style(bot, **DIM))


def summary_box(pairs: list[tuple[str, str]]) -> None:
    """Print a bordered summary box. pairs = [(label, value), ...]"""
    max_label = max(len(l) for l, _ in pairs)
    max_val = max(len(v) for _, v in pairs)
    inner = max_label + max_val + 5
    top = "  ┌" + "─" * inner + "┐"
    bot = "  └" + "─" * inner + "┘"
    click.echo(click.style(top, **DIM))
    for label, value in pairs:
        lstyled = click.style(label.rjust(max_label), **DIM)
        row = "  │ %s  %s%s │" % (lstyled, value, " " * (max_val - len(value)))
        click.echo(row)
    click.echo(click.style(bot, **DIM))


# ── Spinner ─────────────────────────────────────────────────────────────

class Spinner:
    """Simple terminal spinner for long-running operations."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Working..."):
        self._message = message
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, final: str = "") -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        # Clear the spinner line
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()
        if final:
            click.echo(final)

    def _run(self) -> None:
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stderr.write("\r\033[K  %s %s" % (click.style(frame, fg=CYAN), self._message))
            sys.stderr.flush()
            i += 1
            self._stop.wait(0.1)
