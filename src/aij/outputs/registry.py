"""Output plugin registry."""

from __future__ import annotations

from typing import List

from aij.outputs.base import OutputPlugin
from aij.outputs.markdown_file import MarkdownFileOutput
from aij.outputs.terminal import TerminalOutput
from aij.outputs.lark_webhook import LarkWebhookOutput
from aij.outputs.lark_app import LarkAppOutput
from aij.outputs.email_smtp import EmailOutput


_REGISTRY = {
    "markdown": MarkdownFileOutput,
    "terminal": TerminalOutput,
    "lark_webhook": LarkWebhookOutput,
    "lark_app": LarkAppOutput,
    "email": EmailOutput,
}


def get_output(name: str, config: dict | None = None) -> OutputPlugin | None:
    cls = _REGISTRY.get(name)
    if not cls:
        return None
    instance = cls()
    if config:
        instance.configure(config)
    return instance


def get_enabled_outputs(outputs_config: dict) -> List[OutputPlugin]:
    """Return instantiated output plugins for all enabled outputs in config."""
    plugins = []
    for name, cls in _REGISTRY.items():
        section = outputs_config.get(name, {})
        if section.get("enabled", False):
            instance = cls()
            instance.configure(section)
            plugins.append(instance)
    return plugins


def list_output_names() -> list[str]:
    return list(_REGISTRY.keys())
