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

## XHS Poster Defaults

- **Primary skill**: `journal-xhsposter` (`skills/journal-xhsposter/SKILL.md`) — generates journal poster prompts from daily/weekly/monthly markdown. Always apply `POSTER_WORKFLOW.md` as the project layer first.
- **Fallback skill**: `xhsposter-wpd` — only for Wild Product Dept. branded posters. Not for journal posters.
- Default to `Flat Illustration / Infographic` style. Use bold geometric shapes, strong color blocks, high contrast borders, and clean iconography. Avoid chibi mascots, anime cel-shading, and kawaii aesthetics. Only use `Manga / Comic` when the operator explicitly requests it.
- **Poster modes**: Weekly posters have two modes. Default is `project-narrative` (project breakthroughs, bottlenecks, next moves). Use `internal-review` only when operator explicitly asks for technical/workflow recap.
- In project-narrative mode: the poster answers "这周项目推进到了哪里？", not "这周执行了哪些技术操作？". Do not copy weekly summary bullets directly — use context lookup to enrich project stories.
- Treat daily, weekly, and monthly journal posters as visual diary / recap posters, not slogan covers.
- Extract and show five story blocks by default: current mood, solved problems, blockers, project outcomes, and next plan.
- Prefer visual metaphors, icon panels, badges, data callouts, progress bars, gauges, arrows, and stamps over long text.
- Use deep saturated background colors with bright accent pops. Panel borders should be 3-4px dark strokes for thumbnail readability.
- Avoid internal-only labels, task IDs, or shorthand that outside viewers cannot understand. Translate them into plain visual concepts.
- Keep cover text minimal: one main title, one short hook, and only a few tiny labels where they improve comprehension.

## Dual-Repo Architecture

This project exists as **two independent repositories** with no common ancestor.
They share the same purpose but serve different audiences. **Never `git merge` them.**

| | Source Repo (this one) | Deploy Repo |
|---|---|---|
| Path | `20_PROJECTS_MAINTAIN/20260514__automation__daily-thinking-summary` | `~/daily-thinking-summary` |
| Purpose | Public OSS release (GitHub) | Operator's production nightly run |
| Audience | External users / contributors | Operator only |
| GitHub | Has remote | No remote |

### Mental Model

- **Deploy repo = 真身** — the runtime-hardened version that produces your real daily journals.
- **Source repo = 发行版** — the public-facing OSS release that others clone.

### Fix Flow (one-way)

1. Runtime bug fixes (idna crash, API retry, failure alert, date-leak) are **developed and verified in the deploy repo first**.
2. Once verified, they are **cherry-picked / manually ported to the source repo** for the next OSS release.
3. Never port from source → deploy for runtime fixes.

### Feature Flow (one-way, opposite)

1. Format/UX features (v2 short format, wizard, new templates) are **developed in the source repo**.
2. When the operator decides to adopt them, they are ported **source → deploy**.
3. That decision is separate from any runtime fix cycle.

### Hard Rules

- **Do NOT `git merge`** the two repos — no common ancestor, will produce conflicts.
- **Do NOT overwrite deploy with source** unless the operator explicitly wants to switch to v2 format. If doing so, runtime fixes must be re-verified and re-applied.
- **Do NOT hardcode personal identifiers** (Lark user IDs, webhook URLs, etc.) in the source repo. Use env vars with graceful fallback.
- **Do NOT `git push` the source repo** without operator confirmation (even for small fixes).

### Runtime Hardening in This Repo

As of 2026-06-04, the source repo includes these protections ported from the deploy repo:

| Protection | Where | Env var |
|---|---|---|
| idna codec preload | 5 scripts (`02`–`07`) | — (always on) |
| API retry with backoff | `03_summarize.py` (`call_openai`) | — (always on, 3 retries) |
| Failure alert | `run_pipeline.sh` | `LARK_ALERT_USER_ID` (optional; unset = log-only) |

If you add new runtime protections, follow the same pattern: verify in deploy → port to source.

## Task Sequence

1. Extraction POC — Python script to scan and extract today's conversations
2. Summarization — Claude API integration for daily digest generation
3. Output formatting — Obsidian YAML frontmatter + markdown template
4. Automation — launchd plist for nightly scheduling
5. Multi-source merge — Combine Claude Code + Codex into unified daily view
