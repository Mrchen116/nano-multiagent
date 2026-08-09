# bugfix-520-M2 — Progress

## Baseline

- Context: 从 `origin/unit/bugfix-520` 创建独立 milestone worktree，并完成 Full worker 的上下文读取和基线门禁。
- Evidence:
  - Tests: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/test_core_errors.py tests/unit/test_loop_compact.py tests/unit/agent/session/test_conversation_session.py tests/unit/agent/runs/test_runs_registry_executor.py tests/unit/agent/test_kernel_manual_compact.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/integration/test_conversation_compaction_integration.py` → `52 passed`。

## R1 — 失败值与会话计数契约

- Context: 固定 fallback 把 summary provider 失败伪装为成功，且 reloadable payload 无法拥有跨重建的连续失败状态。
- Decision: summarizer 统一返回有效文本或 `None`；新增结构化 `CompactionError`；由稳定 `ConversationSession` 创建 tracker，并把同一引用注入每个 `ConversationState`。
- Rationale: summary 组件只表达结果有效性，触发入口决定失败流程；计数跟随会话 identity 才能跨 external reload 与 LRU eviction。
- Evidence:
  - Tests: Red 为 `CompactionError` import 缺失；Green 为 `PYTHONPATH=src ... pytest -q tests/unit/test_core_errors.py tests/unit/test_loop_compact.py tests/unit/agent/session/test_conversation_session.py` → `29 passed`。
  - Entry: public conversation transaction seam 的 external append 与 payload eviction 后仍观察到同一 tracker 引用和计数。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/agent/session/test_conversation_session.py::test_automatic_compaction_failures_survive_payload_reload_and_eviction`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可恢复原 summarizer/ConversationState 契约。
- Commits: `724ca313b`。
- Next: R2 threshold bounded retry 与 commit 分流。

## R2 — threshold bounded retry 与 commit 分流

- Context: threshold summary failure 必须保留当轮原 prompt，并在同一会话上有限重试；stale 与 persistence 不能误算作 summary failure。
- Decision: loop 通过当前 `ConversationState` 的窄 callback 取得 tracker；前两次 `None` 返回原流程，第三次及已熔断状态抛 typed error；commit success reset，stale 保持计数，persistence 立即 typed failure。
- Rationale: loop 不持有跨 session map，且只有 durable commit 才能宣告压缩成功并清零。
- Evidence:
  - Tests: Red 为 `AgentLoop.__init__` 缺少 tracker callback；Green focused `3 passed`，扩展回归 `32 passed`。
  - Entry: AgentLoop 的实际 `run()` async iterator 验证前两轮仍产出原上下文回复，第三轮在主模型调用前停止。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/test_loop_compact.py::{test_threshold_summary_failure_continues_twice_then_stops,test_threshold_success_resets_failures_but_stale_commit_does_not,test_threshold_persistence_failure_stops_without_incrementing_count}`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可移除 threshold policy callback，R1 domain 不受影响。
- Commits: `d5997a17e`。
- Next: R3 public Kernel manual/overflow failure 与 automatic 用户提示。

## R3 — manual/overflow 与 automatic 用户提示

- Context: manual、overflow 与 threshold 的失败编排分散；automatic exception 原先直接进入 terminal，没有用户安全文本，fallback 又会错误提交 boundary。
- Decision: `_compact_session` 对 summary/stale/persistence 分别产出 typed outcome；overflow 计入共享 tracker 并保留原 provider cause，成功 commit 才 reset；runtime 对 automatic typed error 只发布固定 message/turn events，不写 transcript。
- Rationale: durable history 仍只有 `append_compaction` 一条 commit seam；提示和诊断分离，可复用现有 Web/CLI/Feishu assistant delivery，同时不会污染下一轮模型上下文。
- Evidence:
  - Tests: Red 覆盖旧 RuntimeError/strict、缺失 assistant event 与错误 SessionInfo ref；Green focused `6 passed`，R3 扩展回归 `33 passed`。
  - Entry: public `agent.sdk` Kernel submit/stream 证明 threshold 第三次、overflow summary failure、threshold persistence failure 都先收到固定 assistant text 再收到 failed terminal；manual public compact failure 保持历史。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_conversation_compaction_integration.py` 新增三类真实 SDK 入口回归；`tests/unit/agent/test_kernel_manual_compact.py` 覆盖 manual summary/stale/persistence atomicity。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 可恢复旧 runtime 编排，R1/R2 domain 与 loop policy 保留。
- Commits: `b83fbd948`。
- Next: R4 RunsRegistry 结构化 terminal、成功 reset/重载持续性与完整门禁。

## R4 — terminal 诊断、会话重载持续性与最终门禁

- Context: registry 原先把所有异常 stringify 为 `run_execution_failed`；还需闭合 overflow persistence/stale、外部重载/LRU 后第三次熔断和成功 reset 的矩阵。
- Decision: RunsRegistry 只识别 `CompactionError.to_dict()`，普通异常保持旧 payload；补齐 overflow 双 cause/stale 不计数、session tracker 跨重建及 manual success reset 回归。
- Rationale: terminal writer 是稳定诊断的唯一 owner；不同失败原因在最低层各守一次，再由 public Kernel integration 守事件顺序与 durable history。
- Evidence:
  - Tests: Red 为 typed error 被压成 generic；Green 为 design M2 focused suite `65 passed`，Ruff `All checks passed`，`git diff --check` 通过。
  - Entry: public Kernel submit/stream 覆盖 threshold、overflow、persistence 的 assistant-before-failed 与结构化 terminal；public Kernel compact 覆盖 manual atomicity/success reset。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_conversation_compaction_integration.py`；既有 `tests/unit/personal_assistant/test_external_visible_delivery.py::test_feishu_intermediate_reply_goes_to_external_without_im_manager` 在完整 suite 保持绿色。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint commit 恢复 generic registry terminal，并保留 R1-R3 已实现的运行时语义。
- Commits: `60c3a5871`。
- Next: rebase、复跑门禁并合入 `unit/bugfix-520`。

## Promotion Candidates

None.

## Reviewer fix round 1

- Context: change-code-review 独立确认五项 substantive 缺口：analysis-only 假成功、summary side-chain 事件泄露、skill reinjection parent 缺失、overflow retry 的 typed failure 未提示，以及 manual/overflow 成功后旧 token usage 未清理。
- Decision: 不改 design/spec，在 R5/R6 以可观察红测修复原架构 seam。
