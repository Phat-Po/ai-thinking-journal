"""Anthropic API summarizer plugin."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

from aij.summarizers.base import SummarizerPlugin

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicSummarizer(SummarizerPlugin):
    name = "anthropic"
    display_name = "Anthropic API"

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    def call(self, prompt: str, *, timeout: int = 240) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
        payload = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            ANTHROPIC_URL, data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"].strip()

    def check_availability(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY", ""))

    def configure(self, config: dict) -> None:
        if "model" in config:
            self.model = config["model"]
