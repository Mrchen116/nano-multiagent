# bugfix-453-M1 progress

## R1 — C1 红测：复现同一 response group 内 duplicate thinking

- Context: 现场根因是一轮 LLM response 的一份 reasoning 被展开到多个 assistant tool-call message；Gateway 对每条 `assistant_message.reasoning_content` 都发 `thinking_segment`。
- Decision: 在 `tests/unit/test_inbound_pipeline_streaming.py` 增加两个 Gateway observer 回归 case：同一 `group_id` 的同一 reasoning 只能转发一次；不同 `group_id` 即使 reasoning 文本相同也不能被合并。同步在 `tests/unit/platform/hooks/test_realtime_stream_events.py` 增加 `group_id` 透传测试。
- Rationale: 用户明确区分「一轮 LLM 输出多次」与「两轮 LLM 碰巧 thinking 相同」。`group_id` 是现有 agent loop 表达同一 LLM response 的结构化边界，比按文本全局去重更精确。
- Evidence:
  - Red: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/platform/hooks/test_realtime_stream_events.py::test_message_end_assistant_message_carries_group_id tests/unit/test_inbound_pipeline_streaming.py::TestObserverForwardsThinkingSegment::test_same_group_reasoning_is_forwarded_once tests/unit/test_inbound_pipeline_streaming.py::TestObserverForwardsThinkingSegment::test_same_text_different_group_reasoning_is_not_collapsed -q` -> 2 failed, 1 passed. Failures: `KeyError: 'group_id'`; same-group thinking produced 3 `thinking_segment` frames.
- Rollback: Revert this milestone commit.
- Commits: 91a91257.
- Next: R2。

## R2 — C2 实现：只展示一次同 response thinking，保留历史 round-trip

- Context: `agent.core.agent.loop` 的 `Message` 已经保存 `group_id`，但 `message_end` 事件和 `realtime_stream` 没有透传给 Gateway；provider/mapper 的 `reasoning_content` / `reasoning_signature` round-trip 不能删。
- Decision: `loop.py` 在 `message_end` payload 增加 `group_id`；`realtime_stream.py` 在 `assistant_message` 事件继续透传；Gateway observer 用 per-run `visible_reasoning_by_group` 记录每个 response group 已转发的 reasoning。相同文本重复 suppress；后续文本以前一段为前缀时只转发新增后缀；不同 group 不合并。
- Rationale: 修复点落在用户可见事件边界，不改变 LLM 历史消息和 provider 出站映射，保住 bugfix-373/375 的 thinking round-trip 约束。per-run 状态在 `turn_end` 和 `run_terminal_reconcile` 清理，不落库、不影响历史消息。
- Evidence:
  - Green: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/platform/hooks/test_realtime_stream_events.py::test_message_end_assistant_message_carries_group_id tests/unit/test_inbound_pipeline_streaming.py::TestObserverForwardsThinkingSegment::test_same_group_reasoning_is_forwarded_once tests/unit/test_inbound_pipeline_streaming.py::TestObserverForwardsThinkingSegment::test_same_text_different_group_reasoning_is_not_collapsed -q` -> 3 passed.
- Rollback: Revert this milestone commit.
- Commits: 91a91257.
- Next: R3。

## R3 — C3 验证与文档回填

- Context: 需要证明源头事件、hook 投影、Gateway observer 三段链路一起成立。
- Decision: 扩展 `tests/unit/test_agent_loop.py::test_message_end_observe_event_carries_reasoning_content`，断言带 reasoning 的 `message_end` 同时带 `group_id`。运行相关文件级测试和 ruff。
- Rationale: 覆盖用户可见重复 thinking 的最短链路，同时避免跑昂贵 live e2e；本变更不涉及浏览器 UI、数据库 migration 或外部 IM。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_agent_loop.py::test_message_end_observe_event_carries_reasoning_content tests/unit/platform/hooks/test_realtime_stream_events.py::test_message_end_assistant_message_carries_reasoning_content tests/unit/platform/hooks/test_realtime_stream_events.py::test_message_end_assistant_message_carries_group_id tests/unit/test_inbound_pipeline_streaming.py::TestObserverForwardsThinkingSegment -q` -> 8 passed.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_agent_loop.py tests/unit/platform/hooks/test_realtime_stream_events.py tests/unit/test_inbound_pipeline_streaming.py -q` -> 61 passed.
  - Lint: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff check src/agent/core/agent/loop.py src/agent/platform/hooks/builtins/realtime_stream.py src/personal_assistant/main.py tests/unit/test_agent_loop.py tests/unit/platform/hooks/test_realtime_stream_events.py tests/unit/test_inbound_pipeline_streaming.py` -> All checks passed.
  - Entry: Internal Web IM process timeline via Gateway observer.
  - Frontend State Matrix: N/A, no frontend code changed.
  - Browser QA: N/A, process-item generation is covered before WS persistence.
  - E2E/Regression: N/A, no service startup required for this isolated observer/event-chain fix.
  - Visual/Interaction: N/A.
- Rollback: Revert this milestone commit.
- Commits: 91a91257.
