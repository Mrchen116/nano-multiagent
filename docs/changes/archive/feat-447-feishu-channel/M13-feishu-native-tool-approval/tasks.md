# feat-447-M13 — Feishu Native Tool Approval Tasks

## Scope

- [x] Move Feishu channel implementation into `src/personal_assistant/channels/feishu/` with compatibility shims for old imports.
- [x] Add Feishu interactive card send/update and card action callback support.
- [x] Add Feishu approval pending state with `approval_id -> request_id` mapping, owner/chat/option/TTL validation, and resolved-card update.
- [x] Mirror kernel `permission_request` to Feishu when the run was triggered by Feishu, while preserving the existing IM permission card.
- [x] Route Feishu card decisions through the existing `kernel.submit_permission_decision` handler and first-wins behavior.
- [x] Cover Feishu client, adapter approval, and Gateway observer behavior with focused unit tests.

## Out Of Scope

- No runtime `lark-cli` dependency; `lark-cli` remains a reviewer/live-test tool only.
- No generic multi-channel permission framework yet; package-local Feishu surface comes first, shared protocol can be extracted after another channel repeats the shape.
- No group-admin or sender-based approval policy; M13 only allows the bound owner open_id.
