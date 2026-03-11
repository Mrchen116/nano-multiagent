# M113 — IM 消息交付状态与 SSE 回执收口

## 前置阅读
- [x] 已先阅读 `/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/LOGBOOK.md`
- [x] 已先阅读 `/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`

## 当前处境
- Milestone: M113 / IM 消息交付状态与 SSE 回执收口
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M113`
- branch: `milestone/M113`
- test gate: `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/im_service -q 2>&1 | tail -80`
- allowed scope: `src/IM/**`, `tests/im_service/**`, `TASKS/**`, `PROGRESS/**`
- forbidden scope: `ROADMAP.md`、手改 `data/dev-tasks.json`
- prevention_rules:
  1. 真实入口验证优先于 TestClient happy path
  2. 先修口径一致性（REST/SSE/历史回读统一）再做扩展
  3. 若发现缺口在上游接口契约，先明确责任边界

## 基线
- [x] `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/im_service -q 2>&1 | tail -80`
- 基线结果：`9 failed, 45 passed`
- 失败摘要：`create_message/list_messages` 仍返回 `delivery_status=sent`，`/events` 缺失 `message.delivered`

## Roadpoints

### R1 修复消息持久化后的 completed 口径
- Acceptance:
  - `create_message` 返回 `delivery_status=completed`。
  - `list_messages` 历史回读统一返回 `delivery_status=completed`。
  - 同一次写消息会按顺序持久化 `message.sent` 与 `message.delivered`。
  - `/im/v1/conversations/{id}/events` 能同时回放 `message.sent` 与 `message.delivered`。
- Tests Plan:
  - unit: 复用 `tests/im_service/unit/test_event_repository.py` 与 `tests/im_service/unit/test_repositories.py`，先锁定仓储层顺序与历史回读口径。
  - contract: 复用 `tests/im_service/contract/test_messages_contract.py` 与 `tests/im_service/contract/test_events_contract.py`，锁定 REST/SSE 返回结构与字段语义。
  - integration: 复用 `tests/im_service/integration/test_messages_api.py`、`tests/im_service/integration/test_events_sse_api.py`、`tests/im_service/integration/test_chat_flow_integration.py`，验证真实 HTTP 入口链路。
  - e2e: 复用 `tests/im_service/e2e/test_human_chat_sse_e2e.py`，验证 reconnect 与历史增量事件口径。
- Expected Tests:
  - `tests/im_service/unit/test_event_repository.py::test_create_message_persists_delivery_events_in_order`
  - `tests/im_service/unit/test_repositories.py::test_message_roundtrip_keeps_order`
  - `tests/im_service/contract/test_messages_contract.py::test_create_message_contract_includes_delivery_status`
  - `tests/im_service/contract/test_messages_contract.py::test_list_messages_contract_includes_delivery_status`
  - `tests/im_service/contract/test_events_contract.py::test_events_endpoint_contract_returns_event_stream`
  - `tests/im_service/integration/test_messages_api.py::test_sse_events_roundtrip_for_sent_message`
  - `tests/im_service/integration/test_events_sse_api.py::test_events_sse_supports_last_event_id_reconnect`
  - `tests/im_service/integration/test_chat_flow_integration.py::test_human_chat_roundtrip_with_history_and_conversation_list`
  - `tests/im_service/e2e/test_human_chat_sse_e2e.py::test_human_chat_chain_and_sse_reconnect`
- DoD:
  - `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/im_service -q 2>&1 | tail -80` 全绿。
  - C1/C2/C3 齐全。
  - `PROGRESS/M113-IM-消息交付状态与SSE回执收口.md` 记录决策、证据、回滚点、提交哈希。
- 状态: DONE
