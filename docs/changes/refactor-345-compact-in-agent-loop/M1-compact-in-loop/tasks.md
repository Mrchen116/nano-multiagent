# refactor-345-M1: compact-in-loop — Tasks

> 对齐: ../design.md v1

## 目标

将 compaction 触发点从 runtime preflight 移入 AgentLoop.run() 内部，实现 loop 内 token 超限主动 compact，compact 后继续当前 iteration，session history 不被修改，system prompt 在 compact 后不丢失。

## 退出标准

- [x] loop 内 token 超限触发 compact
- [x] compact 后 iteration 继续
- [x] session history 不被修改
- [x] runtime 消费 summary msg 时正确写 compact_boundary
- [x] system prompt 在 compact 后不丢失

## 测试策略

本 milestone 为纯后端逻辑重构，不涉及前端 UI。测试策略：

1. **单元测试**：新增 `test_loop_compact.py` 覆盖 loop 内 compact 触发、继续 iteration、history 不变性、system prompt 保留
2. **单元测试**：新增 `test_runtime_compact_boundary.py` 覆盖 runtime 消费 summary msg 时写 compact_boundary
3. **现有测试回归**：`test_agent_runtime.py`、`test_agent_prompting.py`、`test_loop_retry.py`、`test_compaction_planner.py` 必须全绿
4. **入口验证**：通过 `test_agent_runtime.py` 中现有 runtime 集成测试验证真实链路

## Roadpoints

### R1 — 前置迁移与 prompting 拆分

- 步骤:
  1. 将 `runtime.py` 中的 `_message_from_turn_entry` 迁移到 `session/entries.py`
  2. 将 `runtime.py` 中的 `_read_file_slice` 迁移到 `tools/session_file_state.py`
  3. 在 `prompting.py` 新增 `build_chat_messages`（不含 system prompt）
  4. 在 `prompting.py` 新增 `_estimate_llm_context_tokens` 适配 LLMMessage
  5. 更新 `build_prompt_messages` 为 `build_system_prompt` + `build_chat_messages` 的兼容包装
- 验证:
  - `test_agent_prompting.py` 全绿
  - 新增 `test_build_chat_messages` 通过
  - 新增 `test_estimate_llm_context_tokens` 通过

### R2 — loop.py 新增 compact 能力

- 步骤:
  1. `AgentLoop.__init__` 注入 `SessionManager`、`CompactionPlanner`、`CompactionSummarizer`、`CompactionSettings`
  2. `run()` 内分离 `rendered_system_prompt` 和 `llm_messages`
  3. `while True` 开头新增 `_should_compact` + `_maybe_compact`
  4. `_maybe_compact` 实现 plan + summarize + file restore + 构建新 llm_messages
  5. compact 后 yield summary msg（带 `is_compact_summary=True`）
  6. 调用 LLM 前临时拼接 system prompt
- 验证:
  - 新增 `test_loop_compact.py` 全绿（5 个退出标准用例）
  - `test_loop_retry.py` 全绿

### R3 — runtime.py 移除 preflight + 消费 compact_boundary

- 步骤:
  1. 移除 `_preflight_compaction` 调用（285-288 行）
  2. 删除 `_post_turn_check_overflow` 死代码
  3. 消费 msg 时检测 `is_compact_summary`，写 `compact_boundary` entry
  4. `_compact_session` 保留但仅用于 public `compact()` API
  5. 更新 `_execute_loop` 注入 compact 组件
- 验证:
  - 新增 `test_runtime_compact_boundary.py` 通过
  - `test_agent_runtime.py` 全绿

### R4 — 回归测试 + 文档

- 步骤:
  1. 跑全量相关测试
  2. 更新 `progress.md`
  3. 如有经验沉淀写 `LOGBOOK.md`
- 验证:
  - `pytest tests/unit/test_agent_runtime.py tests/unit/test_agent_prompting.py tests/unit/test_loop_retry.py tests/unit/test_compaction_planner.py tests/unit/test_loop_compact.py tests/unit/test_runtime_compact_boundary.py -q` 全绿
