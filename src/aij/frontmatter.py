"""YAML frontmatter generation and parsing for journal entries."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from aij.date_utils import weekday_name

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def yaml_scalar(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    text = str(value).replace('"', '\\"')
    return '"%s"' % text


def yaml_inline_dict(data: Dict[str, Any]) -> str:
    parts = []
    for key, value in data.items():
        parts.append("%s: %s" % (key, yaml_scalar(value)))
    return "{" + ", ".join(parts) + "}"


def build_frontmatter(date_str: str, stats: Dict[str, Any]) -> str:
    lines: List[str] = [
        "---",
        'date: "%s"' % date_str,
        "type: daily",
        "weekday: %s" % weekday_name(date_str),
        "tools_used:",
    ]

    tools_used = stats.get("tools_used", {})
    for source in ("claude_code", "codex"):
        source_stats = tools_used.get(source, {})
        messages = source_stats.get("messages", {})
        tools = source_stats.get("tools", {})
        lines.append("  %s:" % source)
        lines.append("    sessions: %s" % int(source_stats.get("sessions", 0)))
        lines.append("    messages: %s" % yaml_inline_dict(messages))
        lines.append("    tools: %s" % yaml_inline_dict(tools))

    lines.append("projects_touched:")
    projects = stats.get("projects_touched", [])
    if projects:
        for project in projects:
            lines.append("  - %s" % yaml_inline_dict(project))
    else:
        lines.append("  []")

    lines.append("total_duration_estimate_min: %s" % int(stats.get("total_duration_estimate_min", 0)))
    lines.append("---")
    return "\n".join(lines) + "\n"


def build_weekly_frontmatter(
    date_range: str, week_label: str, day_count: int, agg: Dict[str, Any]
) -> str:
    lines = [
        "---",
        'date_range: "%s"' % date_range,
        "type: weekly",
        "week: \"%s\"" % week_label,
        "total_sessions: %s" % json.dumps(agg["total_sessions"]),
        "total_days: %d" % day_count,
        "top_projects:",
    ]
    for name, count in sorted(agg["top_projects"].items(), key=lambda x: -x[1]):
        lines.append("  - {name: \"%s\", days: %d}" % (name, count))
    if not agg["top_projects"]:
        lines.append("  []")
    lines.append("---")
    return "\n".join(lines) + "\n"


def build_monthly_frontmatter(
    month_label: str, date_range: str, agg: Dict[str, Any]
) -> str:
    lines = [
        "---",
        'date_range: "%s"' % date_range,
        "type: monthly",
        "month: \"%s\"" % month_label,
        "total_days: %d" % agg["total_days"],
        "total_sessions: %s" % json.dumps(agg["total_sessions"]),
        "top_projects:",
    ]
    for name, count in sorted(agg["top_projects"].items(), key=lambda x: -x[1]):
        lines.append("  - {name: \"%s\", active_days: %d}" % (name, count))
    if not agg["top_projects"]:
        lines.append("  []")
    lines.append("---")
    return "\n".join(lines) + "\n"


def parse_frontmatter(text: str) -> Dict[str, Any]:
    """Extract YAML frontmatter as a dict. Simple parser — no full YAML dependency."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"')
    return fm


def extract_session_count(text: str, source: str) -> int:
    """Extract session count from nested YAML frontmatter using regex."""
    pattern = r"%s:\s*\n\s+sessions:\s*(\d+)" % source
    match = re.search(pattern, text)
    if match:
        return int(match.group(1))
    return 0


def extract_projects(text: str) -> List[str]:
    """Extract project names from projects_touched in frontmatter."""
    projects = []
    for match in re.finditer(r'- \{name:\s*"([^"]+)"', text):
        name = match.group(1)
        if name not in projects:
            projects.append(name)
    return projects
