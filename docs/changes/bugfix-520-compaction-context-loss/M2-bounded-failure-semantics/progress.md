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
- Commits: 本 roadpoint commit。
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
- Commits: 本 roadpoint commit。
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
- Commits: 本 roadpoint commit。
- Next: R4 RunsRegistry 结构化 terminal、成功 reset/重载持续性与完整门禁。

## Promotion Candidates

None.
