#!/usr/bin/env python3
"""
Task 02: Summarization Engine
Reads extracted daily thinking log and generates a structured summary
using local Ollama API.

Usage:
    python3 02_summarize.py                    # summarize today
    python3 02_summarize.py --date 2026-05-14  # summarize specific date
    python3 02_summarize.py --model llama3:latest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ_BEIJING = timezone(timedelta(hours=8))

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3:latest"


def build_prompt(extracted_text: str, date_str: str) -> str:
    return (
        "You are a thinking journal analyst. Given raw AI conversation transcripts "
        "from one day, produce a structured daily summary.\n\n"
        "Write the summary in the SAME LANGUAGE as the transcripts. "
        "If the transcripts are mostly Chinese, write the summary in Chinese. "
        "If mostly English, write in English. If mixed, use the dominant language.\n\n"
        "Output format — use these exact section headers, fill with REAL content:\n\n"
        "## 今日主题 / Today's Themes\n"
        "Write each theme as a dash, colon, and one-line description. Example:\n"
        "- API 调研: 研究了 Ollama 本地 API 的调用方式\n\n"
        "## 关键决策 / Key Decisions\n"
        "Each decision as a dash, colon, and reasoning. Example:\n"
        "- 使用本地 Ollama 而非云端 API: 零成本且数据不出本机\n\n"
        "## 待办事项 / Action Items\n"
        "Only list PENDING or MENTIONED-FUTURE todos, not completed work. Example:\n"
        "- [ ] 添加 launchd 定时任务实现每晚自动运行\n\n"
        "## 思考亮点 / Thinking Highlights\n"
        "Non-obvious insights or reasoning patterns from the conversations. Example:\n"
        "- 从 JSONL 的 cwd 字段获取项目名比解码目录名更可靠\n\n"
        "## 涉及项目 / Projects Touched\n"
        "Project name, colon, what was done. Example:\n"
        "- daily-thinking-summary: 完成了数据提取脚本的开发和测试\n\n"
        "Rules:\n"
        "- Be concise — each bullet one sentence max\n"
        "- Extract REAL decisions and todos from the conversation, don't invent them\n"
        "- If a section has nothing to report, write '无 / None'\n"
        "- Do NOT include a YAML frontmatter or title — just the sections above\n\n"
        f"Date: {date_str}\n\n"
        f"Conversation transcripts:\n\n{extracted_text}"
    )


def call_ollama(prompt: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    content = data["message"]["content"].strip()

    # Strip <think>...</think> blocks (some models emit chain-of-thought)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    return content


def build_frontmatter(date_str: str, model: str, input_tokens: int) -> str:
    now = datetime.now(TZ_BEIJING).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    return (
        "---\n"
        f"date: {date_str}\n"
        f"generated: {now}\n"
        f"model: {model}\n"
        f"input_tokens_approx: {input_tokens}\n"
        "type: daily-summary\n"
        "---\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Summarize daily thinking log via Ollama")
    parser.add_argument(
        "--date",
        default=None,
        help="Date to summarize (YYYY-MM-DD). Default: today in Beijing time.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("SUMMARY_MODEL", DEFAULT_MODEL),
        help=f"Ollama model to use (default: {DEFAULT_MODEL}, or SUMMARY_MODEL env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the prompt without calling Ollama",
    )
    args = parser.parse_args()

    # Resolve date
    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now(TZ_BEIJING).strftime("%Y-%m-%d")

    # Paths
    output_dir = Path(__file__).parent.parent / "output"
    input_file = output_dir / f"{date_str}-daily-thinking.md"
    output_file = output_dir / f"{date_str}-summary.md"

    if not input_file.exists():
        print(f"Error: {input_file} not found", file=sys.stderr)
        print("Run 01_extract.py first to generate the daily thinking log.", file=sys.stderr)
        sys.exit(1)

    extracted_text = input_file.read_text(encoding="utf-8")
    input_tokens = len(extracted_text) // 4  # rough estimate

    print(f"Input: {input_file} ({len(extracted_text):,} chars, ~{input_tokens:,} tokens)")
    print(f"Model: {args.model}")

    prompt = build_prompt(extracted_text, date_str)

    if args.dry_run:
        print("\n--- Prompt ---\n")
        print(prompt)
        print("\n--- End Prompt ---")
        sys.exit(0)

    # Verify Ollama is reachable
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception as e:
        print(f"Error: Cannot reach Ollama at {OLLAMA_URL}", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print("Make sure Ollama is running: ollama serve", file=sys.stderr)
        sys.exit(1)

    print("Calling Ollama... (may take 30-60s)")
    summary = call_ollama(prompt, args.model)

    # Build output
    frontmatter = build_frontmatter(date_str, args.model, input_tokens)
    output_content = frontmatter + "\n" + summary + "\n"

    output_file.write_text(output_content, encoding="utf-8")
    print(f"\nOutput written to: {output_file}")
    print(f"Summary length: {len(summary):,} chars")


if __name__ == "__main__":
    main()
