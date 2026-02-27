# TASKS (Current Milestone: M10)

## [DONE] R10.1 policy + planner + CompactionEntry 基线
- Steps:
  - 新增 compaction 红测（unit/contract/integration/e2e）固定 M10 关键行为缺口（Red）
  - 实现 `agent/compaction` 基础模块：`types/policy/planner/applier/summarizer`（最小骨架）
  - 在 `SessionManager` 增加 `append_compaction/list_entries`，并按 `first_kept_event_id` 重建上下文回放
  - 校验切点规划不拆 `tool_call/tool_result`
  - 跑 R10.1 目标测试集并记录证据
  - 回填历史占位：`R9.1 C3=fc30c3e`
- Expected Tests:
  - `tests/unit/test_compaction_planner.py`
  - `tests/contract/test_compaction_contract.py`
  - `tests/integration/test_compaction_runtime_integration.py`
  - `tests/unit/test_session_entries.py`
  - `tests/contract/test_session_serializers_contract.py`
- DoD:
  - R10.1 目标测试全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R10.1 hash 与证据

## [DONE] R10.2 runtime compaction 接线（threshold/overflow/manual）
- Steps:
  - 增补 runtime compaction 红测：threshold preflight、overflow 补救重试、manual compact、e2e 恢复链路（Red）
  - 在 `AgentRuntime` 接入 preflight compaction 与 overflow post_turn_check 重试
  - 接入 `CompactionSummarizer` 与 `CompactionApplier`，落盘 `CompactionEntry(first_kept_event_id)`
  - 约束上下文重建为 `system + compaction_summary + kept_recent_messages`
  - 支持 `summary_model` 与主模型解耦（最小实现）
  - 跑 `pytest -q` 全量验收并回填 R10.1 C3
- Expected Tests:
  - `tests/contract/test_compaction_contract.py`
  - `tests/integration/test_compaction_runtime_integration.py`
  - `tests/e2e/test_compaction_overflow_recovery_e2e.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R10.2 hash 与证据
  - 不进入 M11/M12

## Milestone M10 状态
- R10.1 已完成：`d7950f0` -> `5ac5758` -> `ec6a086`。
- R10.2 已完成：`41fd8bf` -> `e223a5b` -> `(this docs commit)`。
- M10 验收测试已通过：`pytest -q` => `116 passed in 5.26s`。
