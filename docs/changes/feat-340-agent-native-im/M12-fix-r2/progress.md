# M12-fix-r2 Progress

## 基线

- Frontend: 52 test files / 236 tests 全绿
- Backend: `tests/im_service/integration/test_user_stream_auth.py` 3 passed

### R1 — zh.json shell.tabs.agents 翻译修复

- Context: M11 R5 补 i18n 时只改了 `settings.nav.agents`，漏了 `shell.tabs.agents`，验收截图可见顶栏仍显示英文 "Agents"。
- Decision: 直接将 `zh.json` line 34 `shell.tabs.agents` 改为 "智能体"；补测试断言整个 `shell.tabs.*` namespace 无漏翻 key。
- Rationale: 单行修改，范围精确；同时覆盖 `chat`/`agents`/`me` 三个 key 确保以后不会再漏。
- Evidence:
  - Tests: `npx vitest run` — 52 files / 238 tests passed (新增 2 个 i18n 断言)
  - Entry: vitest 中直接调用真实 i18n 翻译函数，验证 zh 模式下返回 "智能体"
- Rollback: 3f8d51a9 (C1)
- Commits: C1=3f8d51a9, C2=f0824627, C3=TBD
- Next: R2 — 删除 app.py WS ?user_id= legacy fallback

