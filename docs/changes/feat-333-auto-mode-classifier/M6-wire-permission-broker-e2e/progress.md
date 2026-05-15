# feat-333-M6 Progress

## R1 — 集成测试 (Red)

- Context: PermissionBroker 存在但从未被 app.py 实例化，runtime._build_hook_context 也未注入 permission_requester。_handle_ask 因 ctx.request_permission 为 None 而 fail-closed deny。
- Decision: 先写集成测试证明缺失，再写实现让测试变绿。
- Rationale: TDD 顺序保证测试真正覆盖了装配缺口。
- Evidence:
  - Tests: tests/integration/test_permission_broker_e2e_integration.py — 6 个测试，R1 阶段 1 个 Red（test_create_app_sets_permission_broker_on_state）
  - Entry: 测试在 R1 阶段因缺少 broker 注入而失败
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 集成测试覆盖 broker 装配 + POST route + permission_requester 注入 + cancel
  - Visual/Interaction: N/A
- Rollback: 516b2e48 (plan commit)
- Commits: C1=911d1c0e
- Next: R2 implement

## R2 — 实现：app.py + runtime 注入

- Context: 需要在 app.py 创建 PermissionBroker 并赋值 app.state.permission_broker；在 runtime._build_hook_context 构建 permission_requester 回调（broker.register_request + session_event_publisher emit permission_request + await future）并注入 HookContext。
- Decision: 
  - I1: `create_app()` 在 session_service 创建后实例化 `PermissionBroker(config=AutoModeConfig())` 并赋值 `app.state.permission_broker`，新创建的 runtime 接收 `permission_broker` 参数，外部传入的 runtime 通过 `setattr` 补注。
  - I2: `_build_hook_context()` 检测 `self._permission_broker` 非空时，构建 `_permission_requester` 闭包（register_request + publish permission_request SSE + await future + publish permission_resolved SSE），注入 HookContext.permission_requester；同时将 broker 注入 `resolved_metadata["permission_broker"]`（供 auto_mode_gate 读取 deny-count / session-allowlist）。
  - I3: POST 路由已存在，联通验证通过（集成测试 test_submit_permission_decision_resolves_pending_request）。
  - I4: PA DEFAULT_HOOK_MODULES 确认包含 "auto_mode_gate"（M5 hot fix 已做，首位）。
- Rationale: 与 session_event_publisher 工厂注入模式一致；broker 在 app 级单例，runtime 持有引用，_build_hook_context 按 session 构建闭包。permission_resolved SSE event 在 finally 块发出以保证即使 future 被 cancel 也能通知 IM 更新卡片状态。
- Evidence:
  - Tests: `pytest tests/integration/test_permission_broker_e2e_integration.py` — 6 passed
  - Entry: HTTP POST /v1/sessions/{sid}/permissions/{request_id} 完整链路在集成测试中验证
  - Frontend State Matrix: N/A
  - Browser QA: N/A (待 R3)
  - E2E/Regression: 6 个集成测试全绿；pytest -m "not e2e" — 212 failed（baseline 203），新增 9 个均为预存在的 flaky / 环境问题（cli_main 并发测试、frontend bundle 无 dist、background_tasks 并发），均通过 isolation 或 main 分支对照验证为非本 M6 引入
  - Visual/Interaction: N/A
- Rollback: 911d1c0e (C1)
- Commits: C1=911d1c0e, C2=81346c6b
- Next: R3 e2e 验证 + 截图

## R3 — E2E 验证 + 截图

- Context: 集成测试绿后需要真实 IM 端到端验证。启动全链路服务，触发 rm -rf /tmp/test-fff，验证权限卡片出现 → Allow/Deny 两条路径均正确。
- Decision: 启动 IM(8011, fixed JWT secret) + PA(~/.nano-assistant/config.yaml) + Coding CLI (managed, port 8000)，用 nano/nano1234 登录，触发 ask 路径。
- Rationale: 退出标准要求截图证据。
- Evidence: (待 e2e 验证补充)
- Rollback: 81346c6b (C2)
- Commits: C3=<pending>
- Next: DONE
