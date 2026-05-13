# AI Thinking Journal — 產品規格書

> **用途**：交給 Claude Code 進行技術規劃和實現的完整產品定義。
> **不是 MVP**：這是最終產品形態，Claude Code 自行決定分階段實現順序。

---

## 一句話定義

一個自動化 pipeline，每天從 Claude Code 和 Codex CLI 的本地對話記錄中提取數據，生成結構化的「思考日記」，並按週/月自動彙整，最終形成一份可被 AI 讀取、可被人類翻閱的個人思考檔案。

---

## 數據源

### Claude Code

**存放位置**：`~/.claude/projects/` 下的 JSONL 文件

**提取字段**：

| 字段 | 提取方式 | 用途 |
|------|----------|------|
| `timestamp` | 直接取 | 時間軸、篩選今日 |
| `type` (user/assistant) | 直接取 | 角色標識 |
| `message.content` | text block 拼接（見下方邏輯） | 對話內容 |
| `tool_use.name` | 從 content blocks 中 type=tool_use 的提取 name | 工具使用統計 |
| `sessionId` | 每條消息都取 | session 分組 |
| `cwd` | 每條消息都取 | 項目識別 |
| `gitBranch` | 如有則取 | 工作分支上下文 |

### Codex CLI

**存放位置**：`~/.codex/` 下的對話日誌

**提取字段**：

| 字段 | 提取方式 | 用途 |
|------|----------|------|
| `timestamp` | 從 session_meta 或消息推斷 | 時間軸 |
| `role` (user/assistant/developer) | 直接取 | 角色標識 |
| `content[].text` | text block 拼接 | 對話內容 |
| `function_call.name` | 直接取 | 工具使用統計 |
| `reasoning.summary` | 直接取 | Codex 推理摘要，作為摘要素材 |
| `session_meta.id` | 直接取 | session 分組 |
| `session_meta.cwd` | 直接取 | 項目識別 |
| `session_meta.git` | 如有則取 | 分支上下文 |

### 明確不取的字段

| 字段 | 不取原因 |
|------|----------|
| `tool_result` / `function_call_output` | 輸出太長，噪音遠大於信號 |
| `tool_use.input` | 參數細節對摘要無幫助 |
| `web_search_call` | 價值低，增加處理複雜度 |
| `parentUuid` / `isSidechain` | 對話樹結構對 daily summary 無用 |
| `permissionMode` / `version` | 系統配置，不反映工作內容 |
| `error` | 偶發，不值得專門處理 |
| `event_msg` / `turn_context` | 粒度太細 |

---

## Content 提取邏輯

```
if content is string:
    text = content
elif content is list:
    text_blocks = [block.text for block in content if block.type == "text"]
    text = "\n".join(text_blocks)
    
    tool_names = [block.name for block in content if block.type == "tool_use"]
    # tool_names 單獨記錄，不混入 text
```

---

## 過濾邏輯

只有一種模式（不再區分 smart/full/raw）：

```
User 消息：
  - 全部保留完整內容

Assistant 消息：
  - 保留首段 + 末段（首段通常是分析思路，末段是結論）
  - 如果只有一段，完整保留
  - 段的定義：以連續兩個換行符分隔的文本塊

過濾掉的噪音：
  - <system-reminder> 開頭的消息
  - <task-notification> 開頭的消息
  - 純 tool_result 沒有 text 的消息

Codex developer 消息：
  - 只提取 skills 列表和 plugins 列表名稱，丟棄其他內容
```

---

## 輸出體系

### 層級結構

```
obsidian-vault/
└── ai-journal/
    ├── daily/
    │   ├── 2026-05-14.md
    │   ├── 2026-05-15.md
    │   └── ...
    ├── weekly/
    │   ├── 2026-W20.md
    │   └── ...
    └── monthly/
        ├── 2026-05.md
        └── ...
```

### Daily — 每日思考日記

**觸發**：每天 00:00 (cron)
**輸入**：當天所有 Claude Code + Codex 對話
**處理**：兩步 — 先提取原始數據，再餵 LLM 生成摘要

#### 文件格式

