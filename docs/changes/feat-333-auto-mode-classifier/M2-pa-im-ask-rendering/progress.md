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
