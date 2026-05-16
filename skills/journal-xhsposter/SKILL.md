---
name: journal-xhsposter
description: Generate Xiaohongshu poster prompts from AI journal markdown (daily, weekly, monthly). Default Manga style, 4:5 ratio. Supports project-narrative and internal-review modes for weekly posters. Always apply POSTER_WORKFLOW.md as the project layer before generating prompts.
---

# Journal XHSPoster

## Overview

Turn journal markdown into ready-to-copy Xiaohongshu cover prompts for this project's daily, weekly, and monthly thinking summaries.

This skill is the prompt-generation layer. It follows the same output format as `xhsposter-wpd` but is tailored for personal journal / recap posters instead of brand content.

**Always apply `ai-journal/posters/POSTER_WORKFLOW.md` first.** The workflow file decides:
- Which poster mode to use
- How to enrich content (context lookup for project-narrative mode)
- How to extract and reframe the five story blocks
- How to translate internal shorthand into visual metaphors

## Poster Modes (weekly only)

Weekly posters support two modes. Determine which mode before doing anything else.

### project-narrative (default)

Focus: project advancement — what moved forward, breakthroughs, bottlenecks, next moves.

The poster answers: **"这周项目推进到了哪里？"**

Do **not** answer: "这周执行了哪些技术操作？"

Use this mode by default for all weekly poster requests unless the operator explicitly asks for a technical review.

### internal-review

Focus: technical process — tools used, workflows improved, execution-level decisions.

Use **only** when the operator explicitly asks for: technical recap, internal review, workflow recap, tool usage analysis.

## Input Sources

The skill accepts any of these:

- A daily journal file (`ai-journal/daily/YYYY-MM-DD.md`)
- A weekly journal file (`ai-journal/weekly/YYYY-WNN.md`)
- A monthly journal file (`ai-journal/monthly/YYYY-MM.md`)
- Raw journal text pasted by the user

If the user provides a file path, read it. If they paste text, use it directly.

## Workflow

### 1. Determine poster mode

- Daily journals: always diary/worklog mode (no mode selection needed)
- Weekly journals: check if user asked for technical review. If yes → internal-review. Otherwise → project-narrative.
- Monthly journals: always map/dashboard mode (no mode selection needed)

### 2. Context enrichment (weekly project-narrative only)

Follow the Context Lookup section in `POSTER_WORKFLOW.md`:

1. Read the weekly summary frontmatter `top_projects`
2. Pick top 2–4 most relevant projects
3. For each: read `STATUS.md`, `HANDOFF.md`, or `AGENTS.md` (only if they exist)
4. Extract: what advanced, what problem it served, what breakthrough, what bottleneck, what next step
5. Do not read source code or scan directory trees

Skip this step for daily and monthly posters, and for internal-review mode.

### 3. Extract five story blocks

Follow the Extraction Order in `POSTER_WORKFLOW.md`. For each block:

1. **Current mood** — overall emotional state
2. **Solved problems** — what was fixed, improved, shipped
3. **Blockers** — what is still stuck
4. **Project outcomes** — what changed in the project
5. **Next plan** — the most important next thing

In project-narrative mode, reframe each block through project advancement lens (see POSTER_WORKFLOW.md for framing rules). Do not copy raw journal bullets.

### 4. Translate internal shorthand

Follow the Blocker Translation rules in `POSTER_WORKFLOW.md`. Convert internal codes (B2, B4, template references, etc.) into outside-readable visual concepts.

### 5. Select poster layout

Based on journal type:

- **Daily**: worklog layout — center work scene, side badges, obstacle mark, bottom next action
- **Weekly**: recap layout — center mood scene, left/wins, right/blockers, bottom next mission
- **Monthly**: map/dashboard layout — main theme map, outcome markers, mood line, next direction

### 6. Generate the prompt

Follow the xhsposter-wpd output format:

#### 推荐风格

Default: `Manga / Comic`. Only suggest a different style if the content clearly calls for it.

#### 推荐 Mascot

Select 1–3 from this fixed journal mascot family:

| Mascot | Represents | Use when |
|--------|-----------|----------|
| Wrench | Tools, fixes, things that worked | Solved problems panel |
| Bug | Blockers, unresolved issues | Blockers panel |
| Terminal `>_` | Pipeline, automation, ongoing work | Overall theme or next plan |
| Progress gauge | Momentum, things moving forward | Solved or outcomes panel |
| Folder | Projects, organization | Project outcomes panel |

Do not invent new mascots. Do not use generic icons — render them in the chosen style.

#### 最终 Prompt

One clean copy-paste block. Must include:

- Style direction (Manga / Comic)
- Layout type (worklog, recap, or map/dashboard)
- Main title (one line)
- Subtitle hook (one short line)
- Panel descriptions for each story block
- Mascot descriptions rendered in the chosen style
- Visual translation of blockers (no internal shorthand)
- Next plan as a bottom arrow or marker
- 4:5 vertical cover ratio requirement

Keep the cover clean enough to work as a mobile thumbnail. One dominant headline, minimal supporting text, short visual labels only.

#### 内页建议

Include when the post is multi-image (e.g., monthly recap with multiple themes). Suggest 2–4 inner pages that expand on the cover's summary.

### 7. Stop at prompt mode

Default output is **prompt mode**: output the prompt, wait for user confirmation.

Only switch to image mode when the user:
- Confirms the prompt and says "生成" / "开始生成" / "generate"
- Or explicitly asks to skip prompt review and go straight to image

### 8. Image mode (on confirmation)

When generating the image:

- Use the same style, mascots, and prompt from step 6
- Preserve all content — do not silently simplify
- Verify the generated image: `sips -g pixelWidth -g pixelHeight`
- Accept if width/height ratio is within ±15% of 4:5 (i.e. roughly portrait — block only obvious 横图 / 正方形)
- If ratio is grossly off, warn but still accept; do not auto-regenerate
- Do not crop, stretch, or pad to force compliance
- Copy accepted image to `ai-journal/posters/`
- Use filename pattern: `<date-or-week>-manga-cover-vN.png`
- Do not overwrite earlier versions unless operator asks

## Output Format

```
### 推荐风格
[Manga / Comic or other recommendation]

### 推荐 Mascot
[1–3 mascots from the fixed family]

### 最终 Prompt
[One clean copy-paste block]

### 内页建议
[Only for multi-image posts]
```

## Guardrails

- Always apply POSTER_WORKFLOW.md before generating prompts
- Do not copy raw journal bullets onto the cover — reframe for outside readers
- Do not use internal task IDs, codes, or shorthand in the prompt
- Keep brand-free — no Wild Product Dept. or 野生俱乐部 in journal posters
- One visual style per poster
- Keep element usage to the fixed journal mascot family only
- Default to prompt mode — do not generate images without confirmation
- In image mode, use a generous ±15% tolerance around 4:5 (roughly portrait is fine; only block obvious 横图 / 正方形)
- Never fix aspect ratio by cropping, stretching, or padding
