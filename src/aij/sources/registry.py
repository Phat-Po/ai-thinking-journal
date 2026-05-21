"""Source plugin registry — discover and instantiate sources."""

from __future__ import annotations

from typing import Dict, List, Optional

from aij.sources.base import SourcePlugin
from aij.sources.claude_code import ClaudeCodeSource
from aij.sources.codex_cli import CodexCliSource
from aij.sources.cursor import CursorSource
from aij.sources.windsurf import WindsurfSource


_REGISTRY: Dict[str, type] = {
    "claude_code": ClaudeCodeSource,
    "codex_cli": CodexCliSource,
    "cursor": CursorSource,
    "windsurf": WindsurfSource,
}


def get_source(name: str) -> Optional[SourcePlugin]:
    cls = _REGISTRY.get(name)
    if cls:
        return cls()
    return None


def discover_sources() -> List[SourcePlugin]:
    """Return all built-in source instances."""
    return [cls() for cls in _REGISTRY.values()]


def list_source_names() -> List[str]:
    return list(_REGISTRY.keys())
