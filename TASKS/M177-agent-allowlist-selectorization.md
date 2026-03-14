# M177 - Agent 配置 Allowlist 选择器化

## Roadpoints
- [x] 阅读 agent 配置页、allowlist、system prompt 表单、相关 API 与测试，确认当前手写字符串链路和最小改动面。
- [x] 为 IM agent config API 增补“当前系统可用 skills/tools”选项接口，保证返回结果可供真实页面直接渲染选择器。
- [x] 将 Agent 创建页的 Skills Allowlist / Tool Allowlist 从手写字符串改为可选择交互，禁止自由手写并保持 payload 仍为 `string[]`。
- [x] 将 Agent 详情页的 Skills Allowlist / Tool Allowlist 改为同类选择交互，确保编辑已有 agent 时正确回显、保存并对不可用旧值做兼容展示。
- [x] 补齐最小有效前后端测试，覆盖选项接口、创建页选择提交、详情页回显与保存。
- [x] 做一轮可复现验证并把自动化证据持续写入 PROGRESS；本轮以真实构建与前后端测试为主，若后续环境具备浏览器验收条件可继续补充真机证据。
- [ ] 完成提交、合并 main、清理 M177 worktree。

## Scope guard
- 仅完成 M177：allowlist 选择器化与保存/编辑链路验证。
- 不顺手实现 M178 默认 prompt 模板。
- 不修改 `data/dev-tasks.json`。
