# M252 PROGRESS：修复 AgentPolicies 硬性限制

## 初始状态

- baseline：15 tests pass (test_agent_policies + test_agent_loop + test_loop_retry)
- loop.py L128: `self._policies.ensure_turn_allowed(turn_count=state.turn_count)` — 待移除
- loop.py L134: `self._policies.truncate_history(state.history_messages)` — 待移除
- policies.py: max_turns=32, max_context_messages=24, max_tool_calls=16 — 待修改
- policies.py truncate_history bug: max_context_messages<=0 返回空元组，应返回原始

## Roadpoints
