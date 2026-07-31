# M218: Personal Assistant 系统提示词对标 nanobot

## 2026-03-16 22:30:00 +0800

### Done
- 重写 `personal_assistant/prompts.py`：从 4 行纯文本升级为结构化模板，含 Runtime/Platform Policy/Available Tools/Memory/Heartbeat/Guidelines + 4 个 RUNTIME_FILL 占位符
- `personal_assistant/toolsets.py`：DEFAULT_TOOL_IDS 从 `["read", "task"]` 扩充为 `["read", "write", "edit", "bash", "task"]`，对齐 core builtin 全集
- 更新 `docs/内核设计细化/系统提示词.md`：补齐占位符机制说明、两产品模板全文、差异对比表
- 确认改动与 内核设计SPEC / IM-SPEC 无冲突（原 toolset 反而偏离 SPEC，现已修正）

### Evidence
- prompts.py 包含 `<RUNTIME_FILL:AVAILABLE_TOOLS>`、`<RUNTIME_FILL:SKILLS_SECTION>`、`<RUNTIME_FILL:CURRENT_DATETIME>`、`<RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>` 四个占位符
- toolsets.py DEFAULT_TOOL_IDS 与 local_coding 一致

### Files Changed
- `src/agent/products/personal_assistant/prompts.py`
- `src/agent/products/personal_assistant/toolsets.py`
- `docs/内核设计细化/系统提示词.md`

### Next
- 分析对标 nanobot 的能力差距（web_fetch/web_search、HISTORY.md、Bootstrap files 等）