```markdown
---
date: "2026-05-14"
type: daily
weekday: Wednesday
tools_used:
  claude_code:
    sessions: 3
    messages: {user: 28, assistant: 26}
    tools: {Edit: 12, Bash: 5, mcp__supabase__execute_sql: 2, Read: 8}
  codex:
    sessions: 2
    messages: {user: 15, assistant: 14}
    tools: {exec_command: 8, web_search: 1}
projects_touched:
  - {name: "shopee-extension", source: "claude_code", sessions: 2}
  - {name: "bazi-app", source: "codex", sessions: 1}
  - {name: "n8n-automation", source: "claude_code", sessions: 1}
total_duration_estimate_min: 180
---

# 2026-05-14 Wednesday

## 今日主題

- Shopee AI Reply Assistant 的 content script injection 邏輯重構
- BaZi App 的 quiz flow 狀態管理
- n8n Shopee 廣告自動化 workflow 的異常處理

## 關鍵決策

- 決定 extension 改用 shadow DOM 隔離樣式，避免與蝦皮頁面衝突
- BaZi quiz 放棄 multi-step form，改用單頁滾動式，減少跳出率

## 待辦事項

- [ ] Extension: 測試 shadow DOM 在 Shopee 商品頁的相容性
- [ ] BaZi: 完成 quiz result → payment gate 的跳轉邏輯
- [ ] n8n: 補上廣告 API rate limit 的 retry 機制

## 思考亮點

- 發現 Shopee 的 CSP 政策會擋 inline script，這解釋了之前 injection 失敗的原因
- 八字五行的「過量」概念可以用進度條 UI 直覺化呈現，比數字更易理解

## 工具使用觀察

- Claude Code 主要用於 extension 的探索性開發（大量 Read + Edit）
- Codex 用於 BaZi app 的結構化任務（密集 exec_command）
- 今天在 Claude Code 中切換了 3 次 git branch，說明 extension 開發涉及多個功能分支

## 原始對話索引

### Claude Code

#### Session: shopee-extension (14:02 - 16:45)
- 討論了 content script 的 injection timing
- 重構了 shadow DOM wrapper
- 測試了 3 種 CSS 隔離方案

#### Session: shopee-extension (17:30 - 18:15)
- 修復了 message passing 的 race condition

#### Session: n8n-automation (21:00 - 22:30)
- 分析了廣告 API 的 rate limit 模式
- 寫了 exponential backoff 邏輯

### Codex

#### Session: bazi-app (19:00 - 20:40)
- 實現了 quiz flow 的狀態管理
- 生成了 60 個測試用的八字組合
```

#### YAML Metadata 規格說明

`tools_used` 中的 key 是工具名稱原值：
- Claude Code: 取 `tool_use.name`（如 `Edit`, `Bash`, `Read`, `mcp__supabase__execute_sql`）
- Codex: 取 `function_call.name`（如 `exec_command`, `web_search`）

`projects_touched` 的 `name` 取 `cwd` 的最後一層目錄名。

`total_duration_estimate_min` = 最後一條消息的 timestamp - 第一條消息的 timestamp，取分鐘，跨 session 累加，不是精確工時但足夠做趨勢分析。

#### LLM Summary Prompt

```
You are a thinking journal analyst for a solo entrepreneur who builds
e-commerce businesses and AI automation tools.

Given:
1. Raw conversation transcripts from today (between <conversations> tags)
2. Tool usage statistics (between <stats> tags)

Produce a daily thinking journal entry.

<rules>
- Write in the SAME LANGUAGE as the dominant language in transcripts
- Each bullet: one sentence max, concrete and specific
- Extract REAL decisions and todos — never invent
- If a section has nothing: write "無"
- Do NOT output YAML frontmatter or the date title — those are handled separately
- The "工具使用觀察" section should note patterns in HOW different tools
  were used (exploration vs execution, which tool for which type of thinking),
  NOT just list what tools were called
- The "原始對話索引" section should be a concise index, not a transcript.
  For each session: 2-4 bullet points summarizing what happened, nothing more.
</rules>

<sections>
## 今日主題
## 關鍵決策
## 待辦事項
## 思考亮點
## 工具使用觀察
## 原始對話索引
</sections>

<stats>
{{TOOL_STATS_JSON}}
</stats>

<conversations>
{{FILTERED_CONVERSATIONS}}
</conversations>
```

---

### Weekly — 每週思考週刊

**觸發**：每週一 00:30
**輸入**：過去 7 天的 daily markdown 文件（完整內容，含 YAML）
**處理**：讀取 7 個 daily 文件 → 餵 LLM 生成週刊

#### 文件格式

