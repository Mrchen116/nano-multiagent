# feat-385-M1: impl — Tasks

## 目标

将 runtime 从老 f-string 模板路径（`loop.py build_system_prompt`）切换为段式装配路径（`resolve_effective_prompt`），同时完成 memory 闭环修复（MemoryStore freeze + 注入 PromptContext）、MemoryTool per-session 隔离修复，以及删除 `core.runtime_tools` 段和 `pa.memory_intro` 段、老 f-string 模板常量退役。

## 退出标准

- `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` 全绿 ✓
- 新增 contract 测试：`src/` 下 `.nano`/`.nanoassistant`/`.nanocode` 只允许出现在 product `defaults.py`（白名单机制防止新增）✓
- `core.memory_block` / `core.user_profile_block` 段在 memory_curation on + workspace + dirname 齐备时激活，任一缺失时失活 — 单测覆盖 ✓
- `derive_memory_root` 单测覆盖 PA / LC 两种 dirname ✓
- MemoryTool 写入与 runtime freeze 读取从同一物理路径 — 集成测试覆盖 ✓
- 删除 `core.runtime_tools` 段 + `pa.memory_intro` 段 ✓
- `products/{personal_assistant,local_coding}/prompts.py` 整文件删除 ✓

## 测试策略

主要测试层次：
- **单元测试（unit）**：`derive_memory_root` helper、`_ensure_memory_snapshot` 逻辑（内存快照、gate、cache）、PromptContext.user_profile_block、core_sections 改动
- **集成测试（integration）**：runtime 装配产物含 memory_block / user_profile_block；MemoryTool 写路径 == freeze 读路径；bootstrap 默认 metadata 含 workspace_config_dirname
- **Contract 测试（contract）**：无新硬编码 workspace dirname（`.nano`/`.nanoassistant`/`.nanocode` 只允许在 defaults.py）；loop 不 import runtime

N/A 前端/UI（纯后端改动）

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | core/memory/path.py + derive_memory_root 单测 | DONE |
| R2 | PromptContext.user_profile_block + wiring 更新 | DONE |
| R3 | core_sections: 删 runtime_tools + 加 user_profile_block 段 | DONE |
| R4 | runtime 切段式装配 + _ensure_memory_snapshot | DONE |
| R5 | MemoryTool 隔离修复 + bootstrap 改动 | DONE |
| R6 | 老 f-string 模板退役 + pa.memory_intro 删除 | DONE |
| R7 | contract 测试无新 hardcode workspace dirname | DONE |
