# M6 — fix-persistence-gating-create: Tasks

## 目标

修复 acceptance round 2 的 3 个 fail issue：
1. ISSUE-2 (blocking): IM 重启后 features/custom_prompt 丢失 — Gateway `node.register` 注册时 upsert_profile 覆盖已有字段
2. ISSUE-3 (major): memory_curation on/off preview 仍相同 — promptPreview 未传 tool_ids，has_tool() 始终返回 False
3. ISSUE-1 (blocking): create 页 Features 开关组渲染不出 — NodeCapabilitiesResponse 不含 features 字段

## 退出标准

- 编辑→保存→重启 IM+Gateway→GET /config 能读回 features+custom_prompt（端对端 HTTP 证据）
- 带 memory 工具 agent，memory_curation true→preview 含 memory_guidance 段、false→不含（curl 证据）
- 新建 agent 页面 Features 开关组可见（截图证据）
- pytest 相关测试全绿

## 测试策略

- ISSUE-2: 补测 upsert_profile 在 existing profile 时保留 features/custom_prompt；集成测试复现重启丢失场景
- ISSUE-3: 补测 promptPreview API 传 tool_ids 使门控生效
- ISSUE-1: 补测 NodeCapabilitiesResponse 含 features；前端浏览器验收截图

## 前端 UI 状态矩阵 (ISSUE-1)

| 状态 | 覆盖 |
|---|---|
| create 页加载后 Features 可见 | 是 |
| features 按 default_on 预设 | 是 |
| disabled 态（缺工具） | N/A (新建无工具) |
| mobile viewport | N/A (不改样式) |

## 用户路径分类

- ISSUE-1 create page Features: bug-regression — 需补 regression case
- ISSUE-2 持久化: bug-regression — 补 repo 层测试
- ISSUE-3 门控: bug-regression — 补 preview API 端到端测试

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | 补红测试: ISSUE-2 upsert 覆盖问题 + ISSUE-3 tool_ids 门控 + ISSUE-1 node caps features | DONE |
| R2 | 修复: ISSUE-2 _handle_register 保留已有 features/custom_prompt；ISSUE-3 前端传 tool_ids；ISSUE-1 NodeCapabilitiesResponse 加 features | DONE |
| R3 | 端对端验收(TestClient HTTP + Python script)+ 文档 | DONE |
