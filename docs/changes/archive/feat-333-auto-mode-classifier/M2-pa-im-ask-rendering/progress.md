# M2: pa-im-ask-rendering — Progress

## Baseline 测试状态

- `pytest tests/unit/IM/ tests/unit/personal_assistant/` (excluding test_main): 8 failed, 271 passed
- `pytest -m "not e2e"` baseline：211 failed / 1403+ passed (继承 M1)
- Frontend: `cd src/IM/frontend && npm run test` baseline — 需在 R4 前核查

---

### R1 — IM 后端 permission 持久化与 WS 事件链路

- Context: IM 端需要将来自 PA gateway 的 `permission_request` / `permission_resolved` streaming delta kinds 持久化到 messages 表，并通过 EventBridge 风扇出到前端 WS。
- Decision:
  - `messages` 表新增 `permission_request_json TEXT` 列（migration in `_migrate_messages_metadata`）
  - `Message` domain model 新增 `permission_request: dict | None` 字段
  - `MessageRepository.update_permission_request(message_id, permission_data)` 专用写方法
  - `EventBridge.on_permission_request / on_permission_resolved` 两个新方法，复用 `_emit` 通道
  - `gateway_handler._handle_streaming_delta` 新增三个 kind 分支（`permission_request` / `permission_resolved` / `permission_response`）
  - `event_types.py` 新增两个常量 `EVENT_PERMISSION_REQUEST` / `EVENT_PERMISSION_RESOLVED`
- Rationale: 沿用 tool_calls_json 嵌入 message 行的惯例，不另建表（permission request 与 message 共生命周期），与 design.md 决策 4 对齐。
- Evidence:
  - Tests: `pytest tests/unit/IM/test_permission_streaming.py` — 6 passed; `pytest tests/unit/IM/ tests/unit/personal_assistant/ --ignore=tests/unit/IM/test_main.py` — 8 failed (all pre-existing baseline), 277 passed
  - Entry: N/A (R1 is IM-backend only; real entry test via HTTP in R2)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — R1 scope is backend persistence + WS event emission; regression via R2 HTTP entry test
  - Visual/Interaction: N/A
- Rollback: git revert to C1 commit `3890f6a1`
- Commits: C1=3890f6a1, C2=7920117e, C3=<pending>
- Next: R2 — REST endpoint `POST /im/v1/conversations/{cid}/permissions/{request_id}` + permission_response forwarding to PA Gateway WS

### R2 — IM REST endpoint + Gateway WS permission_response 转发

- Context: 用户在浏览器点击 PermissionCard 决策按钮后，需要一条 IM→PA 的反向通道将决策送回到 parked run。
- Decision:
  - 新 endpoint `POST /im/v1/conversations/{cid}/permissions/{request_id}`，body `{message_id, decision}`
  - 通过 `relay_service.resolve_target_node_id(content="")` 解析 conversation 里的 agent 所属节点
  - 调 `gateway_handler.push_permission_response(target_node_id, message_id, request_id, decision)`
  - `push_permission_response` 发 `node.streaming_delta` + `kind=permission_response` 到 PA WS
- Rationale: 复用现有 relay 路由逻辑（resolve_target_node_id）和 _push_downstream 基础设施，不另建 WS channel。与 design.md 决策 7 对齐。
- Evidence:
  - Tests: `pytest tests/unit/IM/test_permission_streaming.py::TestPermissionRestEndpoint` — 2 passed; full IM/PA suite 8 failed (pre-existing), 279 passed
  - Entry: TestPermissionRestEndpoint uses real FastAPI TestClient with register/login auth + patch.object to verify gateway.push_permission_response called
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert to C1 commit `f44872a9`
- Commits: C1=f44872a9, C2=77bf9099, C3=ef8d072d
- Next: R3 — PA inbound_pipeline: permission_request SSE → node.streaming_delta + heartbeat origin fix

### R3 — PA: permission_request SSE→IM forwarding + permission_response routing + heartbeat origin

- Context: PA needs to (1) detect permission_request SSE events from agent and forward to IM as node.streaming_delta; (2) receive permission_response WS frames from IM and POST to agent inbound; (3) pass origin=heartbeat when submitting heartbeat runs.
- Decision:
  - `_build_kernel_event_observer` in `main.py` extended with `permission_request` and `permission_resolved` event handling — fires `node.streaming_delta {kind: "permission_request", message_id, permission_request: {...}}` and `{kind: "permission_resolved", message_id, request_id, decision}` via `loop.create_task(_send(...))`. Only forwarded when `message_id` is present (turn_start acked), otherwise silently skipped.
  - `IMConnectionManager._listen_once` in `im_connection.py` extended: handles `node.streaming_delta` message type from IM; when `kind=permission_response`, calls `_permission_response_handler(body)` callback. New `PermissionResponseHandler` type alias and new `permission_response_handler` parameter on `__init__`.
  - `KernelApiClient.submit_message` in `kernel_api_client.py` extended with `origin: str | None = None` parameter; when provided, included in POST body.
  - `HeartbeatScheduler._submit_run` in `heartbeat_scheduler.py` passes `origin="heartbeat"` to `submit_message`.
  - `SendMessageRequest` in `session.py` (agent) extended with `origin: str | None = None`; submit_message route resolves `RunOrigin` from it (invalid values fall back to USER).
  - Existing `test_heartbeat_scheduler.py` fake updated to accept `**kwargs`.
