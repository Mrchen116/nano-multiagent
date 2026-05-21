# feat-379-M4: core-content-align-cc

## 目标

把 `core_sections.py` 中的 core 段内容对齐 CC 真实通用规范（`prompts.ts` 逐字核实）：
- 新增 `core.actions_care`（风险操作先确认，现为 render→None stub）
- 新增 `core.tone_style`（file_path:line_number / owner/repo#123 / emoji 按需 / tool 前不加冒号，现为 stub）
- 补全 `core.system`（prompt-injection flag / 被拒工具调用处理 / system-reminder 说明 / 自动压缩说明 / hooks 说明）
- 修 `core.tool_rules`（专用工具优先 + 并行调用；纠正现状 render→None stub）

范围：仅 `src/agent/core/agent/prompt_sections/core_sections.py`，不动 `feature_registry.py`（M2 范围）。

## 退出标准

- `[worker]` 新增/改写段单测通过（test_core_sections_m4.py）
- `[worker]` 每个新增/改写段带 `Provenance: CC-adapted` 注释，含 CC 源 `<file:symbol>` + 改了什么
- `[worker]` core 段文案与 CC 对应通用段语义一致（去除 coding/CC 产品专属），逐段 review 记录在 progress.md
- `[reviewer]` agent 在不可逆/影响他人操作前先确认
- `[reviewer]` 引用代码用 `file_path:line_number`，引用 issue 用 `owner/repo#123`，非请求不滥用 emoji

## 测试策略

纯内部改动（core 段文案）；用户入口是 agent 的 system prompt，测试策略：
- C1: 为每个要填充的段写失败单测（断言关键文案短语 / render 不为 None）
- C2: 填充文案让测试通过
- 无前端/浏览器验收（本段纯文案，reviewer 验收用 system prompt 输出观察行为）

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| core.system 文案完整度 | 单测断言各关键句存在 | 是 |
| core.actions_care 文案 | 单测断言 render 非 None + 关键词 | 是 |
| core.tool_rules 文案 | 单测断言 render 非 None + 关键词 | 是 |
| core.tone_style 文案 | 单测断言 render 非 None + 关键词 | 是 |
| Provenance 注释完整 | 代码 review（progress.md 逐段记录） | N/A（注释） |

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 写失败单测（四段 render 非 None + 关键词） | DONE |
| R2 | 填充 core.system 文案 | DONE |
| R3 | 填充 core.actions_care 文案 | DONE |
| R4 | 填充 core.tool_rules 文案 | DONE |
| R5 | 填充 core.tone_style 文案 | DONE |
