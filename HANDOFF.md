# HANDOFF — Signal Pipeline + Poster Style + launchd Shipping

## 本次完成了什么（commit 6d83b93）

给 `01_extract.py` 加了 `--signal-only` 模式。效果：

| 指标 | 改前（full extract） | 改后（signal-only） |
|---|---|---|
| 5/19 输出体积 | 207K chars | 106K chars（51%） |
| 人话密度 | <1% | >80% |
| 需要 LLM 调用 | 20+ 次 | 1 次或 0 次 |
| Codex 支持 | 混在噪音里 | 单独一节，含 agent 文字 |

信号内容：away_summary、ai-title、last-prompt、user text。Codex 的 AGENTS.md bootstrap 和 environment_context 已过滤。

5/19 的 diary-preview 在 `output/2026-05-19/diary-preview.md`（git-ignored），质量确认 OK。

---

## 下一个 agent 的 3 个任务

### Task 1: 改 03_summarize.py — 直接吃 signal 数据

**目标**：跳过 Step 02（每 session 一次 API 调用），让 Step 03 直接读 `signal_conversations.md`。

**具体改动**：
- `03_summarize.py` 的 `build_prompt()` 目前读 `session_summaries.md`（来自 Step 02）
- 改成读 `signal_conversations.md`（来自 Step 01 的 --signal-only 输出）
- prompt 可能需要微调：输入格式从"每个 session 的 3-5 条 bullets"变成了"按项目分组的信号数据"
- Step 02 可以保留但不再必须运行

**参考文件**：
- `scripts/03_summarize.py` — 当前 prompt 在 `build_prompt()` 函数
- `scripts/04_daily_pipeline.py` — 编排脚本，需要加 `--signal-only` 参数传递
- `output/2026-05-19/signal_conversations.md` — 信号数据样本

### Task 2: 调 poster 风格 — 去掉 chibi，换成熟设计

**问题**：当前 2026-05-19 的 poster prompt 用 Manga/Comic chibi 风格，太卡哇伊，颜色对比度不够。

**目标**：换成 flat illustration 或 infographic 风格，保持信息密度。

**参考**：
- `ai-journal/posters/2026-05-19-prompt.md` — 当前 prompt，内容 OK 但风格要换
- `ai-journal/posters/POSTER_WORKFLOW.md` — poster 工作流定义
- `ai-journal/posters/2026-05-17-prompt.md` — 之前的 prompt 格式参考

**具体要求**：
- 风格从 chibi manga 改成 flat illustration 或 infographic
- 颜色对比度加强，面板边框用更深的色
- 保持 2x3 网格布局（六个项目各占一个面板）
- 保持信息密度（数字、项目名、关键动作都要能读到）
- 重新生成图片确认效果

### Task 3: launchd 最终 shipping

**背景**：launchd plist 在本地磁盘（`~/Library/LaunchAgents/`），不在外置硬盘。

**当前状态**：
- `scripts/run_pipeline.sh` — launchd wrapper，处理前一天的日期
- `launchd/com.pohanlee.daily-thinking-summary.plist` — plist 模板
- 需要确认路径指向本地磁盘（不是外置硬盘 `/Volumes/...`）
- 需要确认 `--signal-only` 参数已加入 pipeline 流程

**具体检查**：
1. 读 `scripts/run_pipeline.sh`，确认它传了 `--signal-only` 给 01_extract.py
2. 检查 `~/Library/LaunchAgents/` 下有没有 plist 文件
3. 确认 plist 中的路径是本地磁盘路径
4. 测试 `launchctl load` 能否正常加载
5. 跑一次 dry-run 确认 pipeline 能端到端执行
6. 确认 `.env` 里的 `OPENAI_API_KEY` 能被 launchd 读到

**注意**：
- launchd 环境变量和 .env 载入是之前反复出问题的地方，用绝对路径
- 测试时先用 `--dry-run` 确认不报错，再实际跑
- Host python3 是 3.8.1，所有代码要兼容

---

## Pipeline Flow（当前）

```
01_extract.py --signal-only  → output/YYYY-MM-DD/signal_conversations.md + stats.json
02_session_summarize.py      → output/YYYY-MM-DD/session_summaries.md（可选，不再必须）
03_summarize.py              → ai-journal/daily/YYYY-MM-DD.md
04_daily_pipeline.py         → orchestrator (runs 01→02→03, idempotent)
07_daily_poster.py           → ai-journal/posters/YYYY-MM-DD-prompt.md + Lark DM
run_pipeline.sh              → launchd wrapper (daily + conditional weekly/monthly + poster)
```

## File Inventory

```
scripts/01_extract.py              — extraction (--signal-only 模式新增)
scripts/02_session_summarize.py    — per-session LLM summaries（Task 1 后不再必须）
scripts/03_summarize.py            — daily journal generation（Task 1 需要改）
scripts/04_daily_pipeline.py       — orchestrator
scripts/05_weekly.py               — weekly rollup
scripts/06_monthly.py              — monthly rollup
scripts/07_daily_poster.py         — poster prompt → OpenAI → Lark DM
scripts/run_pipeline.sh            — launchd wrapper
launchd/com.pohanlee.daily-thinking-summary.plist — macOS scheduling
ai-journal/daily/*.md              — daily journals
ai-journal/posters/                — poster prompts + generated covers
output/                            — extraction artifacts (git-ignored)
```

## Known Caveats

- Host python3 是 3.8.1，所有代码要兼容
- output/ 和 logs/ 是 git-ignored
- launchd 在 Mac 睡眠时不跑，wake 后补跑
- .env 有 OPENAI_API_KEY，不要 commit
