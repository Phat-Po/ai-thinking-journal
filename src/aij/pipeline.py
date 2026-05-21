"""Pipeline orchestrator — extract → summarize → deliver."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

from aij.config import load_config
from aij.date_utils import day_bounds, local_time, parse_timestamp, target_date, weekday_name
from aij.frontmatter import build_frontmatter
from aij.message_filters import dedup_message_text
from aij.outputs.base import JournalEntry
from aij.sources.base import SessionData, SourcePlugin


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    prompt_path = Path(__file__).parent / "prompts" / name
    return prompt_path.read_text(encoding="utf-8")


def sort_sessions(sessions: List[SessionData]) -> List[SessionData]:
    def key(session: SessionData) -> str:
        if session.messages:
            return session.messages[0].timestamp
        return ""
    return sorted(sessions, key=key)


def build_stats(date_str: str, sessions: List[SessionData]) -> Dict[str, Any]:
    # Collect all unique source names from sessions
    source_names = sorted(set(s.source for s in sessions))

    tools_used: Dict[str, Any] = {}
    for source in source_names:
        entry: Dict[str, Any] = {"sessions": 0, "messages": {"user": 0, "assistant": 0}, "tools": {}}
        if source == "codex":
            entry["available_skills"] = []
            entry["available_plugins"] = []
        tools_used[source] = entry

    stats: Dict[str, Any] = {
        "date": date_str,
        "tools_used": tools_used,
        "projects_touched": [],
        "total_duration_estimate_min": 0,
    }

    project_sessions: Dict[Tuple[str, str], set] = defaultdict(set)

    for source in source_names:
        source_sessions = [s for s in sessions if s.source == source]
        stats["tools_used"][source]["sessions"] = len(source_sessions)

        tools = Counter()
        available_skills = []
        available_plugins = []
        for session in source_sessions:
            tools.update(session.tools)
            for skill in session.available_skills:
                if skill not in available_skills:
                    available_skills.append(skill)
            for plugin in session.available_plugins:
                if plugin not in available_plugins:
                    available_plugins.append(plugin)
            project_sessions[(session.project_name, source)].add(session.session_id)
            timestamps = [parse_timestamp(m.timestamp) for m in session.messages]
            timestamps = [t for t in timestamps if t is not None]
            if timestamps:
                duration = max(timestamps) - min(timestamps)
                stats["total_duration_estimate_min"] += int(duration.total_seconds() // 60)
            for message in session.messages:
                if message.role not in stats["tools_used"][source]["messages"]:
                    stats["tools_used"][source]["messages"][message.role] = 0
                stats["tools_used"][source]["messages"][message.role] += 1

        stats["tools_used"][source]["tools"] = dict(sorted(tools.items()))
        if source == "codex":
            stats["tools_used"][source]["available_skills"] = sorted(available_skills)
            stats["tools_used"][source]["available_plugins"] = sorted(available_plugins)

    projects = []
    for (name, source), session_ids in sorted(project_sessions.items()):
        projects.append({"name": name, "source": source, "sessions": len(session_ids)})
    stats["projects_touched"] = projects
    return stats


def build_signal_markdown(date_str: str, sessions: List[SessionData], tz: ZoneInfo) -> str:
    lines: List[str] = []
    for source_label, source_key in [("Claude Code", "claude_code"), ("Codex CLI", "codex")]:
        source_sessions = [s for s in sessions if s.source == source_key]
        if not source_sessions:
            continue

        project_groups: Dict[str, List[SessionData]] = defaultdict(list)
        for session in sort_sessions(source_sessions):
            has_signal = session.away_summaries or session.ai_title or session.last_prompt
            user_msgs = [m for m in session.messages if m.role == "user"]
            if has_signal or user_msgs:
                project_groups[session.project_name].append(session)

        if not project_groups:
            continue

        lines.append("# %s — %s" % (source_label, date_str))
        lines.append("")

        for project_name in sorted(project_groups.keys()):
            project_sessions = project_groups[project_name]
            lines.append("## %s" % project_name)
            lines.append("")

            seen_prompts: set = set()

            for session in project_sessions:
                if session.ai_title:
                    lines.append("### %s" % session.ai_title)
                    lines.append("")

                if session.away_summaries:
                    last_summary = session.away_summaries[-1]
                    lines.append("**Recap:**")
                    lines.append("> %s" % last_summary)
                    lines.append("")

                if session.last_prompt:
                    prompt_key = session.last_prompt[:200]
                    if prompt_key not in seen_prompts:
                        seen_prompts.add(prompt_key)
                        prompt_preview = session.last_prompt[:300]
                        if len(session.last_prompt) > 300:
                            prompt_preview += "..."
                        lines.append("**Prompt:**")
                        lines.append("> %s" % prompt_preview)
                        lines.append("")

                user_msgs = [m for m in session.messages if m.role == "user"]
                if user_msgs:
                    lines.append("**User said:**")
                    for msg in user_msgs:
                        text = msg.text[:200]
                        if len(msg.text) > 200:
                            text += "..."
                        lines.append("- [%s] %s" % (local_time(msg.timestamp, tz), text))
                    lines.append("")

            if session.source == "codex":
                asst_msgs = [m for m in session.messages if m.role == "assistant"]
                if asst_msgs:
                    lines.append("**Agent said:**")
                    for msg in asst_msgs[:10]:
                        text = msg.text[:200]
                        if len(msg.text) > 200:
                            text += "..."
                        lines.append("- [%s] %s" % (local_time(msg.timestamp, tz), text))
                    if len(asst_msgs) > 10:
                        lines.append("- ... (%d more)" % (len(asst_msgs) - 10))
                    lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def run_daily(date_str: str, config: Dict[str, Any], *, dry_run: bool = False) -> JournalEntry | None:
    """Run the daily pipeline for a given date. Returns JournalEntry or None."""
    tz_name = config["general"]["timezone"]
    tz = ZoneInfo(tz_name)
    output_dir = Path(config["general"]["output_dir"]).expanduser()
    journal_root = Path(config["general"]["journal_root"]).expanduser()

    start, end = day_bounds(date_str, tz)

    # Step 1: Extract from all enabled sources
    from aij.sources.registry import get_source, list_source_names

    sessions: List[SessionData] = []
    sources_config = config.get("sources", {})
    for source_name in list_source_names():
        source_cfg = sources_config.get(source_name, {})
        if not source_cfg.get("enabled", True):
            continue
        source = get_source(source_name)
        if not source:
            continue
        source.configure(source_cfg)
        detected = source.detect()
        if not detected:
            continue
        for path in source.find_files(date_str):
            parsed = source.parse_file(path, start, end)
            if parsed:
                sessions.append(parsed)

    if not sessions:
        print("No sessions found for %s" % date_str)
        return None

    # Step 2: Build stats and signal markdown
    stats = build_stats(date_str, sessions)
    signal_content = build_signal_markdown(date_str, sessions, tz)

    # Save intermediate artifacts
    extraction_dir = output_dir / date_str
    extraction_dir.mkdir(parents=True, exist_ok=True)

    signal_path = extraction_dir / "signal_conversations.md"
    stats_path = extraction_dir / "stats.json"

    if not dry_run:
        signal_path.write_text(signal_content, encoding="utf-8")
        stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Step 3: Build prompt
    prompt_template = _load_prompt("daily.txt")
    prompt = prompt_template.replace("{data_tag}", "signal").replace(
        "{data_content}", signal_content
    ).replace("{stats}", json.dumps(stats, ensure_ascii=False, indent=2))

    if dry_run:
        print("=== Dry Run ===")
        print("Date: %s" % date_str)
        print("Sessions: %d" % len(sessions))
        print("Signal: %d chars" % len(signal_content))
        print("Prompt: %d chars" % len(prompt))
        return None

    # Step 4: Call summarizer
    from aij.summarizers.registry import get_summarizer

    backend = config["summarizer"]["backend"]
    summarizer_config = config["summarizer"].get(backend, {})
    summarizer = get_summarizer(backend, summarizer_config)
    if not summarizer:
        raise RuntimeError("Summarizer '%s' not available" % backend)

    print("Backend: %s | Model: %s" % (backend, getattr(summarizer, "model", "?")))
    summary = summarizer.call(prompt)

    # Step 5: Build journal entry
    frontmatter = build_frontmatter(date_str, stats)
    title = "# %s %s" % (date_str, weekday_name(date_str))

    entry = JournalEntry(
        date_str=date_str,
        entry_type="daily",
        frontmatter=frontmatter,
        body=summary,
        title=title,
    )

    # Step 6: Deliver via output plugins
    from aij.outputs.registry import get_enabled_outputs

    outputs_config = config.get("outputs", {})
    for output in get_enabled_outputs(outputs_config):
        output.deliver(entry)

    return entry
