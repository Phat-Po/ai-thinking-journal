"""Summarizer plugin ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class SummarizerPlugin(ABC):
    name: str = ""
    display_name: str = ""

    @abstractmethod
    def call(self, prompt: str, *, timeout: int = 240) -> str:
        """Send prompt to LLM, return response text. Raises RuntimeError on failure."""
        ...

    def call_image(self, prompt: str, *, size: str = "1024x1280",
                   quality: str = "medium") -> Optional[bytes]:
        """Generate image from prompt. Returns PNG bytes or None.
        Only implemented by backends supporting image generation (OpenAI)."""
        return None

    @abstractmethod
    def check_availability(self) -> bool:
        """Return True if backend is reachable/configured. Used by aij init."""
        ...

    def configure(self, config: dict) -> None:
        pass
