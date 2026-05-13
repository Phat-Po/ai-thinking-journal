# Task 01: Extraction POC

**Goal**: Python script that scans today's Claude Code conversation files and extracts all user+assistant text into a readable markdown file.

**Status**: Pending

## Input

- `~/.claude/projects/*/<uuid>.jsonl` — filter by file mtime = today
- Each line is a JSON object with `type` field

## Extraction Logic

1. Glob all `~/.claude/projects/*/<uuid>.jsonl` files
2. Filter by `mtime >= start-of-today`
3. For each file, read line by line:
   - If `type == "user"` → extract `message.content` (string)
   - If `type == "assistant"` → extract `message.content[*].text` where `type == "text"`
   - Skip: `type == "attachment"`, `type == "system"`, `type == "file-history-snapshot"`, `type == "last-prompt"`, `type == "permission-mode"`
4. Output: Markdown with session headers and timestamped messages

## Output Format (Draft)

```markdown
# Daily Thinking Log — 2026-05-14

## Session: friend-circle-hackathon
**Started**: 2026-05-13T17:22:20Z | **Project**: 20260501__docs__friend-circle-hackathon

### 17:22 — User
[message text]

### 17:23 — Claude
[response text]

---

## Session: amazon-store-health-dashboard
...
```

## Acceptance Criteria

- [ ] Script runs without errors on today's data
- [ ] Output is valid markdown
- [ ] Both user and assistant messages are captured
- [ ] Timestamps are human-readable (HH:MM format)
- [ ] Project name is decoded from directory path (replace `-` with `/`, etc.)
- [ ] Tool call details and thinking blocks are excluded (text only)
