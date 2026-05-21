"""Ollama local LLM summarizer plugin."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Optional

from aij.summarizers.base import SummarizerPlugin

OLLAMA_URL = "http://localhost:11434/api/chat"


class OllamaSummarizer(SummarizerPlugin):
    name = "ollama"
    display_name = "Local Ollama"

    def __init__(self, model: str = "qwen3-coder:480b-cloud",
                 url: str = OLLAMA_URL):
        self.model = model
        self.url = url

    def call(self, prompt: str, *, timeout: int = 240) -> str:
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3},
        }).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["message"]["content"].strip()
        return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    def check_availability(self) -> bool:
        try:
            base = self.url.rsplit("/api/chat", 1)[0]
            urllib.request.urlopen(base + "/api/tags", timeout=5)
            return True
        except Exception:
            return False

    def configure(self, config: dict) -> None:
        if "model" in config:
            self.model = config["model"]
        if "url" in config:
            self.url = config["url"]
