# M1 — Core Compressor + Contract Extension

## 目标

完成工具结果压缩器的核心实现，以及 ToolSpec/Tool/ToolRegistry 的契约扩展。本 milestone 不修改 AgentLoop，仅建设基础设施并保证压缩器单元测试通过。

---

## Roadpoint

### R1 — ToolResultCompressor

**文件**：`src/agent/core/tools/result_budget.py`

**任务**：
- 定义常量 `DEFAULT_MAX_RESULT_SIZE_CHARS = 50_000`、`PREVIEW_SIZE_CHARS = 2_000`
- 实现 `ToolResultCompressor` 类：
  - `__init__(base_dir: Path)`
  - `maybe_compress(content, tool_name, tool_call_id, session_id, max_size_chars) -> str | list[dict]`
- 实现 `_generate_preview(text, max_chars) -> str`，优先在换行处截断（`> 0.5 * max_chars` 时）
- `None` limit 直接原样返回
- list content 含非 text block 时跳过压缩
- 超限后原子写入 `.txt`（write tmp + replace）

**验收标准**：
- [ ] 40K 内容 + 50K limit → 原样返回
- [ ] 120K 内容 + 50K limit → 返回 `<persisted-output>` 包裹字符串，文件落盘
- [ ] None limit → 任何大小都原样返回
- [ ] list[dict] 含 image block → 原样返回
- [ ] preview 在换行处截断（测试包含多行文本）
- [ ] 文件写入路径正确 `.nano/tool-results/{session_id}/{call_id}.txt`

---

### R2 — ToolSpec / Tool / ToolRegistry 契约扩展

**文件**：
- `src/agent/core/types.py`
- `src/agent/core/tools/base.py`
- `src/agent/core/tools/registry.py`

**任务**：
- `ToolSpec` 增加 `max_result_size_chars: int | None = None`
- `Tool` Protocol 增加同名属性（带默认值 `None`）
- `ToolRegistry.list_specs()` 用 `getattr(tool, "max_result_size_chars", None)` 传递

**验收标准**：
- [ ] `ToolSpec(name="x", description="y", input_schema={}).max_result_size_chars is None`
- [ ] `ToolRegistry.list_specs()` 正确传递各工具的 `max_result_size_chars`

---

### R3 — 单元测试

**文件**：`tests/unit/test_tool_result_budget.py`

**任务**：
- `maybe_compress` 各分支覆盖
- `_generate_preview` 截断边界（换行在 50% 内/外）
- 文件系统断言（落盘内容、路径）

**验收标准**：
- [ ] pytest 全部通过
- [ ] coverage 覆盖所有分支

---

## 测试策略

纯单元测试，不依赖 LLM、不启动 HTTP server、不使用真实文件系统（tmpdir 即可）。

```bash
uv run pytest tests/unit/test_tool_result_budget.py -v
```
