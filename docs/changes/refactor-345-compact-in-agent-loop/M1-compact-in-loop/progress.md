# refactor-345-M1 — Progress

<!--
每个 roadpoint 完成后实时追加。一个 roadpoint 一段。
重点记"为什么这么决定"和"凭什么相信改对了"，不重复代码本身。

【硬约束：Pause-on-design-issue】
实现期发现 design 偏差时，禁止悄悄绕过。worker 必须：
1. 立即暂停编码
2. 在本文加一段 [Design 修订] R<n>: X → Y（现状 / 新方案 / 原因）
3. 同步改 ../../design.md 正文；若影响后续 milestone，再追加 design.md 顶部 Changelog
4. 通知人/orchestrator 确认后再继续

phase-locked 不重要，知识同步重要。
-->

## R1 — 前置迁移与 prompting 拆分

- Context: design.md 要求前置迁移 `_message_from_turn_entry`、`_read_file_slice`，并拆分 `build_prompt_messages`
- Decision: 按设计完成迁移，新增 `build_chat_messages` 和 `_estimate_llm_context_tokens`
- Rationale: 解除 loop 对 runtime 的循环依赖，为 loop 内 compact 做准备
- Evidence:
  - Tests: 待补充
  - Entry: N/A（纯内部重构，无用户入口变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 待补充
- Commits: 待补充
- Next: R2

## R2 — loop.py 新增 compact 能力

- Context: 待补充
- Decision: 待补充
- Rationale: 待补充
- Evidence:
  - Tests: 待补充
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 待补充
- Commits: 待补充
- Next: R3

## R3 — runtime.py 移除 preflight + 消费 compact_boundary

- Context: 待补充
- Decision: 待补充
- Rationale: 待补充
- Evidence:
  - Tests: 待补充
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 待补充
- Commits: 待补充
- Next: R4

## R4 — 回归测试 + 文档

- Context: 待补充
- Decision: 待补充
- Rationale: 待补充
- Evidence:
  - Tests: 待补充
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 待补充
- Commits: 待补充
- Next: 本 milestone 已完成
