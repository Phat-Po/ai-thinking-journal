# Handoff - Daily Thinking Summary Pipeline

## Current Status

Task 01 (Extraction) - daily pipeline working for Claude Code + Codex
Task 02 (Daily Summarization) - working with product-spec prompt
Task 03 (Automation / Weekly / Monthly) - not started after scope change

Latest commit:

- `f6e94b4 reduce filtered conversation noise`

Working tree status at handoff: clean.

## What Changed

1. `scripts/01_extract.py` now reads Claude Code JSONL and Codex JSONL.
2. Extraction writes `output/YYYY-MM-DD/filtered_conversations.md` and `output/YYYY-MM-DD/stats.json`.
3. `scripts/02_summarize.py` reads those two files and writes `ai-journal/daily/YYYY-MM-DD.md`.
4. The default model is `qwen3-coder:480b-cloud` via local Ollama.
5. Codex `available_skills` and `available_plugins` are stored in `stats.json` only; they are environment inventory, not actual usage.

## Noise Fixes Already Applied

The main conversation markdown now filters:

- Codex bootstrap messages containing AGENTS instructions
- Codex developer messages
- Codex reasoning summaries
- Claude/Codex slash-command markup such as `<local-command-caveat>`
- `<system-reminder>...</system-reminder>` tag blocks
- Consecutive assistant messages in the same session and same local minute are merged

Validation on `2026-05-10`:

```text
AGENTS.md instructions: 0
^- skill:: 0
Reasoning summary:: 0
local-command-caveat: 0
<system-reminder: 0
size: 169,907 bytes
lines: 4,328
```

Before noise fixes this file was 286,247 bytes and 7,131 lines.

## Verified Commands

```bash
python3 -m py_compile scripts/01_extract.py scripts/02_summarize.py
python3 scripts/01_extract.py --date 2026-05-10
python3 scripts/01_extract.py --date 2026-05-14
python3 scripts/02_summarize.py --date 2026-05-14
python3 scripts/02_summarize.py --date 2026-05-14 --dry-run
```

## Known Caveats

- Host `python3` is 3.8.1, below the project baseline of Python 3.10, so current code is intentionally Python 3.8-compatible.
- Generated `output/` artifacts are ignored by git.
- `ai-journal/daily/2026-05-14.md` is tracked as the current verified sample output.
- The operator says there are still issues to modify next; do not assume Task 03 should start before diagnosing those issues.

## Next Step

Ask the operator for the remaining problem details, inspect the generated markdown/stat output, then decide whether the fix belongs in extraction, stats metadata, or the summary prompt.
