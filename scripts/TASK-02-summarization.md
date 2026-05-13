# Task 02: Summarization Engine

**Goal**: Use Claude API to compress extracted daily conversations into a structured thinking summary.

**Status**: Blocked by Task 01

## Prompt Design

```
You are a thinking journal analyst. Given raw AI conversation transcripts from one day,
produce a structured daily summary.

Input: [extracted text from Task 01]

Output format:
## Today's Themes
- [topic 1]: [one-line description]
- [topic 2]: ...

## Key Decisions Made
- [decision]: [context and reasoning]

## Action Items / Todos
- [ ] [todo from conversation]

## Thinking Highlights
- [insight or non-obvious reasoning pattern]

## Projects Touched
- [project name]: [what was done]
```

## Batching Strategy

If daily content exceeds 100K tokens:
1. Summarize each session individually (per-session prompt)
2. Merge session summaries into daily digest (aggregate prompt)

## Cost Estimate

- Haiku: ~$0.05–0.20/day (recommended for MVP)
- Sonnet: ~$0.50–2.00/day (better quality)
- Batch API: 50% discount if not time-sensitive

## Acceptance Criteria

- [ ] Summary captures main topics from each session
- [ ] Decisions and todos are accurately extracted
- [ ] Output is Obsidian-compatible markdown with YAML frontmatter
- [ ] Token limits handled via batching
