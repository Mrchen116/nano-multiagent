# feat-379-M3 progress

## 初始化

- 基线测试: 2 failed / 328 (token-chip R8-3 + policies-page — 与本 M3 无关的既存失败)
- 既存失败 commit: a7b02d1e (M1 结束)

---

## C1 — 红测 (5ad7038a)

4 failing:
- agent-detail-page.test: 3 new M3 tests (BehaviorCard 不存在)
- agent-edit.test: 1 (System Prompt label 被移除)

## C2 — 实现 (169392b2)

变更文件: im-agent-config-api.ts, agent-detail-page.tsx, agent-create-page.tsx, agent-edit.test.tsx, agent-create.test.tsx, i18n/en.json, i18n/zh.json

最终测试: 2 failed / 334 (仅剩既存 token-chip R8-3 + policies-page)

`npm run build`: tsc 0 error，vite build success (535kB bundle)

browser self-test: IM (127.0.0.1:53163) + Vite (127.0.0.1:53164) 起服务，
Vite proxy → IM login 200，注册账号成功，API 链路通。
无 agent 节点在此测试环境中（纯 IM，无 Gateway），Behavior card 在 agent detail
页面需有 agent 配置才可见，单元测试已覆盖三态 checkbox + collapsible preview。

---
