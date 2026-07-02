# feat-447-M12 — Progress

## Startup

- Context: M12 starts from `origin/unit/feat-447` after M10/M11 are merged. Scope is restricted to Feishu mention parsing, external group context parity, config/channel diagnostic warnings, and focused tests.
- Decision: Split into R1 mention parsing/metadata, R2 external group buffer/drain, R3 diagnostic warning plus live/non-e2e verification.
- Rationale: These roadpoints map directly to the three failure modes in design.md: deleted mention content, disconnected group buffer identity, and platform configs that only deliver @Bot events.
- Evidence:
  - Baseline: `pytest -m "not e2e"` -> 3250 passed, 1 skipped, 22 deselected, 20 warnings in 155.21s.
  - Read context: `spec.md`, `design.md`, `AGENTS.md`, `LOGBOOK.md`, `docs/TESTING_GUIDE.md`, current Feishu/Pipeline code and tests.

## R1 — Mention 正文保真与结构化 metadata

- Context: Feishu 原始 text 用 `@_user_N` placeholder 表示 mention。旧实现把 placeholder 从正文删除，导致 `@bot hi` 只剩 `hi`，纯 `@bot` 变成空串，`@所有人` 也丢失用户可见内容。
- Decision: `FeishuClient` 将 placeholder 规范化为用户可见 `@DisplayName`/`@所有人`，并在 `FeishuMessageEvent` 上保留 `raw_text` 与 `mention_only`；`FeishuAdapter` 透传 `raw_text`/`mention_only`，并继续只用结构化 `mentions.open_id == botOpenId` 写入 `mentioned_agent_ids`。
- Rationale: mention 是用户消息正文的一部分，IM 展示、GroupContextStore 和 LLM current message 必须使用同一份可见文本；触发判断则使用结构化 metadata，避免 `@所有人` 或其他人的 @ 被当成 Bot 触发。
- Evidence:
  - Tests: `pytest -q tests/unit/test_feishu_client.py tests/unit/test_feishu_adapter.py` -> 37 passed in 2.28s.
  - Entry: Unit-level Feishu event parse/adapter delivery boundary; R3 记录真实 Feishu live-critical 入口。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: Regression tests in `tests/unit/test_feishu_client.py` cover `@bot hi` not deleting @, mention-only non-empty text, and `@所有人` visible text; `tests/unit/test_feishu_adapter.py` covers `mention_only` and `mentioned_agent_ids` metadata.
  - Visual/Interaction: N/A
- Rollback: Revert C2 `16ea5540` and C1 `87704611` if mention preservation must be removed.
- Commits: C1=87704611, C2=16ea5540, C3=TODO
- Next: R2

## R2 — External group buffer key 与纯 @ drain

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R3

## R3 — 普通群消息投递能力 warning/health 诊断与收尾验收

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
  - Live Critical: TODO
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: Milestone complete
