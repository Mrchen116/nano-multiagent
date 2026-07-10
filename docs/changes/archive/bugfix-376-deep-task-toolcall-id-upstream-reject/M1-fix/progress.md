# M1-fix progress

## 根因分析（复现坐实）

通过分析 LLM proxy raw logs 坐实两个根因：

### RC1: get_completed_results 跳过 executing safe tool（主因）

原始 upstream-req `21-43-10_194`（114 messages）暴露：
- [19] assistant: tool_use A (SGycDRbp1KDbuV26tVftnnsg, read) + tool_use B (TYMV0Fyv9NyC68U8NTY3QOIj, read)
- [20] user: tool_result for A only
- [21] assistant: tool_use C (ZYiRX2dMcfVgTVdK5UmkH3ey, bash)  ← B 的 result 还没来
- [22] user: tool_result for B
- [23] user: tool_result for C

kimi 报 `read:10 did not have response messages`，因为 B 的 result 出现在下一个 assistant 消息之后。

**代码路径**：`tool_executor.py:get_completed_results()` line 219
```python
elif item.status == "executing" and not item.is_safe:
    break  # not item.is_safe = False for safe tools → 不 break！
```
对 safe tools，`not item.is_safe == False`，所以遇到 A(executing,safe) 时不 break，继续找到 B(completed,safe) 并返回 B。B 进入 `early_tool_results`，在流结束后先写入 llm_messages。A 在 `get_remaining_results()` 阶段才写入，结果 B 在 A 之后写入，但 A 先于 B 在 tool_use list 中——这就产生了 mispairing。

### RC2: _merge_adjacent_assistant 丢失 reasoning 字段（次要，可能引发独立问题）

`prompting.py:_merge_adjacent_assistant` 合并 assistant 消息时不携带 reasoning_content/reasoning_signature。

## 进度

- [x] 复现坐实（raw log 分析，2026-05-20）
- [x] C1 红测已写（2026-05-21）
- [ ] C2 修复
- [ ] C3 验证
