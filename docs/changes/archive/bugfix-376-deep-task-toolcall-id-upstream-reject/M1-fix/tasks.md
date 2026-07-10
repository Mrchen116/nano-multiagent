# M1-fix tasks

## 测试策略

单测为主。两个根因都可以在不依赖真实 LLM 的情况下确定性覆盖：
- RC1（`get_completed_results` 跳过 executing safe tool）→ 纯 StreamingToolExecutor 单测，asyncio mock
- RC2（`_merge_adjacent_assistant` 丢失 reasoning 字段）→ 纯 prompting 单测，构造 LLMMessage 列表

e2e 验证在 C3 做：跑一轮真实 kimi K2.6 deep task，抓 raw upstream-req 确认无 mispairing。

## C1 — 红测

- [x] 补 `tests/unit/test_streaming_tool_executor.py`：
  - `test_get_completed_results_skips_executing_safe_before_earlier_executing_safe` — [A(executing,safe), B(completed,safe)] 时 get_completed_results() 不应返回 B（当前 BUG：会返回 B）
  - `test_parallel_safe_tool_results_always_in_enqueue_order` — 两个并行 safe 工具，慢完成的先入队，get_completed_results() + get_remaining_results() 拼起来的顺序必须与 enqueue 顺序一致
- [x] 补 `tests/unit/test_prompting_merge_adjacent.py`（新文件）：
  - `test_merge_adjacent_assistant_preserves_reasoning_fields` — _merge_adjacent_assistant 不应丢弃 reasoning_content / reasoning_signature

## C2 — 修复

- [ ] 修 `tool_executor.py:get_completed_results`：遇到任何 executing 项（不论 is_safe）都 break，保证 FIFO
- [ ] 修 `prompting.py:_merge_adjacent_assistant`：合并时保留 reasoning_content/reasoning_signature

## C3 — 验证 + 文档

- [ ] 运行单测 green
- [ ] e2e：kimi K2.6 thinking，bash+read 深度任务，看 raw upstream-req 无 mispairing
- [ ] 回填 fix.md 修复/验证节
- [ ] 更新 progress.md
