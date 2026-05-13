# Project AGENTS — Daily Thinking Summary Pipeline

Automated nightly pipeline that extracts AI conversation transcripts from Claude Code and Codex CLI, generates structured daily thinking summaries, and saves them to an Obsidian vault.

## Scope

- Data extraction from `~/.claude/projects/` and `~/.codex/sessions/`
- Summarization via Claude API or `claude -p` CLI
- Output to Obsidian-compatible markdown
- macOS launchd scheduling

## Constraints

- Read-only access to conversation data (never modify source files)
- No secrets in code — API keys go in `.env`
- Summaries are local-only by default (git push requires explicit approval)
- Respect file permissions (mode 600)

## Task Sequence

1. Extraction POC — Python script to scan and extract today's conversations
2. Summarization — Claude API integration for daily digest generation
3. Output formatting — Obsidian YAML frontmatter + markdown template
4. Automation — launchd plist for nightly scheduling
5. Multi-source merge — Combine Claude Code + Codex into unified daily view
