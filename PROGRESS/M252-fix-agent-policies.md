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

### R2 移除 loop.py 中 ensure_turn_allowed 和 truncate_history 调用
- Context: loop.py L128 调用 ensure_turn_allowed（硬性 turn 限制），L134 调用 truncate_history（硬性截断 history）；compaction 子系统已负责上下文管理，两处调用多余且有害。
- Decision: 删除 L128 的 ensure_turn_allowed 调用；将 L134 truncate_history(state.history_messages) 替换为直接传 state.history_messages。
- Rationale: 上下文超限由 compaction preflight/post-turn 处理，不需要 loop 层再次硬截断；max_turns 限制会在 agent 未完成任务时误终止会话。
- Evidence:
  - Tests: 653 unit tests passed in 150s（全绿）
  - Entry: loop.run() 在 turn_count=9999 + max_turns=1 时不再抛 PolicyViolation；5 条 history 消息完整传入 LLM
- Rollback: 回退到 7c74e07（R2 C1 测试提交）
- Commits: C1=7c74e07, C2=4f73749, C3=pending
- Next: 集成到 main
