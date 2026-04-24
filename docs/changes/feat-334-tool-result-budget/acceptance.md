# Acceptance: Per-Tool Result Budget（工具结果单条预算与预览）

##  verdict

**通过（PASS）**

本 feature 已完成 M1（核心压缩器 + 契约扩展）和 M2（AgentLoop 集成 + 工具声明 + 集成测试）。所有新增单元测试和集成测试通过，现有测试无回退。

---

## 用户旅程验证

### 场景 1：Bash 大输出自动压缩

**用户操作**：让 agent 运行 `find . -type f | xargs cat`（产生大量输出）

**预期**：
- LLM 收到的 tool result 被替换为 `<persisted-output>` preview
- 完整输出保存到 `.nano/tool-results/{session_id}/{call_id}.txt`
- model 仍可从 preview 获知"这是一个超大输出"

**验证方式**：集成测试 `test_loop_compresses_oversized_tool_result`
- 500 字符结果 + 100 字符 limit → 触发压缩
- `tool_results[0].content` 包含 `<persisted-output>`
- `metadata["tool_output"]` 保留原始 `{"text": "x"*500}`
- 文件保存路径和内容正确

**结果**：通过

---

### 场景 2：Read 工具永远完整

**用户操作**：`read` 一个 10 万行的日志文件

**预期**：
- Read 工具结果完整进入 LLM 上下文，不触发压缩
- 模型获得精确的文件内容用于后续 edit/write

**验证方式**：集成测试 `test_loop_skips_compression_for_unlimited_tool`
- 500 字符结果 + `max_result_size_chars=None` → 不压缩
- `tool_results[0].content == "x" * 500`
- 无落盘文件

**结果**：通过

---

### 场景 3：小输出不受影响

**用户操作**：`bash ls` 或 `read` 一个小文件

**预期**：
- 结果字符数 ≤ limit，原样发送，无 `<persisted-output>` 包裹

**验证方式**：集成测试 `test_loop_under_limit_no_compression`
- 50 字符结果 + 100 字符 limit → 不压缩
- `tool_results[0].content == "x" * 50`

**结果**：通过

---

## 问题清单

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | 无 aggregate budget（N 个 parallel 工具结果总和未限制）| 低 | 设计内决策，需要时追加 |
| 2 | 落盘文件无自动清理机制，长期运行可能累积 | 低 | product 层负责，非本 feature 范围 |
| 3 | preview 纯文本截断，非 LLM 摘要 | 低 | 设计内决策 |

---

## 测试覆盖

| 测试文件 | 用例数 | 说明 |
|---------|--------|------|
| `tests/unit/test_tool_result_budget.py` | 16 | 压缩器核心：limit/None/list/图片/空串/换行截断 |
| `tests/unit/test_agent_loop.py` | 12 (+3 新增) | AgentLoop 集成：压缩/豁免/通过 |
| `tests/unit/test_tools_builtins.py` | 56 | Builtin 工具行为无回退 |

---

## 关键文件变更

```
src/agent/core/tools/result_budget.py       # 新增：ToolResultCompressor
src/agent/core/types.py                      # 修改：ToolSpec.max_result_size_chars
src/agent/core/tools/base.py                 # 修改：Tool.max_result_size_chars
src/agent/core/tools/registry.py             # 修改：list_specs() 传递默认值
src/agent/core/agent/loop.py                 # 修改：_serialize_tool_result() 集成压缩
src/agent/core/agent/runtime.py              # 修改：构造 compressor 注入 loop
src/agent/platform/tools/builtins/read.py    # 修改：max_result_size_chars = None
tests/unit/test_tool_result_budget.py        # 新增：16 单元测试
tests/unit/test_agent_loop.py                # 修改：+3 集成测试
```
