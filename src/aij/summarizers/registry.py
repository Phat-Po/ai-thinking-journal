"""Summarizer plugin registry."""

from __future__ import annotations

from typing import Optional

from aij.summarizers.base import SummarizerPlugin
from aij.summarizers.openai_api import OpenAISummarizer
from aij.summarizers.ollama import OllamaSummarizer


_REGISTRY = {
    "openai": OpenAISummarizer,
    "ollama": OllamaSummarizer,
}


def get_summarizer(name: str, config: dict | None = None) -> Optional[SummarizerPlugin]:
    cls = _REGISTRY.get(name)
    if not cls:
        return None
    instance = cls()
    if config:
        instance.configure(config)
    return instance


def list_summarizer_names() -> list[str]:
    return list(_REGISTRY.keys())
