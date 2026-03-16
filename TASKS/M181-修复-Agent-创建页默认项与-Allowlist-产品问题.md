# M181 - 修复 Agent 创建页默认项与 Allowlist 产品问题

## Roadpoints
- [x] 复核 New Agent 页面、allowlist selector、默认 prompt 来源、默认 model 输入链路与相关测试，锁定这组问题的共同根因与改动面。
- [x] 修复 Skills Allowlist 空白的根因：让 `personal_assistant` 产品配置兼容当前运行环境的 skill roots，真实 API 能返回可选 skill 列表。
- [x] 收口 Agent 创建页与详情页的 allowlist 呈现：Tool Allowlist 以短名称为主，移除冗长描述作为主文本，同时保留不可用项兼容提示。
- [x] 让 New Agent 页面从产品侧 `personal_assistant` 默认模板预填 System Prompt，而不是依赖前端硬编码或空值。
- [x] 将默认模型输入改为基于后端实时可用模型列表的选择器，只提供当前环境有效值，并暴露平台默认模型。
- [x] 补齐前后端测试与前端构建验证，覆盖 allowlist options API、create/detail/edit 页面行为、默认模型与默认 prompt 回显。
- [x] 用真实运行中的 IM 页面与 API 做一轮核对，记录浏览器截图、快照和接口响应证据。
- [x] 完成提交并 push 到 `main`；不修改 `data/dev-tasks.json`。

## Scope guard
- 仅收口 M181 这组高度相关的 Agent 创建页问题：skills 空白、tool 文案过长、system prompt 未预填、默认模型无效。
- 不顺手扩展其他设置页需求，不修改 `data/dev-tasks.json` 状态。
