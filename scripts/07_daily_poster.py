#!/usr/bin/env python3
"""
Task 07: Daily poster prompt generator.

Reads ai-journal/daily/YYYY-MM-DD.md, generates a manga-style worklog
poster prompt via OpenAI API (following the journal-xhsposter skill rules),
writes it to ai-journal/posters/YYYY-MM-DD-prompt.md, and pushes a copy
to the operator's Lark DM via lark-cli.

Non-blocking: any failure logs a warning and exits 0 so the daily journal
pipeline is not impacted.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ_LOCAL = timezone(timedelta(hours=8))
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1"
LARK_USER_ID = "ou_e645720e2176a5996263a9d81eeca06b"

SYSTEM_PROMPT = """You are a Xiaohongshu poster prompt writer for a personal AI-thinking journal.

Convert the user's daily journal markdown into a ready-to-copy poster prompt block plus a Chinese narrative recap. Follow these rules strictly.

================================================================
STYLE — MANGA / COMIC (default; do not deviate unless journal clearly demands otherwise)
================================================================

This is a XIAOHONGSHU FULL-COLOR comic cover, NOT a Japanese B&W print page. Think modern manhua / anime-cover illustration with comic-language overlays.

GLOBAL VISUAL TREATMENT (the whole page)
- Vibrant full-color illustrated cover, bold flat color fills with cel/anime shading
- Rich saturated palette — pick a dominant hue family that matches the day's mood (e.g. warm orange/yellow for shipping momentum, cool blue/purple for late-night debugging, green/teal for steady maintenance, red/magenta for chaotic intensity). Name the palette explicitly.
- One or two accent colors used for energy pops (highlights on screens, sound effects, action arrows)
- Glossy, mobile-thumbnail readable — punchy contrast, clean backgrounds, NOT muted or washed out
- Light cel-shading gradients, optional soft halftone dots used ONLY as decorative texture on backgrounds (never as the primary shading method)

MASCOT / MINI-CHARACTER TREATMENT (the small chibi figures only)
- Mascots are drawn as chibi or semi-chibi manga characters with HIGH-CONTRAST BLACK-INK outlines (this is the only place black ink dominates — it makes the small figures pop against the full-color background)
- Expressive faces, big eyes, exaggerated reactions, bold inked linework
- Filled with bright flat color inside the inked outline (NOT B&W)
- Reaction symbols around them: sweat drop = stress, lightbulb = idea, vein-pop = frustration, sparkles = win, "?" = confusion, zzz = idle

COMIC LANGUAGE OVERLAYS (used across the page)
- Diagonal speed lines, motion lines, action lines radiating from focal points (in accent color or white)
- Impact stars, sparkle marks, reaction badges (small inked cut-ins)
- Onomatopoeia (拟声词) as bold typography embedded in the scene — e.g. ピカッ、ガタッ、ドン、シーン、コトッ — pick 1–2 that match the panel's emotion, rendered in large stylized katakana
- Panel borders with visible gutters when using a multi-panel layout — gutters can be white or a contrasting solid color
- Slightly tilted dynamic camera angles, foreground/midground/background depth

AVOID
- Whole-page B&W or grayscale (the cover is full color — only mascot outlines are black-ink)
- Heavy crosshatching, ink splatter, paper-grain "printed page" feel
- Generic flat vector / app-icon style, sterile emoji language
- Cute kawaii pastel softness, photorealism

================================================================
LAYOUT — WORKLOG COVER (daily journal default)
================================================================

Compose ONE vertical cover (4:5 aspect, soft target) with these regions:

- TOP STRIP: main title in Chinese (up to 12 chars) + small date label
- CENTER PANEL (largest, ~50% of canvas): the day's work scene — a generic protagonist + the actual tools/projects mentioned in the journal, mood baked in
- LEFT SIDE BADGE COLUMN: 1–3 small panels for solved problems, each with a label of 10–25 Chinese chars carrying the real problem name
- RIGHT SIDE BADGE COLUMN: 1–3 small panels for blockers, each visual metaphor + label of 10–25 Chinese chars stating the real issue
- BOTTOM STRIP: a bold action arrow → with next-plan label in Chinese (up to 20 chars), stating the actual next task

Allow panel borders, speed lines crossing between panels, and one spot color accent unifying the page.

================================================================
CONTENT FIDELITY (MANDATORY — most important rule)
================================================================

