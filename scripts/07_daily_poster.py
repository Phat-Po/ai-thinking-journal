#!/usr/bin/env python3
"""
Task 07: Daily poster generator.

Reads ai-journal/daily/YYYY-MM-DD.md, generates a poster prompt via OpenAI API,
generates the poster image via OpenAI image API, writes prompt to
ai-journal/posters/YYYY-MM-DD-prompt.md, and sends the recap text + image
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
OPENAI_IMG_URL = "https://api.openai.com/v1/images/generations"
DEFAULT_MODEL = "gpt-4.1"
LARK_USER_ID = "ou_e645720e2176a5996263a9d81eeca06b"

SYSTEM_PROMPT = """You are a Xiaohongshu poster prompt writer for a personal AI-thinking journal.

Convert the user's daily journal markdown into a ready-to-copy poster prompt block plus a Chinese narrative recap. Follow these rules strictly.

================================================================
STYLE — FLAT ILLUSTRATION / INFOGRAPHIC (default; do not deviate unless journal clearly demands otherwise)
================================================================

This is a XIAOHONGSHU FULL-COLOR infographic-style cover. Think modern dashboard meets visual diary — bold geometric shapes, strong color blocks, high-contrast borders, clean iconography. NOT anime, NOT manga, NOT chibi.

GLOBAL VISUAL TREATMENT (the whole page)
- Clean flat illustration with bold geometric shapes and strong color blocks
- Rich saturated palette — pick a dominant hue family that matches the day's mood (e.g. warm orange/yellow for shipping momentum, cool blue/purple for late-night debugging, green/teal for steady maintenance, red/magenta for chaotic intensity). Name the palette explicitly.
- One or two accent colors used for energy pops (highlights on data callouts, progress indicators, action arrows)
- Deep saturated background with bright accent foreground elements
- Panel borders: 3-4px dark strokes for thumbnail readability
- Mobile-thumbnail readable — punchy contrast, clean backgrounds, NOT muted or washed out

ICON / PANEL TREATMENT
- Each project or data point gets its own distinct bordered panel with a unique accent color
- Use flat icons (wrench, gear, chart, document, microphone, etc.) as visual anchors — NOT characters
- Data callouts: bold numbers, progress bars, checkmark rows, comparison arrows (→)
- Badges: rounded rectangles with solid fills, dark stroke borders, clean sans-serif text
- Warning/blocker indicators: red accent borders, X marks, warning triangle icons

AVOID
- Chibi mascots, anime characters, kawaii aesthetics, big eyes, exaggerated expressions
- Speed lines, manga screentones, comic reaction symbols, onomatopoeia (拟声词)
- Heavy crosshatching, ink splatter, paper-grain "printed page" feel
- Cute kawaii pastel softness, photorealism
- Generic corporate vector / sterile emoji language

================================================================
LAYOUT — INFOGRAPHIC WORKLOG COVER (daily journal default)
================================================================

Compose ONE vertical cover (4:5 aspect, soft target) with these regions:

- TOP STRIP: main title in bold sans-serif Chinese (up to 12 chars) + small date badge
- CENTER PANEL (largest, ~50% of canvas): a 2x3 grid of icon panels, each showing one project as an infographic vignette with distinct accent color border
- LEFT SIDE BADGE COLUMN: 1–3 small rounded-rect badges for solved problems, each with a flat icon + label of 10–25 Chinese chars
- RIGHT SIDE BADGE COLUMN: 1–3 small rounded-rect badges for blockers, each with a warning icon + label of 10–25 Chinese chars stating the real issue
- BOTTOM STRIP: a bold accent-color arrow → with next-plan label in Chinese (up to 20 chars), stating the actual next task

Grid gutters use dark charcoal separators. Each panel has a unique accent color border for visual distinction.

================================================================
CONTENT FIDELITY (MANDATORY — most important rule)
================================================================

The operator does NOT read the source journal. The poster prompt + the recap section together must let them know what happened today.

- Center panel descriptions MUST embed 2–3 specific events from today's journal, as concrete data callouts. Use real project names, tool names, file names, error names freely — they belong in the panel description, not just in labels.
- Each badge label MUST carry the actual problem/solution name (e.g. "修复 VIBE Dashboard 启动卡死"，NOT "修复启动"). 10–25 Chinese chars per label.
- Blocker badges: use warning icons (red border, X mark, caution triangle) paired with a label that states the real issue in plain Chinese — no metaphor-only labels.
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
VISUAL ELEMENT FAMILY (pick icons, not mascots)
================================================================