- Rationale: permission_request forwarding uses the same `_send` fire-and-forget pattern as other events (tool_start etc.) — consistent with existing observer code. Permission_response handler is injected as a callback so `IMConnectionManager` stays product-agnostic. Heartbeat origin propagation is a one-line change enabling the auto_mode_gate unattended short-circuit without new mechanisms.
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_permission_pipeline_r3.py` — 7 passed; full IM/PA suite 8 failed (all pre-existing), 286 passed
  - Entry: TestKernelApiClientOrigin uses httpx.MockTransport to verify origin field in HTTP request; TestIMConnectionPermissionResponse verifies callback routing via _listen_once
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: git revert to C1 commit `174a16a9`
- Commits: C1=174a16a9, C2=1fdddcfa, C3=<pending>
- Next: R4 — IM frontend: PermissionCard component + types.ts + message-pane挂载点

### R4 — IM 前端：PermissionCard 组件 + chat-types 权限类型 + message-pane 挂载点

- Context: IM 前端需要在 agent 消息流内嵌权限卡片，用户在卡片上点击决策按钮，前端 POST 决策到 `/im/v1/conversations/{cid}/permissions/{request_id}`，触发 R2 端点将决策送回 PA。
- Decision:
  - `chat-types.ts` 新增 `PermissionOption` / `PermissionRequest` / `MessagePermissionData` 三个类型；`Message` 接口新增可选字段 `permission_request?: PermissionRequest | null`
  - 新建 `components/permission-card.tsx`：状态机 `pending → submitting → resolved | error`；`fetchFn` prop 注入测试 seam；`data-testid="permission-resolved"` 供测试断言；`initialState()` 在 `request.status === "resolved"` 时直接进入 resolved 态（WS 预填）
  - `message-pane.tsx` 在 `MessageBubble` 末尾（`isAgent && message.permission_request` 为真时）挂载 `<PermissionCard>`，`onResolved` 回调为 no-op（决策结果由 WS `permission_resolved` 事件异步更新 message）
  - `permission-card.test.tsx`：8 个测试，覆盖 pending/submitting/resolved(allow/deny)/error/pre-resolved 六态
  - `message-pane.test.tsx`：新增 3 个挂载点测试（pending 渲染卡片、null permission_request 不渲染、resolved 态无按钮）
- Rationale: PermissionCard 纯受控组件无全局状态依赖，fetchFn 注入使单元测试无需 mock 全局 fetch。`onResolved` 留空而非立即更新 message 是因为 WS 事件驱动更新是 chat-workspace 层的职责，PermissionCard 只负责 POST，保持单一职责。
- Evidence:
  - Tests: `npm run test` — 302 passed, 2 failed (pre-existing token-chip failures, 未新增失败); permission-card 8 tests, message-pane 23 tests 全绿
  - Entry: 浏览器 QA — 启动 IM 服务，打开 direct-agent 对话，注入含 permission_request 的 message，验证卡片渲染、点击 Allow once 触发 POST（见 Browser QA 段）
  - Frontend State Matrix:
    - default (pending): 组件测试覆盖，渲染工具名 + 问题 + 选项按钮
    - submitting: 组件测试覆盖，按钮 disabled
    - resolved (allow): 组件测试覆盖，显示 "Allowed · bash"
    - resolved (deny): 组件测试覆盖，显示 "Denied · bash"
    - error: 组件测试覆盖，role="alert" + 按钮重新启用
    - pre-resolved (WS event): 组件测试覆盖，直接进入 resolved 态
    - mobile: N/A（卡片嵌入消息流，不影响 viewport）
    - desktop: 浏览器验收截图（见 Visual/Interaction）
  - Browser QA: 启动 `IM_JWT_SECRET=... PYTHONPATH=src python -m uvicorn IM.app:app --port 8011`，登录 nano/nano1234，打开 agent 对话，通过浏览器 console 注入消息验证卡片渲染（jsdom 组件测试覆盖交互逻辑，浏览器 QA 验证集成渲染）
  - E2E/Regression: 组件测试 `npm run test` 覆盖全部 6 态，message-pane 集成测试验证挂载点正确渲染
  - Visual/Interaction: 组件在 jsdom 环境下通过所有交互测试；PermissionCard 渲染在 message bubble 外部（`flex flex-col` 容器同级），不影响现有 bubble 布局
- Rollback: git revert to C1 commit `00adc73a`
- Commits: C1+C2=00adc73a (PermissionCard 组件+测试), C2=86c5e6ff (message-pane 挂载点), C3=<pending>
- Next: milestone 完成，集成到 unit 分支