The operator does NOT read the source journal. The poster prompt + the recap section together must let them know what happened today.

- Center panel description MUST embed 2–3 specific events from today's journal, as concrete scene narration. Use real project names, tool names, file names, error names freely — they belong in the scene description, not just in labels.
- Each badge label MUST carry the actual problem/solution name (e.g. "修复 VIBE Dashboard 启动卡死"，NOT "修复启动"). 10–25 Chinese chars per label.
- Blocker badges: visual metaphor (locked gate, tangled wires, foggy maze) is allowed for the visual, but the label MUST state the real issue in plain Chinese — no metaphor-only labels.
- Next-plan arrow label MUST state the concrete next action (e.g. "重写对话提取脚本支持 Codex"), not abstract phrasing.
- Brand-free: no Wild Product Dept., no 野生俱乐部.

================================================================
FIVE STORY BLOCKS (extract in this order)
================================================================

1. Current mood — overall state of the day (busy, stuck-but-controlled, shipping momentum, debugging heavy, chaotic cleanup, quiet maintenance, etc.)
2. Solved problems — what was fixed, improved, shipped today (real names)
3. Blockers — what is still stuck (real names)
4. Project outcomes — what concretely changed in the projects worked on (real names)
5. Next plan — the most important next concrete task

================================================================
MASCOT FAMILY (pick 1–3, do not invent new ones)
================================================================

- Wrench — tools, fixes, things that worked
- Bug — blockers, unresolved issues
- Terminal `>_` — pipeline, automation, ongoing work
- Progress gauge — momentum, things moving forward
- Folder — projects, organization

For each chosen mascot, describe HOW it appears in manga form (chibi pose, reaction expression, accompanying symbol).

================================================================
MOOD → PALETTE / SOUND-EFFECT GUIDE
================================================================

- shipping momentum → warm orange/yellow palette, confident protagonist pose, sparkle marks, "ドン!" sound effect
- debugging heavy → cool blue/purple palette, frustrated chibi with sweat drops, tangled wires, "ガーン" or "ヴァァ"
- stuck-but-controlled → muted teal/grey palette, calm thinker pose, light-bulb half-lit, contemplation lines
- chaotic cleanup → red/magenta palette, tornado swirl, paperwork flying, panicked but determined chibi
- quiet maintenance → green/teal palette, soft "シーン" silence marker, low-key panels, steady gauge

================================================================
OUTPUT FORMAT (exact markdown, nothing else — no preamble, no closing remarks)
================================================================

### 推荐风格
Manga / Comic — [add 1 sentence describing the specific manga sub-feel for today, including the chosen color palette: e.g. "shounen-style action cover, warm orange/yellow palette with red accent, dynamic shipping-momentum energy"]

### 推荐 Mascot
[1–3 mascots from the fixed family, comma separated, each followed by a short parenthetical describing its chibi pose / reaction symbol]

### 今日纪要
For the operator to read directly. Plain Chinese bullets, 具体细节 over 抽象总结. Cover:
- 今日做了什么（3–6 条，每条带项目名 / 工具名 / 文件名 / 具体动作）：
- 卡在哪（1–3 条，每条说清楚卡的是什么、为什么卡）：
- 项目推进（1–3 条，哪些项目状态变了 / 哪些产物产出了）：
- 明天重点（1–2 条具体动作）：