- Wrench icon — tools, fixes, things that worked
- Warning triangle / X mark — blockers, unresolved issues
- Terminal prompt `>_` — pipeline, automation, ongoing work
- Progress bar / gauge — momentum, things moving forward
- Folder icon — projects, organization
- Checkmark circle — completed items
- Document page — files, outputs, deliverables
- Gear icon — configuration, settings, infrastructure

For each chosen element, describe how it appears as a flat icon with accent color fill and dark stroke border.

================================================================
MOOD → PALETTE GUIDE
================================================================

- shipping momentum → warm orange/yellow palette, bold data callouts, upward progress arrows
- debugging heavy → cool blue/purple palette, tangled wire icons, warning markers
- stuck-but-controlled → muted teal/grey palette, half-filled progress bars, contemplation icons
- chaotic cleanup → red/magenta palette, scattered document icons, bold warning badges
- quiet maintenance → green/teal palette, steady progress bars, checkmark rows

================================================================
OUTPUT FORMAT (exact markdown, nothing else — no preamble, no closing remarks)
================================================================

### 推荐风格
Flat Illustration / Infographic — [add 1 sentence describing the specific infographic feel for today, including the chosen color palette: e.g. "dashboard-style data visualization cover, warm orange/yellow palette with teal accent, bold shipping-momentum energy"]

### 推荐视觉元素
[2-4 flat icons from the element family, comma separated, each followed by a short parenthetical describing its visual treatment — accent color, stroke style, accompanying data callout]

### 今日纪要
For the operator to read directly. Plain Chinese bullets, 具体细节 over 抽象总结. Cover:
- 今日做了什么（3–6 条，每条带项目名 / 工具名 / 文件名 / 具体动作）：
- 卡在哪（1–3 条，每条说清楚卡的是什么、为什么卡）：
- 项目推进（1–3 条，哪些项目状态变了 / 哪些产物产出了）：
- 明天重点（1–2 条具体动作）：

