# feat-333-M6 Progress

## R1 — 集成测试 (Red)

- Context: PermissionBroker 存在但从未被 app.py 实例化，runtime._build_hook_context 也未注入 permission_requester。_handle_ask 因 ctx.request_permission 为 None 而 fail-closed deny。
- Decision: 先写集成测试证明缺失，再写实现让测试变绿。
- Rationale: TDD 顺序保证测试真正覆盖了装配缺口。
- Evidence:
  - Tests: 见 tests/integration/test_permission_broker_e2e_integration.py
  - Entry: 测试在 R1 阶段因缺少 broker 注入而 Red
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 落地集成测试
  - Visual/Interaction: N/A
- Rollback: HEAD before R1 commit
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: R2 implement

## R2 — 实现：app.py + runtime 注入

- Context: 需要在 app.py 创建 PermissionBroker 并赋值 app.state.permission_broker；在 runtime._build_hook_context 构建 permission_requester 回调（broker.register_request + session_event_publisher emit permission_request + await future）并注入 HookContext。
- Decision: PermissionBroker 在 create_app() 中实例化（使用默认 AutoModeConfig），赋值到 app.state.permission_broker。runtime 接受可选 permission_broker 参数，_build_hook_context 用它构建 permission_requester。
- Rationale: 与 session_event_publisher 的注入模式一致；broker 单例在 app 级共享，runtime 持有引用。
- Evidence:
  - Tests: pytest tests/integration/test_permission_broker_e2e_integration.py - PASS
  - Entry: HTTP POST /v1/sessions/{sid}/permissions/{request_id} 真实路由
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 集成测试两条路径（allow/deny）均绿
  - Visual/Interaction: N/A
- Rollback: C1 commit
- Commits: C1=<R1>, C2=<R2>, C3=<pending>
- Next: R3 e2e验证

## R3 — E2E 验证 + 截图

- Context: 集成测试绿后需要真实 IM 端到端验证。
- Decision: 启动 IM(8011) + PA + Coding API，用 nano/nano1234 登录，让 agent 执行 rm -rf /tmp/test-fff，触发 ask → 权限卡片 → Allow once / Deny。
- Rationale: 退出标准要求真实截图证据。
- Evidence: (待补充)
- Rollback: C2 commit
- Commits: C3=<pending>
- Next: DONE
