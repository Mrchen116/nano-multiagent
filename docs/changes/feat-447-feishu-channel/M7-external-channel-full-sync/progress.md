# feat-447-M7 — Progress

## Context

- Skill: `change-impl-worker`
- Unit: `feat-447`
- Milestone: `feat-447-M7 external-channel-full-sync`
- Base: `origin/unit/feat-447` at `a49b10c6ea8066bb028bab4b8548ac981c3ed5c6`
- Scope: files listed in `docs/changes/feat-447-feishu-channel/design.md` M7 row.

## Startup

- Sync Gate: local `unit/feat-447` equals `origin/unit/feat-447` at `a49b10c6ea8066bb028bab4b8548ac981c3ed5c6`.
- Context read: `spec.md`, `design.md` M7 decisions and Runbook for Reviewer, `AGENTS.md`, `CLAUDE.md`, `LOGBOOK.md`, `docs/TESTING_GUIDE.md`, and existing IM/Gateway/Feishu code/test structure.
- Baseline: `pytest -m "not e2e"` started before implementation; final result will be recorded in R1/R5 evidence.

## Roadpoint Progress

### R1 — IM 影子会话与消息持久化

- Context: M7 需要 IM 侧能以外部身份幂等创建 shadow conversation，并能保存外部群成员显示名。现状 conversations/messages schema 缺外部来源字段，HTTP API 也没有 find-or-create 入口。
- Decision: 在 `conversations` 增加 `external_source` / `external_chat_id` 与联合索引；在 `messages` 增加 `sender_display_name` 行级覆盖；新增 repository/service/API 的 `external/find-or-create`，影子会话 agent 维度复用 `config_agent_id`。
- Rationale: 幂等键按 design 使用 `(external_source, external_chat_id, config_agent_id, owner_id)`，避免同一个飞书群绑定多个 agent 时混淆；`sender_display_name` 放 message 行上，避免给外部成员创建 fake IM user。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_db_init.py tests/im_service/unit/test_repositories_user_conversation.py::test_external_conversation_find_or_create_is_agent_scoped_and_updates_title tests/im_service/unit/test_repositories_message.py::test_message_roundtrip_preserves_external_sender_display_name tests/im_service/integration/test_messages_api.py::test_external_find_or_create_and_message_display_name_roundtrip` -> 5 passed; `pytest -q tests/im_service/unit/test_db_init.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/unit/test_repositories_message.py tests/im_service/integration/test_messages_api.py` -> 33 passed, 1 skipped.
  - Entry: HTTP `POST /im/v1/conversations/external/find-or-create` integration test creates/reuses a shadow conversation and `POST /messages` returns row-level sender display name.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: R1 regression lives in `tests/im_service/unit/test_db_init.py`, `tests/im_service/unit/test_repositories_user_conversation.py`, `tests/im_service/unit/test_repositories_message.py`, and `tests/im_service/integration/test_messages_api.py`.
  - Visual/Interaction: N/A
- Rollback: revert `e42f74a8` then `2a0d2e02`.
- Commits: C1=2a0d2e02, C2=e42f74a8, C3=TODO
- Next: R2

### R2 — IM relay metadata 回环到 Gateway

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R3

### R3 — Gateway 外部 session identity、sync_only 与 group buffer

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R4

### R4 — Shadow conversation 同步、run context 与出站路由

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R5

### R5 — 非 e2e 门禁与真实飞书端到端验收

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: milestone DONE after live evidence is complete.