### 最终 Prompt
[ONE long, richly-detailed copy-paste block for the image generator. Must include, in this order:

  1. Opening style declaration — "Clean flat illustration / infographic cover, vertical 4:5 aspect, bold geometric shapes with strong color blocks, [palette description], [accent color] energy pops, high-contrast dark panel borders, no chibi characters, no anime cel-shading, mobile-thumbnail readable, modern dashboard aesthetic."
  2. Top region — main title text in bold sans-serif Chinese (quoted, up to 12 chars), with small date badge
  3. Center panel grid — describe each of the 2x3 panels as an infographic vignette with distinct accent color border, embedding 2–3 SPECIFIC events from the journal as data callouts (real project names, tool names, numbers). Use flat icons, bold numbers, progress indicators.
  4. Left side badges — describe each solved-problem badge: what flat icon, accent color fill, full 10–25 char Chinese label naming the real problem solved
  5. Right side badges — describe each blocker badge: warning icon (red border, X mark), paired with a 10–25 char Chinese label stating the real issue
  6. Bottom region — bold accent-color arrow → with concrete next-plan text in Chinese (quoted, up to 20 chars)
  7. Composition notes — grid layout, accent color assignments per panel, gutter style, background texture (faint terminal symbols), palette unity
  8. Typography notes — title font (bold sans-serif, Inter/Helvetica Neue weight 700+), data numbers in large amber monospace, badge text in clean sans-serif
  9. Closing constraints — 4:5 vertical, brand-free, full-color, no real-person faces, no internal task IDs visible, labels in Chinese, no chibi/anime elements, flat infographic style

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


def call_openai_image(prompt: str, api_key: str, size: str = "1024x1280") -> bytes:
    payload = json.dumps({
        "model": "gpt-image-2",
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": "medium",
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_IMG_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    import base64
    return base64.b64decode(data["data"][0]["b64_json"])


def extract_section(text: str, header: str) -> str:
    """Extract content under a ### header until the next ### or end."""
    marker = "### " + header
    idx = text.find(marker)
    if idx < 0:
        return ""
    start = idx + len(marker)
    next_section = text.find("\n### ", start)
    if next_section < 0:
        return text[start:].strip()
    return text[start:next_section].strip()


def extract_recap(prompt_text: str) -> str:
    """Extract the 今日纪要 section as the text to send to Lark."""
    return extract_section(prompt_text, "今日纪要")


def extract_final_prompt(prompt_text: str) -> str:
    """Extract the 最终 Prompt section for image generation."""
    return extract_section(prompt_text, "最终 Prompt")


def send_to_lark(recap_text: str, date_str: str, image_path: str = None) -> bool:
    if not shutil.which("lark-cli"):
        warn("lark-cli not found in PATH; skipping Lark send.")
        return False

    lark_env = dict(os.environ, LARK_CLI_NO_PROXY="1")

    # Step 1: Send recap text
    body = "**Daily thinking — %s**\n\n%s" % (date_str, recap_text)
    cmd = [
        "lark-cli", "im", "+messages-send",
        "--user-id", LARK_USER_ID,
        "--as", "user",
        "--markdown", body,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=lark_env)
    except subprocess.TimeoutExpired:
        warn("lark-cli text send timed out after 60s")
        return False

    if result.returncode != 0:
        warn("lark-cli text send failed (exit %d): %s" % (result.returncode, result.stderr.strip()))
        return False

    text_ok = False
    try:
        resp = json.loads(result.stdout)
        text_ok = resp.get("ok", False)
        if not text_ok:
            warn("lark-cli returned non-ok: %s" % result.stdout.strip()[:200])
    except json.JSONDecodeError:
        warn("lark-cli output was not JSON: %s" % result.stdout.strip()[:200])

    # Step 2: Send image if available
    img_ok = False
    if image_path and Path(image_path).exists():
        cmd_img = [
            "lark-cli", "im", "+messages-send",
            "--user-id", LARK_USER_ID,
            "--as", "user",
            "--image", image_path,
        ]
        try:
            result_img = subprocess.run(cmd_img, capture_output=True, text=True, timeout=120, env=lark_env)
        except subprocess.TimeoutExpired:
            warn("lark-cli image send timed out after 120s")
        else:
            if result_img.returncode == 0:
                try:
                    resp_img = json.loads(result_img.stdout)
                    img_ok = resp_img.get("ok", False)
                except json.JSONDecodeError:
                    pass
            if not img_ok:
                warn("lark-cli image send failed: %s" % result_img.stderr.strip()[:200])

    return text_ok


def main() -> int:
    args = parse_args()
    date_str = target_date(args.date)

    journal_path = Path(args.journal_root) / "daily" / ("%s.md" % date_str)
    posters_dir = Path(args.journal_root) / "posters"
    output_path = posters_dir / ("%s-prompt.md" % date_str)
    image_path = posters_dir / ("%s-poster.png" % date_str)

    if not journal_path.exists():
        warn("Daily journal not found: %s (skipping poster step)" % journal_path)
        return 0

    if output_path.exists() and image_path.exists() and not args.force:
        print("Poster prompt + image already exist: %s (skipping)" % output_path)
        return 0

    # Step 1: Generate poster prompt via chat completion
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

    # Save prompt file
    posters_dir.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text(prompt_text + "\n", encoding="utf-8")
        print("Wrote poster prompt: %s" % output_path)
    except OSError as exc:
        warn("Failed to write poster prompt: %s" % exc)
        return 0

    # Step 2: Extract sections
    recap_text = extract_recap(prompt_text)
    final_prompt = extract_final_prompt(prompt_text)

    if not recap_text:
        warn("Could not extract 今日纪要 from prompt; using full prompt as recap")
        recap_text = prompt_text

    # Step 3: Generate image via OpenAI image API
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not final_prompt:
        warn("Could not extract 最终 Prompt; skipping image generation")
    elif not api_key:
        warn("OPENAI_API_KEY not set; skipping image generation")
    elif not image_path.exists() or args.force:
        print("Generating poster image via OpenAI...")
        try:
            img_bytes = call_openai_image(final_prompt, api_key)
            image_path.write_bytes(img_bytes)
            print("Saved poster image: %s (%d KB)" % (image_path, len(img_bytes) // 1024))
        except Exception as exc:
            warn("Image generation failed: %s (non-blocking)" % exc)
    else:
        print("Poster image already exists: %s" % image_path)

    # Step 4: Send recap text + image to Lark
    if args.skip_lark:
        print("Lark send skipped (--skip-lark).")
        return 0

    img_file = str(image_path) if image_path.exists() else None
    print("Sending to Lark DM (user_id=%s)..." % LARK_USER_ID)
    if send_to_lark(recap_text, date_str, img_file):
        print("Lark send: OK")
    else:
        print("Lark send: failed (non-blocking, prompt file still saved)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
