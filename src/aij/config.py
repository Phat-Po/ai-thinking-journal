"""Configuration management for ~/.aij/config.toml."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

# TOML handling: tomllib in 3.11+, tomli for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore[assignment]


CONFIG_DIR = Path.home() / ".aij"
CONFIG_PATH = CONFIG_DIR / "config.toml"


def _defaults() -> Dict[str, Any]:
    return {
        "general": {
            "timezone": "Asia/Taipei",
            "journal_root": str(Path.home() / "ai-journal"),
            "output_dir": str(CONFIG_DIR / "output"),
            "log_level": "info",
        },
        "schedule": {
            "frequency": "all",
            "trigger": "manual",
        },
        "sources": {
            "claude_code": {"enabled": True},
            "codex_cli": {"enabled": True},
            "cursor": {"enabled": False},
            "windsurf": {"enabled": False},
        },
        "summarizer": {
            "backend": "openai",
            "temperature": 0.3,
            "openai": {
                "model": "gpt-4.1-mini",
                "poster_model": "gpt-4.1",
                "image_model": "gpt-image-2",
            },
            "anthropic": {
                "model": "claude-sonnet-4-20250514",
            },
            "ollama": {
                "model": "qwen3-coder:480b-cloud",
                "url": "http://localhost:11434",
            },
            "claude_cli": {},
        },
        "poster": {
            "enabled": False,
            "image_quality": "medium",
            "image_size": "1024x1280",
        },
        "outputs": {
            "markdown": {"enabled": True},
            "terminal": {"enabled": False},
            "lark_webhook": {"enabled": False},
            "lark_app": {"enabled": False},
            "email": {"enabled": False},
        },
    }


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, recursively for nested dicts."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> Dict[str, Any]:
    """Load config from TOML file, merged with defaults."""
    config_path = path or CONFIG_PATH
    defaults = _defaults()

    if not config_path.exists():
        return defaults

    with open(config_path, "rb") as f:
        user_config = tomllib.load(f)

    return _deep_merge(defaults, user_config)


def save_config(config: Dict[str, Any], path: Path | None = None) -> None:
    """Write config to TOML file with mode 600."""
    if tomli_w is None:
        raise RuntimeError("tomli-w not installed. Run: pip install tomli-w")

    config_path = path or CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)

    os.chmod(config_path, 0o600)


def get_nested(config: Dict[str, Any], dotkey: str, default: Any = None) -> Any:
    """Get a nested config value using dot notation: 'summarizer.openai.model'."""
    keys = dotkey.split(".")
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def set_nested(config: Dict[str, Any], dotkey: str, value: Any) -> None:
    """Set a nested config value using dot notation."""
    keys = dotkey.split(".")
    current = config
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def config_path_str() -> str:
    return str(CONFIG_PATH)
