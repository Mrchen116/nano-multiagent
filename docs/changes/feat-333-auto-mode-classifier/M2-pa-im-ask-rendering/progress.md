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
