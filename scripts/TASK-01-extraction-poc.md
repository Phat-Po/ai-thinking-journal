# Task 01: Extraction

**Goal**: Extract one local day of Claude Code + Codex CLI conversations into structured intermediate files for the journal pipeline.

**Status**: Complete for daily pipeline

## Inputs

- Claude Code: `~/.claude/projects/**/*.jsonl`
- Codex CLI: `~/.codex/sessions/YYYY/MM/DD/*.jsonl`
- Codex archived sessions: `~/.codex/archived_sessions/*.jsonl`

## Output

For each date:

```text
output/YYYY-MM-DD/
  filtered_conversations.md
  stats.json
```

`output/` is ignored by git.

## Extraction Logic

- User messages: keep full text.
- Assistant messages: keep first paragraph + last paragraph.
- Claude Code tools: count `tool_use.name`.
- Codex tools: count `function_call.name`.
- Codex reasoning summaries: include `reasoning.summary` as assistant summary material.
- Codex developer messages: reduce to skills/plugins names only.
- Drop `tool_result`, `function_call_output`, tool inputs, and pure noise messages.

## Usage

```bash
python3 scripts/01_extract.py
python3 scripts/01_extract.py --date 2026-05-14
```

## Acceptance Criteria

- [x] Script runs without errors.
- [x] Claude Code and Codex sessions are both parsed.
- [x] Text and tool statistics are separated.
- [x] Output includes `filtered_conversations.md` and `stats.json`.
- [x] Project names come from `cwd` final path segment.
