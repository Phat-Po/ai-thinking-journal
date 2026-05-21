"""Noise filtering, dedup, and text extraction for conversation messages."""

from __future__ import annotations

import hashlib
import re
from typing import Any, List, Set, Tuple

from aij.sources.base import ExtractedMessage
from aij.date_utils import local_time

from zoneinfo import ZoneInfo


SKILL_FRONTMATTER_RE = re.compile(
    r"^---\s*\nname:\s*.+\ndescription:\s*.+\nmetadata:\s*\n\s+type:\s*",
    re.MULTILINE,
)


def extract_text_and_tools(content: Any) -> Tuple[str, List[str]]:
    if isinstance(content, str):
        return content.strip(), []
    if not isinstance(content, list):
        return "", []

    texts = []
    tools = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type in ("text", "input_text", "output_text", "summary_text"):
            value = block.get("text")
            if isinstance(value, str):
                texts.append(value)
        elif block_type == "tool_use":
            name = block.get("name")
            if isinstance(name, str) and name:
                tools.append(name)
    return "\n".join(texts).strip(), tools


def is_codex_bootstrap_message(text: str) -> bool:
    return (
        "AGENTS.md instructions for" in text
        or "<INSTRUCTIONS>" in text
        or "</INSTRUCTIONS>" in text
        or text.strip().startswith("<environment_context>")
    )


def is_slash_command_noise(text: str) -> bool:
    stripped = text.strip()
    return (
        "<local-command-caveat>" in text
        or "<command-name>" in text
        or "<local-command-stdout>" in text
        or stripped.startswith("<command-")
    )


def strip_system_reminders(text: str) -> str:
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
    text = re.sub(r"<system-reminder>.*", "", text, flags=re.DOTALL)
    return text.strip()


def is_noise_text(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("<task-notification>") or is_slash_command_noise(text)


def first_and_last_paragraph(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        return text.strip()
    if paragraphs[0] == paragraphs[-1]:
        return paragraphs[0]
    return paragraphs[0] + "\n\n" + paragraphs[-1]


def filter_message_text(role: str, text: str) -> str:
    if not text:
        return ""
    text = strip_system_reminders(text)
    if not text or is_noise_text(text):
        return ""
    if role == "assistant":
        return first_and_last_paragraph(text)
    return text.strip()


def merge_consecutive_assistant_messages(
    messages: List[ExtractedMessage], tz: ZoneInfo
) -> List[ExtractedMessage]:
    merged: List[ExtractedMessage] = []
    for message in messages:
        minute = local_time(message.timestamp, tz)
        if (
            merged
            and message.role == "assistant"
            and merged[-1].role == "assistant"
            and message.session_id == merged[-1].session_id
            and minute == local_time(merged[-1].timestamp, tz)
        ):
            previous = merged[-1]
            merged[-1] = ExtractedMessage(
                source=previous.source,
                role=previous.role,
                timestamp=previous.timestamp,
                session_id=previous.session_id,
                cwd=previous.cwd,
                git_branch=previous.git_branch,
                text=previous.text.rstrip() + "\n\n" + message.text.lstrip(),
            )
        else:
            merged.append(message)
    return merged


def _text_hash(text: str) -> str:
    return hashlib.md5(text[:500].encode("utf-8")).hexdigest()


def _looks_like_skill_content(text: str) -> bool:
    return bool(SKILL_FRONTMATTER_RE.search(text))


def dedup_message_text(text: str, seen: Set[str]) -> str:
    if len(text) < 500:
        return text
    if _looks_like_skill_content(text):
        return "[引用了 skill 文件内容]"
    h = _text_hash(text)
    if h in seen:
        return "[重复内容已省略 — 见上方 session]"
    seen.add(h)
    return text
