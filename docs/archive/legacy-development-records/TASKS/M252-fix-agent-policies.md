# M252 任务计划：修复 AgentPolicies 硬性限制

## 目标

- 移除 loop.py 中 `ensure_turn_allowed` 调用（硬性 turn 限制）
- 移除 loop.py 中 `truncate_history` 调用（硬性截断）
- 修复 policies.py 默认值与 `truncate_history` <= 0 边界 bug

## Roadpoints

### R1 — 修复 policies.py：默认值 + truncate_history 边界 bug

**状态：DONE**

**Acceptance：**
1. `max_turns` 默认值 = 10_000
2. `max_context_messages` 默认值 = 0
3. `max_tool_calls` 默认值 = 64
4. `truncate_history(messages, max_context_messages=0)` 返回原始 messages，不返回空元组
5. `truncate_history(messages, max_context_messages=-1)` 也返回原始 messages

**Tests Plan：**
- unit：测试默认值字段、truncate_history 边界（<=0 时返回原始、>0 时正常截断）
- contract：无需额外 contract 测试（dataclass 字段类型 Pydantic 已覆盖）
- integration：不适用（纯内存逻辑）
- e2e：不适用

**Expected Tests：**
- `tests/unit/test_agent_policies.py`
  - `test_default_max_turns_is_10000`
  - `test_default_max_context_messages_is_zero`
  - `test_default_max_tool_calls_is_64`
  - `test_truncate_history_returns_original_when_max_context_messages_is_zero`
  - `test_truncate_history_returns_original_when_max_context_messages_is_negative`

**DoD：** test_command 全绿 + C1/C2/C3 齐全

---

### R2 — 移除 loop.py 中 ensure_turn_allowed 和 truncate_history 调用

**状态：DONE**

**Acceptance：**
1. `loop.run()` 不再调用 `ensure_turn_allowed`
2. 即使 `turn_count >= max_turns`，loop.run() 不抛 PolicyViolation
3. `loop.run()` 不再调用 `truncate_history`，`history_messages` 完整传给 LLM
4. 现有测试全部通过

**Tests Plan：**
- unit：测试 loop 不再因 turn_count 超限抛异常；测试 history 完整传递
- contract：不适用
- integration：不适用
- e2e：不适用

**Expected Tests：**
- `tests/unit/test_agent_loop.py`
  - `test_loop_does_not_raise_on_high_turn_count`
  - `test_loop_passes_full_history_to_llm`

**DoD：** test_command 全绿 + C1/C2/C3 齐全
