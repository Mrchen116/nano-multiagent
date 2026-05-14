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
- Commits: C1=3f8d51a9, C2=f0824627, C3=c2c29b6b
- Next: R2 — 删除 app.py WS ?user_id= legacy fallback

### R2 — 删除 app.py WS ?user_id= legacy fallback

- Context: M1 R5 实现 WS JWT auth 时，注释里承诺"M2 worker tests 不 break，unit lands 前删除"。M11 修完已到 unit 合并前最后阶段，fallback 仍未删。4 个测试文件直接连接 `?user_id=` 也是同期遗留。
- Decision: 删除 `app.py:user_stream_websocket` 中 `else` 分支（`?user_id=` 路径）；更新 4 个使用旧 fallback 的测试文件（test_events_contract.py、test_events_sse_api.py、test_messages_api.py、test_human_chat_sse_e2e.py）改用 `?token=`。
- Rationale: WS 只接受 `?token=<jwt>` 是 M1 R5 的设计意图。legacy fallback 完全绕过 auth，是安全漏洞。测试文件已有 `access_token`，只需替换 query param。
- Evidence:
  - Tests: `pytest tests/im_service/ --timeout=30` — 207 passed (vs 基线 203 passed)，新增 1 个拒绝 `?user_id=` 用例，修复 4 个原本依赖 fallback 的用例；剩余 8 failures (m103×5, m136×3) 均为 pre-existing `_FakeKernelClient` 问题，与本修复无关
  - Entry: 真实 HTTP TestClient WS 连接，`?user_id=xxx` 触发 5s timeout → pytest-timeout FAILED 转 PASSED（fallback 删除后正确拒绝）
- Rollback: 205176a5 (C1)
- Commits: C1=205176a5, C2=950ff61f, C3=TBD
- Next: M12 完成，合并到 unit 分支

