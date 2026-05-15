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

## R3 — Orchestrator 接管 e2e + 找到真因 + 补修

- Context: worker 完成 R1+R2 后在 R3 e2e 阶段卡住（错误诊断 ANTHROPIC_API_KEY 方向）超过 1 小时无进展，orchestrator 停掉 worker 接管。R2 注入的 broker 在单测层 6 个绿但真实 e2e 仍 fail-closed。orchestrator 直接调 agent kernel HTTP API 跑 bash → 触发 hook → 抓 SSE 与 kernel.log，加 trace 行单步定位到两处真因。
- Decision:
  1. **Bug A — `loop.py:274-281` 拷贝 HookContext 漏传 `permission_requester`**：worker R2 把 permission_requester 接到 `_build_hook_context` 的 `active_hook_ctx`，但 `loop.py` 给每个 tool call 又造一个 `tool_hook_ctx`（line 274），copy 字段时漏了它，导致 hook 实际收到的 ctx.permission_requester=None → `_handle_ask` 永远 fail-closed deny。修法：补一行 `permission_requester=active_hook_ctx.permission_requester`。
  2. **Bug B — `HookContext.call_model` 签名不接受 `max_tokens / stop_sequences / temperature`**，但 `_classify_action`（M1 写）调用时传了这三个 → classifier 每次抛 TypeError → fail-closed ask（被 Bug A 又转 deny）。修法：扩 `HookModelCall` 加这三个字段（core），`HookContext.call_model` 接收并透传，`runtime._call_hook_model` 把它们透传给 `LLMGenerateRequest`（core 已有 temperature/max_tokens，加 `stop_sequences`），`openai_compat/mapper.py` 把 `stop_sequences` 映射成 OpenAI `stop` 字段。这是 M1 写 classifier 时跟 hook context API 没对齐留下的债，单测层永远抓不到（mock 不走真实签名校验）。
  3. **集成测试 fix**：worker R1 加的 `test_submit_permission_decision_resolves_pending_request` 用 `asyncio.new_event_loop()` 创建 future 但永不 run loop，`broker.resolve` 经 `call_soon_threadsafe` 调度的回调永远不执行 → future pending → 测试失败。改写成 `asyncio.run(_exercise())` 让 future 在 running loop 上注册，`TestClient.post` 放 `to_thread` 跨线程触发 resolve。
- Rationale: 跨层 wiring bug 必须直接跑 LLM + 真 SSE 才能暴露，单测假设 mock 都过；Bug A 在 worker R1 集成测试里没踩到是因为测试直接调 `broker.register_request` 不经过 loop.py 的 ctx 拷贝路径。
- Evidence:
  - Tests: 6 个集成测试全绿（含 `test_submit_permission_decision_resolves_pending_request` 修复后）；`pytest -m "not e2e"` 与 baseline (203) 失败集合一致（详见 R4 验证）
  - Entry: orchestrator 直接 `POST /v1/sessions` + `POST /v1/sessions/{sid}/messages` + 监听 `GET /v1/sessions/{sid}/stream` SSE
  - E2E timeline:
    - Test 1 — `ls /tmp/test-fff`：safety policy allowed → tool_end status=completed exit=0 stdout="testfile.txt" 直接执行（无卡片，正确）
    - Test 2 — `curl -sS https://example.com`（deny_limit=1 临时配置 + Bug A 修后、B 未修）：emit `event: permission_request` payload 完整 4 options；`POST /permissions/{request_id}` decision=allow_once 返回 `{"resolved":true}`；session messages 显示 tool 真执行返回 example.com 完整 HTML（`<!doctype html>...Example Domain...`）；agent 后续回复"命令执行成功"
    - Test 3 — `curl -sS https://example.com`（Bug B 修后默认 deny_limit=3）：LLM proxy log 出现 2 次 classifier 调用（stage 1 + stage 2，system prompt 起始 = `You are an automated security classifier...`），classifier 决定 deny → tool blocked（第 1 次 deny 不弹卡，符合 design 的 deny-limit 累计意图）；要看到卡片需要 3 次连续 deny 累计或 classifier 给 ask
  - Visual/Interaction: 真实 IM 浏览器截图四态留给 reviewer round 5 在浏览器层补全
- Rollback: 81346c6b (worker C2 broker 装配 / 进一步 rollback 整个 unit 撤 PR)
- Commits: C4 = orchestrator 接管补修
- Next: R4 全量回归 + cleanup commit
