"""Claude CLI summarizer plugin — uses `claude -p` subprocess."""

from __future__ import annotations

import shutil
import subprocess

from aij.summarizers.base import SummarizerPlugin


class ClaudeCliSummarizer(SummarizerPlugin):
    name = "claude_cli"
    display_name = "Claude CLI"

    def call(self, prompt: str, *, timeout: int = 240) -> str:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError("claude CLI failed (exit %d): %s" % (
                result.returncode, result.stderr.strip()[:200]))
        return result.stdout.strip()

    def check_availability(self) -> bool:
        return shutil.which("claude") is not None
