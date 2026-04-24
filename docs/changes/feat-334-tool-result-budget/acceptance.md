# Acceptance: Per-Tool Result Budget（工具结果单条预算与预览）

##  verdict

**通过（PASS）**

本 feature 已完成 M1（核心压缩器 + 契约扩展）、M2（AgentLoop 集成 + 工具声明 + 集成测试）和 M3（Bash 文件模式 + 30K 阈值 + 真实 CLI 验证）。所有新增单元测试和集成测试通过，现有测试无回退。

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

### 场景 4：Bash 真实 CLI 大输出（60K）自动压缩

**用户操作**：通过 CLI 让 agent 运行 `python3 -c "print('x' * 60000)"`

**预期**：
- BashTool 返回完整 60K stdout（文件模式，无内存膨胀）
- AgentLoop 压缩器识别 60K > 30K limit，替换为 `<persisted-output>`
- 完整输出保存到 `.nano/tool-results/{session_id}/{call_id}.txt`
- LLM JSONL message 中 tool result 仅含 preview

**验证方式**：真实 CLI 运行（session `sess_9e7efd3f162fcf51`）
- JSONL tool message 内容包含 `<persisted-output>...60000 chars > 30000 limit`
- 落盘文件大小 60000 bytes，内容完整
- 临时文件 `.agent/tmp/bash-stdout-*.log` 运行后自动清理

**结果**：通过

---

### 场景 5：Bash 真实 CLI 小输出（17 chars）不压缩

**用户操作**：通过 CLI 让 agent 运行 `echo hello_world_small`

**预期**：
- 结果原样进入 LLM 上下文，无 `<persisted-output>`

**验证方式**：真实 CLI 运行（session `sess_9add78a5d07d4478`）
- JSONL tool message content = `"hello_world_small"`
- 无 persisted-output 标记

**结果**：通过

---

### 场景 6：1MB 硬上限截断

**用户操作**：通过 CLI 让 agent 运行 `python3 -c "print('z' * (2 * 1024 * 1024))"`

**预期**：
- Safety 层文件模式在写入 1MB 后停止落盘，标记 truncated
- BashTool 返回的 stdout 恰好 1MB（1048576 字节）
- 不会触发后续压缩（因为 truncated 已在 safety 层处理）

**验证方式**：直接集成测试 `test_file_mode_and_30k_compression`
- `result["truncated"] == True`
- `len(result["stdout"]) == 1048576`

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
| `tests/unit/test_tools_builtins.py` | 64 (+8 新增) | Bash 文件模式 + 30K limit + 1MB 截断 + serialize 简化 |

---

## 关键文件变更

```
src/agent/core/tools/result_budget.py        # 新增：ToolResultCompressor
src/agent/core/types.py                       # 修改：ToolSpec.max_result_size_chars
src/agent/core/tools/base.py                  # 修改：Tool.max_result_size_chars
src/agent/core/tools/registry.py              # 修改：list_specs() 传递默认值
src/agent/core/agent/loop.py                  # 修改：_serialize_tool_result() 集成压缩
src/agent/core/agent/runtime.py               # 修改：构造 compressor 注入 loop
src/agent/platform/tools/builtins/read.py     # 修改：max_result_size_chars = None
src/agent/platform/tools/builtins/bash.py     # 修改：文件模式读取 + max_result_size_chars=30K
src/agent/platform/tools/safety.py            # 修改：run_command_stream 文件模式 + 1MB 硬上限
tests/unit/test_tool_result_budget.py         # 新增：16 单元测试
tests/unit/test_agent_loop.py                 # 修改：+3 集成测试
tests/unit/test_tools_builtins.py             # 修改：+8 Bash 文件模式相关测试
```