```markdown
---
date_range: "2026-05-11 ~ 2026-05-17"
type: weekly
week: "2026-W20"
total_sessions: {claude_code: 18, codex: 9}
total_messages: {user: 210, assistant: 195}
top_projects:
  - {name: "shopee-extension", sessions: 8}
  - {name: "bazi-app", sessions: 6}
  - {name: "n8n-automation", sessions: 4}
top_tools:
  - {name: "Edit", count: 89}
  - {name: "exec_command", count: 45}
  - {name: "Bash", count: 32}
---

# 2026-W20 週刊

## 本週三大推進

1. Shopee AI Reply Assistant 完成了 shadow DOM 架構，進入功能測試階段
2. BaZi App 的 quiz flow 基本成型，剩 payment gate 對接
3. n8n 廣告自動化加上了完整的錯誤處理和 retry 機制

## 未解決的問題

- Extension 在 Shopee 聊聊頁面的 DOM 結構不穩定，MutationObserver 策略需要重新設計
- BaZi quiz 的題目順序對轉化率的影響還沒有數據驗證

## 本週決策回顧

- [好決策] shadow DOM 隔離方案確實解決了樣式衝突，省去了大量 debug 時間
- [待驗證] 單頁滾動式 quiz 是否真的比 multi-step 好，需要 A/B 測試

## 工具使用趨勢

- 本週 Claude Code 偏重探索性開發（Read/Edit 比例高）
- Codex 偏重執行性任務（exec_command 密集）
- 週三開始 MCP 工具使用量增加，說明 Supabase 整合進入實作階段

## 下週最重要的一件事

[由 LLM 根據本週待辦和未解決問題推斷]
```

#### LLM Summary Prompt

```
You are a weekly review analyst for a solo entrepreneur.

Given 7 daily thinking journal entries (between <daily_entries> tags),
produce a weekly review that captures the arc of the week.

<rules>
- Write in the same language as the daily entries
- Focus on PROGRESS and PATTERNS, not activity lists
- "本週三大推進" = the 3 things that moved the needle most
- "未解決的問題" = things that are stuck or need rethinking
- "決策回顧" = look back at decisions made this week,
  tag each as [好決策] [待驗證] or [值得反思]
- "工具使用趨勢" = patterns across the week, not daily stats
- "下週最重要的一件事" = based on momentum and blockers,
  what single thing would have the highest impact
- Be honest. If a week was scattered, say so.
</rules>

<daily_entries>
{{ALL_DAILY_MDS_CONCATENATED}}
</daily_entries>
```

---

### Monthly — 每月思考月報

**觸發**：每月 1 日 01:00
**輸入**：過去一個月的所有 weekly markdown 文件 + 當月所有 daily 的 YAML metadata（不含正文）
**處理**：讀取 weekly 文件 + daily YAML → 餵 LLM 生成月報

#### 文件格式

```markdown
---
date_range: "2026-05-01 ~ 2026-05-31"
type: monthly
month: "2026-05"
total_sessions: {claude_code: 72, codex: 35}
total_messages: {user: 840, assistant: 790}
active_days: 26
top_projects:
  - {name: "shopee-extension", sessions: 30, trend: "↑"}
  - {name: "bazi-app", sessions: 22, trend: "→"}
  - {name: "n8n-automation", sessions: 15, trend: "↓"}
tool_usage_trend:
  week1: {Edit: 65, Bash: 20, exec_command: 30}
  week2: {Edit: 89, Bash: 32, exec_command: 45}
  week3: {Edit: 70, Bash: 28, exec_command: 38}
  week4: {Edit: 55, Bash: 15, exec_command: 22}
---

# 2026-05 月報

## 本月覆盤

[2-3 段文字，回顧整個月的主線劇情]

## 項目進展地圖

| 項目 | 月初狀態 | 月末狀態 | 關鍵里程碑 |
|------|----------|----------|------------|
| shopee-extension | PRD 階段 | 功能測試中 | shadow DOM 架構完成 |
| bazi-app | quiz 設計 | quiz + payment 基本完成 | 60-day roadmap 啟動 |
| n8n-automation | 有 bug | 穩定運行 | retry 機制上線 |

## 決策品質回顧

- 本月做了 N 個關鍵決策，其中 X 個被驗證為好決策，Y 個待驗證，Z 個值得反思
- [具體列出值得反思的決策]

## AI 工具使用演變

- Claude Code vs Codex 的使用比例變化
- 是否出現了新的使用模式或偏好轉移
- 哪些類型的任務逐漸固定在某個工具上

## 下月關注重點

[基於趨勢和未完成事項的建議]
```

