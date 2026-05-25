# ai-thinking-journal

**Your AI coding conversations, distilled into a daily thinking journal.**

You spend hours every day talking to AI coding assistants. Decisions get made, insights emerge, bugs get squashed — then the conversation scrolls away and you forget what you were thinking.

`aij` reads your local conversation transcripts from Claude Code, Codex CLI, Cursor, and Windsurf, then uses an LLM to write a structured daily journal entry in your own voice. Not a corporate report. A thinking diary.

```
$ aij run

  ╭──────────────────────────────────────────╮
  │  aij — Daily Thinking Summary            │
  │  2026-05-25 Sunday                       │
  ╰──────────────────────────────────────────╯

  ✓ Claude Code — 4 sessions, 3 projects
  ✓ Codex CLI — 2 sessions, 1 project

  Summarizing (openai / gpt-4o)...
  ✓ Summary generated (847 words)
  ✓ Saved to ~/ai-journal/daily/2026-05-25.md
  ✓ Sent to Lark webhook

  ╭──────────────────────────────────────────╮
  │  Done in 12s                             │
  ╰──────────────────────────────────────────╯
```

## Install

```bash
pip install ai-thinking-journal
```

Or with optional dependencies:

```bash
pip install ai-thinking-journal[rich]    # styled terminal output
pip install ai-thinking-journal[all]     # rich + keyring for secure credential storage
```

## Quick Start

```bash
# Interactive setup — auto-detects your AI tools, picks a summarizer, configures outputs
aij init

# Generate today's journal
aij run

# Generate for a specific date
aij run --date 2026-05-20

# Weekly rollup
aij run --weekly

# Monthly rollup
aij run --monthly

# Preview without calling LLM
aij run --dry-run
```

## How It Works

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Data Sources    │────▶│  Summarizer  │────▶│    Outputs       │
│                  │     │              │     │                  │
│  Claude Code     │     │  OpenAI      │     │  Markdown file   │
│  Codex CLI       │     │  Anthropic   │     │  Terminal         │
│  Cursor          │     │  Claude CLI  │     │  Lark webhook    │
│  Windsurf        │     │  Ollama      │     │  Lark app DM     │
│                  │     │              │     │  Email (SMTP)    │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

**Source plugins** scan local conversation files, extract messages from the target date, filter noise (tool output, system prompts, repeated boilerplate), and group by session.

**Summarizer** receives the filtered transcript and writes a structured journal with sections: today's theme, key decisions, action items, thinking highlights, tool usage patterns, and conversation index.

**Output plugins** deliver the journal wherever you want — local files, terminal, team chat, email.

## Supported Sources

| Source | Location | Status |
|--------|----------|--------|
| Claude Code | `~/.claude/projects/*.jsonl` | Stable |
| Codex CLI | `~/.codex/sessions/*.jsonl` | Stable |
| Cursor | `~/.cursor/logs/` | Experimental |
| Sources are auto-detected during `aij init`. No manual config needed. |

## Summarizer Backends

| Backend | Model | Notes |
|---------|-------|-------|
| `openai` | gpt-4o (default) | Requires `OPENAI_API_KEY` |
| `anthropic` | claude-sonnet-4-20250514 | Requires `ANTHROPIC_API_KEY` |
| `claude_cli` | (inherits CLI config) | Uses your local `claude` CLI |
| `ollama` | llama3 (configurable) | Runs locally, no API key |

## Output Plugins

| Plugin | Delivers to | Setup |
|--------|-------------|-------|
| `markdown` | `~/ai-journal/daily/` | Always on |
| `terminal` | stdout | Toggle in config |
| `lark_webhook` | Lark/Feishu group chat | Webhook URL |
| `lark_app` | Lark/Feishu DM | App ID + Secret + open_id |
| `email` | SMTP email | SMTP host/port/credentials |

## Commands

| Command | What it does |
|---------|-------------|
| `aij init` | Interactive setup wizard |
| `aij run` | Generate journal entry |
| `aij run --weekly` | Generate weekly rollup |
| `aij run --monthly` | Generate monthly rollup |
| `aij run --poster` | Also generate a poster prompt |
| `aij run --dry-run` | Preview without LLM call |
| `aij config show` | View current config (secrets redacted) |
| `aij config set <key> <value>` | Update a config value |
| `aij config edit` | Open config in $EDITOR |
| `aij status` | Show sources, summarizer, outputs, last run |

## Configuration

Config file: `~/.aij/config.toml`

```toml
[general]
timezone = "Asia/Taipei"
journal_root = "~/ai-journal"

[summarizer]
backend = "openai"

[summarizer.openai]
model = "gpt-4o"

[outputs.markdown]
enabled = true

[outputs.terminal]
enabled = false

[outputs.lark_webhook]
enabled = false
# webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/..."

[outputs.lark_app]
enabled = false
# app_id = ""
# app_secret = ""
# open_id = ""

[outputs.email]
enabled = false
# from_addr = ""
# to_addr = ""
# smtp_host = "smtp.gmail.com"
# smtp_port = 587
```

API keys are stored in `~/.aij/.env` (mode 600, never committed).

## Plugin Architecture

Sources, summarizers, and outputs are all Python entry-point plugins. To add a custom one:

```python
# my_source.py
from aij.sources.base import SourcePlugin

class MySource(SourcePlugin):
    name = "my_tool"
    display_name = "My AI Tool"

    def detect(self):
        return Path("~/.my-tool/sessions").expanduser() if Path("~/.my-tool/sessions").expanduser().exists() else None

    def find_files(self, date_str):
        # return list of session files for the given date
        ...

    def parse_file(self, path, start, end):
        # return SessionData with extracted messages
        ...
```

Register via `pyproject.toml` entry points:

```toml
[project.entry-points."aij.sources"]
my_tool = "my_source:MySource"
```

## Scheduling (macOS)

A launchd plist is included for nightly runs:

```bash
# Copy to LaunchAgents
cp launchd/com.pohanlee.daily-thinking-summary.plist ~/Library/LaunchAgents/

# Edit the paths in the plist, then load:
launchctl load ~/Library/LaunchAgents/com.pohanlee.daily-thinking-summary.plist
```

## Output Example

```markdown
---
date: 2026-05-25
day: Sunday
sources: [claude_code, codex_cli]
tools_used: [Read, Edit, Bash, Grep]
projects: [ai-thinking-journal, shopee-automation]
---

## 今日主題
今天主要在搞 aij 的開源發布，把個人日記從 git 裡拔掉，寫了一個 killer README。

## 關鍵決策
- 決定把 ai-journal/ 整個 gitignore，因為裡面有個人日記內容和 9.8MB 的 PNG 海報，不適合公開
- README 不放 emoji，保持乾淨專業的風格

## 待辦事項
- push 到 GitHub 並確認 repo 可見
- 考慮加 GitHub Actions CI

## 思考亮點
- 發現 .env 裡有真實 API key 但從未被 git 追蹤過，.gitignore 第一行就擋住了

## 工具使用觀察
大量使用 Read + Bash 做 repo 狀態盤點，Edit 只用來改 .gitignore。典型「先偵察再動手」的模式。

## 原始對話索引
### ai-thinking-journal
- Claude Code session: 開源發布流程 — 清理 git 追蹤、建立 GitHub repo、寫 README
```

## Why?

You already think through problems with AI every day. Those thinking patterns are valuable — they show how you approach decisions, what tradeoffs you consider, what you learn.

But conversations are ephemeral. `aij` turns them into a persistent, searchable thinking journal that you own. No cloud sync. No subscription. Just your data, processed locally, delivered wherever you want.

## License

MIT
