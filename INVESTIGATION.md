# Daily Thinking Summary Pipeline — Feasibility Investigation

**Date**: 2026-05-14
**Status**: Green Light — Fully Feasible

---

## Stage 1: Data Source Investigation

### Claude Code (`~/.claude/`)

#### Source A: Per-project conversation transcripts (PRIMARY)

- **Path**: `~/.claude/projects/<encoded-project-path>/<sessionId>.jsonl`
- **Format**: JSONL (one JSON object per line)
- **Total files**: 321 across all projects
- **Content**: Full conversation transcripts — both `type: "user"` and `type: "assistant"` messages with complete text
- **Timestamps**: Every message has ISO 8601 `timestamp` field
- **Metadata**: `sessionId`, `cwd`, `version`, `gitBranch`, `model`, token `usage`
- **Size**: 11KB–1.7MB per session
- **Permissions**: mode 600, owned by user (readable)

#### Source B: User input history

- **Path**: `~/.claude/history.jsonl`
- **Format**: JSONL, 3.4MB, 15,034 lines
- **Content**: User input only (`display`, `timestamp`, `project`, `sessionId`). No AI responses.
- **Use case**: Session index / project activity detection only.

#### Source C: Session metadata

- **Path**: `~/.claude/sessions/<pid>.json`
- **Content**: `pid`, `sessionId`, `cwd`, `startedAt`, `version`, `status`

---

### Codex CLI (`~/.codex/`)

#### Source A: Rollout transcripts (PRIMARY)

- **Path**: `~/.codex/sessions/2026/MM/DD/rollout-<ISO-timestamp>-<uuid>.jsonl`
- **Format**: JSONL
- **Total**: 1,079 files, 782MB
- **Content**: Full transcripts — metadata, system prompt, all messages, tool calls, results
- **Timestamps**: In filename AND inside each line
- **Size**: 36KB–9.5MB per session

#### Source B: Thread database

- **Path**: `~/.codex/state_5.sqlite`
- **Tables**: `threads` (298 rows), `stage1_outputs` (72 rows with `rollout_summary`)
- **Key columns**: `id`, `title`, `created_at`, `updated_at`, `cwd`, `first_user_message`, `tokens_used`, `model`

#### Source C: Session index

- **Path**: `~/.codex/session_index.jsonl`
- **Content**: `session_id`, `thread_name`, `updated_at`

#### Source D: System logs (NOT useful)

- **Path**: `~/.codex/logs_2.sqlite` — 385MB HTTP/TRACE logs, no conversation content.

---

### Other Sources

- `~/.config/codex/` — config only (`config.toml`, `mcp.json`)
- `~/.zsh_history` — shell commands only, no conversation content
- No other AI tool data stores found

---

## Stage 2: Technical Feasibility

### Data Extraction

**Claude Code**:
- Parse `~/.claude/projects/*/<uuid>.jsonl`
- Filter lines where `type == "user"` or `type == "assistant"`
- Filter by `timestamp` for today's date
- User messages: `message.content` is a string
- Assistant messages: `message.content` is an array of objects (`text`, `thinking`, `tool_use`)

**Codex**:
- Fast metadata: `SELECT * FROM threads WHERE datetime(created_at, 'unixepoch') >= 'YYYY-MM-DD'`
- Full data: Parse rollout JSONL filtered by filename date pattern
- Pre-compressed: Read `stage1_outputs.rollout_summary`

### Date Filtering Proof

- Claude Code: `find ~/.claude/projects -name "*.jsonl" -mtime 0` returns 13 files (May 14)
- Codex: Filename format `rollout-YYYY-MM-DDTHH-MM-SS-uuid.jsonl` enables direct date filtering

### Volume Estimate

- Typical day: 10–20 session files across both tools
- Average size: ~300KB (Claude Code), ~700KB (Codex)
- Daily raw total: ~5–15MB JSONL
- Extracted text: ~50K–200K tokens/day — must batch by session for summarization

### Automation Options

| Mechanism | Pros | Cons |
|-----------|------|------|
| launchd | Runs when terminal closed, macOS native | More complex plist syntax |
| cron | Simple | Unreliable if machine was sleeping |
| claude -p | Non-interactive CLI mode | Depends on Claude Code being installed |

---

## Stage 3: Architecture Recommendation

### Pipeline Design

```
launchd (23:30 nightly)
    │
    ▼
Step 1: Extract (Python)
  - Scan ~/.claude/projects/*/<uuid>.jsonl (mtime=today)
  - Scan ~/.codex/sessions/YYYY/MM/DD/ (filename date)
  - Parse JSONL → extract user+assistant text
  - Group by project, sort by timestamp
    │
    ▼
Step 2: Summarize (Claude API / claude -p)
  - Per-session: compress to structured summary
  - Aggregate: merge session summaries → daily digest
  - Output: topics, decisions, todos, insights
    │
    ▼
Step 3: Output
  - Write Obsidian vault: YYYY-MM-DD-daily-thinking.md
  - Optional: git commit + push
```

### Risks and Limitations

1. **Data completeness**: `.last-cleanup` exists — sessions may be pruned. Verify cleanup policy.
2. **Privacy**: Summaries sent to API for processing — consider redaction for sensitive content.
3. **Token cost**: ~$0.50–2.00/day via API. Use Haiku for cost efficiency.
4. **File permissions**: mode 600 — script runs as same user, no issue.
5. **Codex volume**: 782MB total — always filter by date before loading.
