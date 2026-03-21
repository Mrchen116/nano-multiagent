# M252 PROGRESS：修复 AgentPolicies 硬性限制

## 初始状态

- baseline：15 tests pass (test_agent_policies + test_agent_loop + test_loop_retry)
- loop.py L128: `self._policies.ensure_turn_allowed(turn_count=state.turn_count)` — 待移除
- loop.py L134: `self._policies.truncate_history(state.history_messages)` — 待移除
- policies.py: max_turns=32, max_context_messages=24, max_tool_calls=16 — 待修改
- policies.py truncate_history bug: max_context_messages<=0 返回空元组，应返回原始

## Roadpoints

### R1 修复 policies.py：默认值 + truncate_history 边界 bug
- Context: 默认值过于保守（max_turns=32, max_context_messages=24, max_tool_calls=16）；truncate_history 在 <=0 时错误返回空元组，应表示"无限制"。
- Decision: 默认值改为 max_turns=10000, max_context_messages=0, max_tool_calls=64；truncate_history <=0 分支改为 `return messages`。
- Rationale: 上下文管理由 compaction 子系统负责，policies 默认不截断；max_turns=10000 作为极端保护而非实用限制。
- Evidence:
  - Tests: 9 passed (test_agent_policies.py) in 0.10s
  - Entry: AgentPolicies() 实例字段值已更新，truncate_history(messages, 0) 返回原始 messages
- Rollback: 回退到 bd2d405（plan commit）
- Commits: C1=dc2e31c, C2=5f4d955, C3=pending
- Next: R2 — 移除 loop.py 中 ensure_turn_allowed 和 truncate_history 调用
