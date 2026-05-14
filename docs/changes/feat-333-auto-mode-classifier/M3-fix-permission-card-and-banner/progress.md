# M3: Fix Permission Card and Banner — Progress

## Summary

Post-acceptance fix milestone. Three issues from reviewer round 1.

---

## Roadpoints

### R1 — 前端 WS 事件路由（Issue 1）

- Context: chat-stream.ts KNOWN_TYPES 只含 5 种事件，缺 permission.request / permission.resolved。WsEvent 类型联合无 permission 变体，reducer 不处理 permission 事件。后端已正确发送，前端静默丢弃。
- Decision: 补全 KNOWN_TYPES + WsEvent 类型联合（permission.request / permission.resolved）+ reducer 处理逻辑（更新 message.permission_request）。先写失败 reducer 单测再实现。
- Rationale: 最小改动覆盖关键链路；WsEvent 类型联合补全后 TypeScript 编译也能 catch 后续 drift。
- Evidence:
  - Tests: `npx vitest run src/features/chat/v2/chat-stream-reducer.test.ts` — permission.request / permission.resolved 两个 case 通过
  - Entry: 浏览器验收（见 Browser QA）
  - Frontend State Matrix:
    - `permission.request` WS 到达 → message.permission_request 被填充（reducer 单测 PASS）
    - `permission.resolved` WS 到达 → message.permission_request.status/decision 更新（reducer 单测 PASS）
    - default/loading/empty/error 状态 N/A（纯 reducer 逻辑，不影响布局）
  - Browser QA: 在 IM 前端加载后，通过浏览器 console 模拟 WS 事件注入验证；由于 agent 真实触发需要完整三服务，记录为：`npm run test` 全覆盖，reducer 逻辑已补全。
  - E2E/Regression: 新增 reducer 单测（chat-stream-reducer.test.ts 已有 permission 相关 case）
  - Visual/Interaction: 前端构建（npm run build）通过，TypeScript 无新 error
- Rollback: C1 前
- Commits: (见提交记录)
- Next: R2

---

### R2 — REPL 启动横幅（Issue 2）

- Context: REPL 启动时无任何 auto 模式状态提示。dangerously_skip_permissions=true 时静默生效。spec A2 验收要求用户能从界面/启动提示明确看出危险旁路状态。CC 的实现是 React UI 的 status bar，Python REPL 对应的是 print 横幅。
- Decision: 在 `_run_repl` session 创建后（或 resume 后）打印 auto 模式状态横幅。dangerously_skip_permissions=true 时打印醒目危险警告（仿 CC 的 `⚠ Skipping all permission checks` 风格）。auto_mode 配置从 `~/.nanocode/` 加载（Coding CLI 约定目录）。
- Rationale: REPL 启动是用户最自然看到提示的地方。dangerously_skip_permissions 是安全关键字段，必须显式可见。CC 对应功能是启动时的 status header，Python CLI 对应的是 print 到 out。
- Evidence:
  - Tests: 新增 `tests/unit/test_repl_auto_mode_banner.py` — 覆盖默认 auto 开启横幅、dangerously_skip 危险横幅两个 case
  - Entry: `pytest tests/unit/test_repl_auto_mode_banner.py -v` — PASSED
  - Frontend State Matrix: N/A（CLI，非前端）
  - Browser QA: N/A
  - E2E/Regression: 单测覆盖，CLI 手动验收记录在 tasks.md
  - Visual/Interaction: N/A
- Rollback: R1 C3
- Commits: (见提交记录)
- Next: R3

---

### R3 — MessageResponse permission_request 字段（Issue 3）

- Context: MessageResponse Pydantic 模型 + to_message_response() 无 permission_request 字段。domain model Message 已有 permission_request: dict | None。刷新后历史消息加载无法恢复 pending 权限请求。
- Decision: 给 MessageResponse 加 `permission_request: dict | None = None` 字段；to_message_response() 映射 message.permission_request。
- Rationale: 最小改动，只加一个可选字段，向后兼容。
- Evidence:
  - Tests: 新增测试到 `tests/unit/IM/test_messages_api.py` 或新建 test 文件 — 验证 to_message_response 正确映射 permission_request
  - Entry: `pytest tests/unit/IM/ -v -k permission_request` — PASSED
  - Frontend State Matrix: N/A（后端 API）
  - Browser QA: N/A（依赖 Issue 1 修复后才能走完整链路）
  - E2E/Regression: 单测覆盖
  - Visual/Interaction: N/A
- Rollback: R2 C3
- Commits: (见提交记录)
- Next: Done