#### LLM Summary Prompt

```
You are a monthly review analyst for a solo entrepreneur.

Given:
1. Weekly reviews from this month (between <weekly_reviews> tags)
2. Aggregated YAML metadata from all daily entries (between <monthly_stats> tags)

Produce a monthly review that captures the narrative arc of the month.

<rules>
- Write in the same language as the weekly reviews
- "本月覆盤" should read like a story — what was the month's narrative?
- "項目進展地圖" = concrete before/after comparison, not vague progress
- "決策品質回顧" = aggregate the [好決策][待驗證][值得反思] tags from weeklies
- "AI 工具使用演變" = look at tool_usage_trend in stats,
  identify shifts and what they mean about work patterns
- Be reflective. This is for the person to read months later
  and understand who they were and what they were thinking.
</rules>

<monthly_stats>
{{AGGREGATED_YAML_STATS}}
</monthly_stats>

<weekly_reviews>
{{ALL_WEEKLY_MDS_CONCATENATED}}
</weekly_reviews>
```

---

## 自動化架構

```
每日 00:00 (cron)
│
├─ 1. extract.py
│    ├─ 讀取 ~/.claude/projects/ 下今天修改的 JSONL
│    ├─ 讀取 ~/.codex/ 下今天的對話日誌
│    ├─ 按上述邏輯提取字段、過濾、統計
│    └─ 輸出: filtered_conversations.md + stats.json
│
├─ 2. summarize.py
│    ├─ 讀取 filtered_conversations.md + stats.json
│    ├─ 組裝 daily summary prompt
│    ├─ 調用本地 Ollama (qwen3-coder) 生成摘要
│    ├─ 組裝 YAML frontmatter + LLM 輸出
│    └─ 輸出: ai-journal/daily/YYYY-MM-DD.md
│
├─ 3. (可選) git push
│    └─ cd ai-journal && git add . && git commit && git push
│
每週一 00:30 (cron)
│
├─ 4. weekly.py
│    ├─ 讀取過去 7 天的 daily/*.md
│    ├─ 拼接後餵 LLM
│    └─ 輸出: ai-journal/weekly/YYYY-WNN.md
│
每月 1 日 01:00 (cron)
│
└─ 5. monthly.py
     ├─ 讀取當月所有 weekly/*.md
     ├─ 提取當月所有 daily/*.md 的 YAML（只要 metadata，不要正文）
     ├─ 拼接後餵 LLM
     └─ 輸出: ai-journal/monthly/YYYY-MM.md
```

**技術選擇**：
- 語言：Python（處理 JSON/YAML 最方便）
- LLM：本地 Ollama（qwen3-coder 或同級別，262K context）
- 定時：cron（macOS 用 launchd 也行）
- 存儲：本地 Obsidian vault，可選 git sync

---

## Obsidian 整合要點

YAML frontmatter 的設計已經考慮了 Dataview 查詢，以下是幾個可直接使用的查詢：

```dataview
// 本週每天的 session 數量
TABLE tools_used.claude_code.sessions AS "CC Sessions",
      tools_used.codex.sessions AS "Codex Sessions"
FROM "ai-journal/daily"
WHERE date >= date(today) - dur(7 days)
SORT date DESC

// 哪個項目本月最活躍
FLATTEN projects_touched AS p
WHERE type = "daily" AND month = "2026-05"
GROUP BY p.name
SORT length(rows) DESC

// 所有待驗證的決策（來自週刊）
LIST
FROM "ai-journal/weekly"
WHERE contains(file.content, "待驗證")
```

---

## 設計原則

1. **數據提取和摘要生成嚴格分離** — extract.py 只做結構化提取，summarize.py 只做 LLM 調用。中間用文件交接。這樣任何一步壞了都能單獨 debug。

2. **YAML metadata 是一等公民** — metadata 不是裝飾，是這個系統的長期價值核心。日記正文會過時，但 metadata 能做跨月跨年的趨勢分析。

3. **摘要 prompt 保持穩定** — prompt 定了就不要頻繁改，否則不同時期的日記風格不一致，日後對比分析會很困難。如果要改，記錄版本號。

4. **寧可少取不要多取** — 每多一個字段就多一個維護點。上面列的已經是精簡過的，不要再加了，除非有非常明確的分析需求。

5. **所有輸出都是 markdown** — 不引入數據庫、不引入 web UI。markdown 是最持久的格式，10 年後還能讀。Obsidian 是查看層，不是存儲層。
