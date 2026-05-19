# Journal Poster Workflow

Project-specific workflow for turning AI journal markdown into Xiaohongshu posters with the `xhsposter-wpd` skill.

## Purpose

Use this workflow whenever this project asks to turn a daily, weekly, or monthly journal into a poster.

The poster should feel like a visual diary or recap, not a slogan cover. It should show what happened, what got solved, what got stuck, what changed, and what comes next.

## Poster Modes

Weekly posters support two modes:

### project-narrative (default for weekly posters)

Focuses on **project advancement** — what moved forward, what breakthroughs happened, what bottlenecks remain, and what the next move is.

The poster should answer: "这周项目推进到了哪里？"

Not: "这周执行了哪些技术操作？"

Use this mode by default for all weekly poster requests unless the operator explicitly asks for a technical review.

### internal-review

Focuses on **technical process and workflow** — what tools were used, how the team worked, what workflows improved, what decisions were made at the execution level.

Use this mode **only** when the operator explicitly asks for: technical recap, internal review, workflow recap, tool usage analysis, or similar process-focused requests.

---

## Context Lookup (project-narrative mode only)

When generating a weekly poster in project-narrative mode, enrich the weekly summary with project-specific context. This is a fast lookup, not a full project audit.

### Step 1 — Read weekly summary

Read the source weekly journal markdown. Extract:
- Mood and overall state
- Decisions made
- Unresolved issues (as rough directions, not final content)
- Next week's priority

### Step 2 — Pick top projects

From the weekly summary's frontmatter `top_projects`, select the **top 2–4 most relevant projects** (the ones that had the most activity or were most impactful that week).

### Step 3 — Fast file inspection

For each selected project, read **only** these high-signal files if they exist:
- `STATUS.md`
- `HANDOFF.md`
- `AGENTS.md` or `README.md`

Do **not** read source code, scan directory trees, or do broad exploration. The goal is to understand the project's current state in 1–2 minutes per project.

### Step 4 — Extract this week's state

From each inspected project, extract only:
- What advanced this week
- What project problem it served
- What breakthrough happened
- What bottleneck remains
- What next step matters

### Step 5 — Rewrite story blocks

Use the enriched context to rewrite the five poster story blocks (see Extraction Order below) through the lens of **project advancement**, not raw journal bullets. Translate technical shorthand into outside-readable project narratives.

---

## Extraction Order

Read the source journal markdown and extract these five story blocks:

1. Current mood
   - What was the overall state of the week or day?
   - Examples: busy but productive, stuck but controlled, chaotic cleanup, heavy debugging, shipping momentum.

2. Solved problems
   - What was actually fixed, improved, simplified, shipped, or clarified?
   - In project-narrative mode: frame as project progress ("朋友圈黑客松活动流程变轻了"), not implementation details ("改用方案 C 约束引擎").
   - Prefer visible outcomes over process details.

3. Blockers
   - What is still stuck or uncertain?
   - In project-narrative mode: explain what project goal is blocked, not what code is broken.
   - Convert internal labels into plain visual concepts.

4. Project outcomes
   - What changed in the project because of this work?
   - In project-narrative mode: focus on what the project can now do, or what became possible, not what was technically changed.
   - Examples: more stable flow, lighter event design, saved disk space, clearer handoff, safer automation.

5. Next plan
   - What is the next most important thing?
   - In project-narrative mode: frame as the next project milestone, not the next code change.
   - This should usually become the bottom arrow, next mission marker, or final panel.

---

## Visual Style

Default style: **Flat Illustration / Infographic**

- Bold geometric shapes, strong color blocks, high contrast borders
- Deep saturated backgrounds with bright accent color pops
- Panel borders: 3-4px dark strokes for thumbnail readability
- Clean iconography: flat icons, progress bars, gauges, data callouts
- Typography: bold sans-serif for titles, clean labels for data points
- No chibi mascots, no anime cel-shading, no kawaii aesthetics
- No speed lines, no manga screentones, no comic reaction symbols
- Think: infographic dashboard meets visual diary, not anime magazine cover

Only use `Manga / Comic` style when the operator explicitly requests it.

## Visual Translation Rules

Prefer pictures over text. Use:

- icon panels with bold borders
- badges and stamps
- progress bars and gauges
- data callouts with numbers
- folders and file icons
- warning signs and checkmarks
- arrows and flow indicators
- maps and dashboards
- before / after contrast
- geometric shapes as visual metaphors

Avoid:

- dense paragraphs
- generic motivational slogans
- internal-only codes
- task IDs that outside readers cannot understand
- fake screenshots
- chibi mascots or anime-style characters
- overexplaining the journal

## Text Budget

Default cover text should stay minimal:

- One main title
- One short hook
- Three to six tiny visual labels at most
- Brand lines from `xhsposter-wpd`
- Terminal symbol `>_`

Tiny labels should explain visual panels, not replace the illustration.

## Blocker Translation

When the journal contains internal shorthand, translate it into outside-readable concepts.

Examples:

- `B2` / `B4` -> unfinished handoff route, broken roadmap pieces, unconnected workflow segments
- missing templates -> empty folders with question marks
- review pending -> poster draft and rules document stamped `REVIEW?`
- large backup uncertainty -> oversized backup box weighing down the disk
- blocked migration -> locked bridge or checkpoint gate

## Weekly Poster Composition

For weekly journals, use a recap layout:

- Center: the week's emotional state and workbench scene
- Left or upper panels: solved problems and wins
- Right or lower panels: blockers and unresolved issues
- Bottom: next week's main mission

The composition should show both momentum and friction.

## Daily Poster Composition

For daily journals, use a worklog layout:

- Center: the day's main work scene
- Side badges: solved items and discoveries
- Obstacle mark: the one biggest blocker
- Bottom marker: tomorrow's next action

## Monthly Poster Composition

For monthly journals, use a map or dashboard layout:

- Main map: projects or themes across the month
- Outcome markers: shipped, improved, archived, blocked
- Mood line: overall operating state
- Next month marker: the main direction

## Required Validation

After image generation:

1. Locate the generated PNG under `$CODEX_HOME/generated_images/`.
2. Check dimensions with `sips -g pixelWidth -g pixelHeight`.
3. Accept if the width / height ratio is within ±15% of 4:5 (roughly portrait — block only obvious 横图 / 正方形).
4. Copy the accepted image into `ai-journal/posters/`.
5. Leave the original generated image in place.
6. Report the saved project path and measured dimensions.

If the ratio is grossly off (clearly landscape or square), warn and report measured sizes — do not auto-regenerate.
