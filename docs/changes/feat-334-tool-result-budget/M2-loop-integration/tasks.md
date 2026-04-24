# M2 — AgentLoop 集成 + 工具声明 + 集成测试

## 目标

将 M1 建设的压缩器接入 `AgentLoop._serialize_tool_result()`，在 `AgentRuntime` 中完成构造注入，为各 builtin 工具声明 limit，并通过集成测试验证端到端行为。

---

## Roadpoint

### R1 — AgentLoop 集成压缩调用

**文件**：`src/agent/core/agent/loop.py`

**任务**：
- `__init__` 增加 `tool_result_compressor: ToolResultCompressor | None = None`
- `run()` 开头设置 `self._active_session_id = state.session_id`，`finally` 中清理
- `_serialize_tool_result()` 中：序列化后调用 `compressor.maybe_compress()`
  - 从 tool 实例读取 `max_result_size_chars`
  - 传入 `tool_call_id=result.call_id`、`session_id=self._active_session_id`

**验收标准**：
- [ ] 工具结果 > limit 时 LLMMessage.content 为 preview 文本
- [ ] 工具结果 ≤ limit 时原样通过
- [ ] `None` limit 时完全豁免

---

### R2 — AgentRuntime 构造注入

**文件**：`src/agent/core/agent/runtime.py`

**任务**：
- `__init__` 中创建 `ToolResultCompressor(base_dir=repo_root / ".nano" / "tool-results")`
- 注入到 `AgentLoop(..., tool_result_compressor=compressor)`

**验收标准**：
- [ ] Runtime 初始化后 loop 持有 compressor
- [ ] 落盘目录为 `{repo_root}/.nano/tool-results`

---

### R3 — Builtin 工具声明 limit

**文件**：
- `src/agent/platform/tools/builtins/read.py` → `max_result_size_chars = None`
- `src/agent/platform/tools/builtins/bash.py` → 默认（省略）
- `src/agent/platform/tools/builtins/web_fetch.py` → 默认或显式
- `src/agent/platform/tools/builtins/write.py` → 默认
- `src/agent/platform/tools/builtins/edit.py` → 默认
- `src/agent/platform/tools/builtins/task.py` → 默认

**验收标准**：
- [ ] ReadTool 实例的 `max_result_size_chars` 为 `None`
- [ ] 其他工具为 `None`（默认值）或显式值

---

### R4 — 集成测试

**文件**：`tests/unit/test_agent_loop.py`（追加）或 `tests/integration/`

**任务**：
- Mock tool 返回 oversized 结果，验证 AgentLoop yield 的 Message.content 为 preview
- 验证 `metadata["tool_output"]` 保留原始数据
- 验证 Read 工具豁免（使用真实 ReadTool）

**验收标准**：
- [ ] pytest 通过
- [ ] 无现有测试回退

---

## 测试策略

单元测试使用 mock LLM client + mock tool registry，不依赖外部 LLM。

```bash
uv run pytest tests/unit/test_agent_loop.py -v
uv run pytest tests/unit/test_tools_builtins.py -v
```
