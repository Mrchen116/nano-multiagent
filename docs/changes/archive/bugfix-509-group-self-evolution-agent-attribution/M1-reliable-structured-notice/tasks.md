# M1 reliable-structured-notice

## Roadpoints

- [x] Red/Green: Gateway callback retains Agent/session/sequence identity, sends the structured notice with awaited ACK, and contains delivery failure to a warning.
- [x] Red/Green: IM validates authenticated node/profile/conversation membership, snapshots the profile name, normalizes targets, and persists the notice idempotently.
- [x] Red/Green: nullable SQLite migration, REST history, canonical `message.created`, and duplicate replay all expose one consistent notice/message identity.
- [x] Red/Green: direct-chat fork copies the persisted notice snapshot exactly while legacy messages remain nullable.
- [x] Run the focused Gateway/IM regression suite and preserve real-stack evidence.

## 测试策略

- 保护的回归风险与可观察 seam: Gateway business frame loses source/targets or retry identity; IM accepts spoofed source, duplicates a replay, drops live/history sidecar, or fork loses the sidecar. Observe at callback payload/ACK, IM handler + persisted message/event, REST response, and forked history.
- 已有保护与处置: extend existing files listed below; no parallel milestone-named test file. Existing caller idempotency, ordinary system-message compatibility, and rich fork-copy coverage remain `keep`.
- 落层/目录/marker: `tests/unit/personal_assistant/` and `tests/im_service/{unit,integration}/`, marker: none. These are the lowest public seams that expose each failure; the real process/browser journey remains one-time evidence.
- 文件归属: extend existing behavior-owner tests; no optional test dependency.
- 可选依赖 importorskip: none.
- 本 milestone 产生的一次性验收证据: real-stack browser/protocol observations under `evidence/`; no temporary `test_*.py`.

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| subscription identity | `tests/unit/personal_assistant/test_background_subscription_manager.py` | rewrite-merge | Callback contract changes from two to four arguments; keep subscriber lifecycle coverage while asserting stable request identity. | focused pytest |
| structured awaited delivery | `tests/unit/personal_assistant/test_external_visible_delivery.py` | rewrite-merge | Existing fixed-English fire-and-forget assertion protects the superseded wire shape; update it to the public business-frame contract and failure boundary. | focused pytest |
| legacy system message | `tests/unit/personal_assistant/test_background_session_events.py` | keep | Still protects optional-sidecar compatibility. | focused pytest |
| source trust owner | `tests/im_service/unit/test_gateway_conversation_persistence.py` | rewrite-merge | Extend the existing persistence seam; do not duplicate profile/user/conversation setup elsewhere. | focused pytest |
| handler/replay/live event | `tests/unit/personal_assistant/test_background_session_events.py` | rewrite-merge | The existing Gateway frame-handler seam exposes validation, idempotency and created-event behavior together. | focused pytest |
| schema migration | `tests/im_service/unit/test_db_init.py` | rewrite-merge | Existing metadata migration test is the lowest migration seam. | focused pytest |
| Message round-trip | `tests/im_service/unit/test_repositories_message.py` | rewrite-merge | Existing repository round-trip is the owner for the new nullable sidecar. | focused pytest |
| REST history | `tests/im_service/integration/test_messages_api.py` | rewrite-merge | API serialization must preserve the same notice snapshot. | focused pytest |
| fork rich sidecars | `tests/im_service/unit/test_fork_conversation_edges.py` | rewrite-merge | Extend current complete-bubble copy risk instead of a new fork test file. | focused pytest |
