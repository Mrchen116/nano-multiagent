# feat-379-M9: fix-feature-tool-coupling — tasks

## 目标

修复 dogfood 发现的 3 个缺陷，使特性↔工具联动、从零可达、新建页预览三个场景全部可用。

## 退出标准

1. `PYTHONPATH=src python3 -c "from personal_assistant.reporter.upstream_reporter import _build_tool_names; print(_build_tool_names())"` 输出含 `memory` 和 `skill_manage`
2. `POST /im/v1/nodes/{node_id}/prompt-preview` curl 可达、不依赖既有 agent、返回组装串
3. detail 页和 create 页特性 checkbox 无禁用态（不再 `disabled=!feat.available`）
4. 勾特性 → 对应工具即时在 allowlist 变绿；移除工具 → 对应特性即时取消
5. create 页展开「完整系统提示词预览」不报 404
6. `npm run test` + `npm run build` 通过
7. 全量与 main diff 0 新增失败

## 测试策略

- R1（决策 13）: 单测 `_build_tool_names()` 返回含 memory/skill_manage；contract 测试 capabilities.tools 含所有 FEATURE_REGISTRY requires_tool
- R2（决策 11）: 集成测试 node 级预览 HTTP 端点（MockGateway round-trip，不依赖真实 agent）
- R3（决策 12/14）: 前端联动 helper 单测（勾特性→加工具、移工具→取消特性、取消特性→不动工具）；后端 PATCH 兜底测试；真实浏览器验证联动 + 两页预览加载

## UI 状态矩阵

| 状态 | 适用性 |
|---|---|
| default（特性可勾） | 适用——特性无禁用态 |
| loading（预览加载中） | 适用 |
| error（预览失败） | 适用 |
| feature checked | 适用——联动加工具变绿 |
| feature unchecked | 适用——工具保留不变 |
| tool removed | 适用——对应特性取消 |
| create page (agent 未存在) | 适用——预览可加载 |
| mobile viewport | N/A（本 milestone 不改布局） |
| dark mode | N/A |

## 前端路径分类

- `critical-path`: 特性↔工具联动（两页共用）+ 新建页预览加载 → 必须真实浏览器验收
- `bug-regression`: effectiveToolIds 删除 + disabled 移除 + node 级预览 → 落 regression 保护

## Roadpoints

| R | 标题 | 状态 |
|---|---|---|
| R1 | 修 _build_tool_names（决策 13）—— capabilities.tools 含 memory/skill_manage | ✓ DONE |
| R2 | 新增 node 级预览链路（决策 11）—— IM POST /nodes/{id}/prompt-preview + Gateway WS + 前端调用 | DONE |
| R3 | 前端联动 helper + 移除 disabled + 删 effectiveToolIds（决策 12/14）+ 后端 PATCH 兜底 | DONE |
