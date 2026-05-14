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
- Decision: 按设计完成迁移，新增 `build_chat_messages` 和 `estimate_llm_context_tokens`
- Rationale: 解除 loop 对 runtime 的循环依赖，为 loop 内 compact 做准备
- Evidence:
  - Tests: `test_agent_prompting.py` 全绿（11 passed），`test_loop_retry.py` 全绿（5 passed），`test_compaction_planner.py` 全绿（3 passed）
  - Entry: N/A（纯内部重构，无用户入口变更）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert a4ffe545`
- Commits: C1=1220cf1f, C2=a4ffe545 (R1-R3 合并提交)
- Next: R2

## R2 — loop.py 新增 compact 能力

- Context: loop 内部需要 token 检查 + compact 触发，system prompt 分离
- Decision: AgentLoop.__init__ 注入 compact 组件；run() 内分离 rendered_system_prompt 和 llm_messages；while True 开头检查 token 并触发 compact；compact 后 yield summary msg 并继续 iteration
- Rationale: 与 CC query.ts 架构一致，compact 后继续当前 turn 不中断
- Evidence:
  - Tests: `test_loop_compact.py` 全绿（4 passed）：token 超限触发、iteration 继续、history 不变性、system prompt 保留
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert a4ffe545`
- Commits: C1=1220cf1f, C2=a4ffe545
- Next: R3

## R3 — runtime.py 移除 preflight + 消费 compact_boundary

- Context: runtime 不再做 preflight compact，改为 loop 内部触发；runtime 消费 summary msg 时写 compact_boundary
- Decision: 移除 `_preflight_compaction` 调用和 `_post_turn_check_overflow` 死代码；消费 msg 时检测 `is_compact_summary` 并写 `compact_boundary` entry；`_compact_session` 保留供 public `compact()` API
- Rationale: 与 design.md 决策 2（compact 与 JSONL 写入解耦）一致
- Evidence:
  - Tests: `test_runtime_compact_boundary.py` 全绿（1 passed）：runtime 消费 summary msg 时正确写 compact_boundary
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert a4ffe545`
- Commits: C1=1220cf1f, C2=a4ffe545
- Next: R4

## R4 — 回归测试 + 文档

- Context: 确保所有相关测试全绿，无回归
- Decision: 跑全量相关测试 + 更新 progress.md
- Rationale: 验证实现不破坏现有功能
- Evidence:
  - Tests: `pytest tests/unit/test_loop_compact.py tests/unit/test_agent_prompting.py tests/unit/test_loop_retry.py tests/unit/test_compaction_planner.py tests/unit/test_agent_runtime.py tests/unit/test_runtime_compact_boundary.py -q` = 31 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: `git revert a4ffe545`
- Commits: C3=本提交
- Next: 本 milestone 已完成