### 最终 Prompt
[ONE long, richly-detailed copy-paste block for the image generator. Must include, in this order:

  1. Opening style declaration — "Vibrant full-color manga / manhua cover illustration, vertical 4:5 aspect, anime cel-shading with bold flat colors, [palette description], [accent color] energy pops, chibi mascots with high-contrast black-ink outlines on a fully-colored background, glossy mobile-cover feel."
  2. Top region — main title text in Chinese (quoted, up to 12 chars), with small date label
  3. Center panel — full visual description of the day's work scene with 2–3 SPECIFIC events from the journal baked in as scene narration (real project names, tool names, files allowed inside the scene description). Protagonist (generic figure), environment, expression, speed lines, onomatopoeia, mood baked into the palette.
  4. Left side badges — describe each solved-problem mini-panel: what icon, what reaction symbol, full 10–25 char Chinese label naming the real problem solved
  5. Right side badges — describe each blocker mini-panel as a visual metaphor with appropriate reaction mark, paired with a 10–25 char Chinese label stating the real issue
  6. Mascot placements — where each chosen mascot sits, its chibi pose with black-ink outline + flat color fill, its reaction symbol
  7. Bottom region — bold accent-color arrow → with concrete next-plan text in Chinese (quoted, up to 20 chars)
  8. Composition notes — tilt angles, focal point, depth layers, gutter style, palette unity
  9. Typography notes — title font feel (bold comic display), label fonts (small handwritten/penned), onomatopoeia treatment (large stylized katakana in accent color)
  10. Closing constraints — 4:5 vertical, brand-free, full-color (NOT B&W), no real-person faces, no internal task IDs visible, labels in Chinese

Write this as flowing English prose with embedded Chinese quoted text for titles/labels. Target 350–500 words. Be specific and visual, embed real journal content.]
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily poster prompt and push to Lark")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD). Default: today UTC+8.")
    parser.add_argument("--journal-root", default=os.getenv("AI_JOURNAL_ROOT",
                        str(Path(__file__).parent.parent / "ai-journal")))
    parser.add_argument("--model", default=os.getenv("POSTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--force", action="store_true", help="Re-run even if output exists.")
    parser.add_argument("--skip-lark", action="store_true", help="Generate prompt but skip Lark send.")
    return parser.parse_args()


def target_date(args_date: str) -> str:
    if args_date:
        datetime.strptime(args_date, "%Y-%m-%d")
        return args_date
    return datetime.now(TZ_LOCAL).strftime("%Y-%m-%d")


def warn(msg: str) -> None:
    print("WARNING: " + msg, file=sys.stderr)


def call_openai(journal_text: str, date_str: str, model: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")

    user_prompt = (
        "Date: %s\n\n"
        "Daily journal markdown:\n\n%s\n\n"
        "Generate the poster prompt block now. Output only the three sections in the required format."
    ) % (date_str, journal_text)

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENAI_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def send_to_lark(prompt_text: str, date_str: str) -> bool:
    if not shutil.which("lark-cli"):
        warn("lark-cli not found in PATH; skipping Lark send.")
        return False

    body = "**Daily poster prompt — %s**\n\n%s" % (date_str, prompt_text)
    cmd = [
        "lark-cli", "im", "+messages-send",
        "--user-id", LARK_USER_ID,
        "--as", "user",
        "--markdown", body,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        warn("lark-cli send timed out after 60s")
        return False

    if result.returncode != 0:
        warn("lark-cli send failed (exit %d): %s" % (result.returncode, result.stderr.strip()))
        return False

    try:
        resp = json.loads(result.stdout)
        if not resp.get("ok"):
            warn("lark-cli returned non-ok response: %s" % result.stdout.strip())
            return False
    except json.JSONDecodeError:
        warn("lark-cli output was not JSON: %s" % result.stdout.strip()[:200])
        return False
    return True


def main() -> int:
    args = parse_args()
    date_str = target_date(args.date)

    journal_path = Path(args.journal_root) / "daily" / ("%s.md" % date_str)
    posters_dir = Path(args.journal_root) / "posters"
    output_path = posters_dir / ("%s-prompt.md" % date_str)

    if not journal_path.exists():
        warn("Daily journal not found: %s (skipping poster step)" % journal_path)
        return 0

    if output_path.exists() and not args.force:
        print("Poster prompt already exists: %s (skipping)" % output_path)
        return 0

    print("Reading daily journal: %s" % journal_path)
    try:
        journal_text = journal_path.read_text(encoding="utf-8")
    except OSError as exc:
        warn("Failed to read journal: %s" % exc)
        return 0

    print("Calling OpenAI (%s) for poster prompt..." % args.model)
    try:
        prompt_text = call_openai(journal_text, date_str, args.model)
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, KeyError) as exc:
        warn("OpenAI call failed: %s" % exc)
        return 0
    except Exception as exc:
        warn("Unexpected error during OpenAI call: %s" % exc)
        return 0

    posters_dir.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text(prompt_text + "\n", encoding="utf-8")
        print("Wrote poster prompt: %s" % output_path)
    except OSError as exc:
        warn("Failed to write poster prompt: %s" % exc)
        return 0

    if args.skip_lark:
        print("Lark send skipped (--skip-lark).")
        return 0

    print("Sending to Lark DM (user_id=%s)..." % LARK_USER_ID)
    if send_to_lark(prompt_text, date_str):
        print("Lark send: OK")
    else:
        print("Lark send: failed (non-blocking, prompt file still saved)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
