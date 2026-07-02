# feat-447-M11 — Progress

## Baseline

- Context: M11 在 `unit/feat-447` 基础上实现 external live parity，涉及 Gateway reply mirror、IM live event payload、frontend reducer 和 Feishu reaction lifecycle。
- Evidence:
  - `pytest -q tests/unit/test_feishu_adapter_send.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_integration.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_gateway_im_relay.py tests/im_service/integration/test_messages_api.py` -> 76 passed, 1 skipped.

## R1 — IM live `message.created` payload

- Context: 外部 channel 用户消息由 Gateway 调 IM `POST /im/v1/conversations/{id}/messages` 写入，且设置 `suppress_relay=true`；此前该路径只产生 `message.sent` / `message.delivered`，打开的 shadow 会话无法用前端 canonical `message.created` 插入新气泡。
- Decision: `MessageRepository.create_message` 增加默认关闭的 `emit_created_event` 开关；messages API 在 `suppress_relay=true` 时开启它，按 `message.sent` -> `message.created` -> `message.delivered` 顺序写入 events。`message.created` payload 增加 `sender`、`sender_display_name`、`attachments`，并保留 delivery/progress events 的现有语义。
- Rationale: 外部同步写入没有浏览器 optimistic insert，因此必须由服务端发完整 live insert 事件；普通浏览器发消息和 relay-backed 写入不自动开启 `message.created`，避免改变已有提交/投递状态机。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_ws_event_types.py::test_build_message_created_payload_carries_external_insert_fields tests/im_service/integration/test_messages_api.py::test_external_find_or_create_and_message_display_name_roundtrip` 先红，失败点为缺 `attachments` 和缺 `message.created`；实现后 `pytest -q tests/im_service/unit/test_ws_event_types.py tests/im_service/unit/test_repositories_message.py tests/im_service/integration/test_messages_api.py` -> 43 passed, 1 skipped。
  - Entry: FastAPI `POST /im/v1/conversations/external/find-or-create` + `POST /im/v1/conversations/{id}/messages` 集成测试覆盖外部 shadow API 写入，断言 DB `conversation_events` 有 canonical `message.created` payload。
  - Frontend State Matrix: default/empty/missing data 的后端 payload 已可支持；前端 reducer 行为在 R2 覆盖。
  - Browser QA: N/A，R1 是 backend live event payload；真实浏览器/live path 在 R4。
  - E2E/Regression: `tests/im_service/unit/test_ws_event_types.py::test_build_message_created_payload_carries_external_insert_fields`；`tests/im_service/integration/test_messages_api.py::test_external_find_or_create_and_message_display_name_roundtrip`。
  - Visual/Interaction: N/A。
- Rollback: revert `0b7d974d` 后再 revert `bf89fd25` 可回到 R1 前状态。
- Commits: C1=`bf89fd25`, C2=`0b7d974d`, C3=<pending>
- Next: R2 前端 reducer 使用 `message.created` payload 的 sender display name 并去重。

## R2 — 前端 reducer display name 与去重

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix:
  - Browser QA:
  - E2E/Regression:
  - Visual/Interaction:
- Rollback:
- Commits:
- Next:

## R3 — Gateway external reply mirror 与 reaction lifecycle

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix:
  - Browser QA:
  - E2E/Regression:
  - Visual/Interaction:
- Rollback:
- Commits:
- Next:

## R4 — live-critical 与全量门禁

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
  - Frontend State Matrix:
  - Browser QA:
  - E2E/Regression:
  - Visual/Interaction:
- Rollback:
- Commits:
- Next:
