# M148 Acceptance Handoff

## Scope
- Milestone: M148 — 修复 live acceptance 暴露的 IM 接口与动态同步残留问题
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M148`
- Branch: `milestone/M148`
- Date: 2026-03-13

## What is closed in this pass
1. IM 共享 SQLite 连接在跨线程参数化查询下的抖动已被定向红测锁定，并通过关闭 statement cache 收口。
2. IM 在 agent create/update 后会立即向已连接绑定节点推送 `config.sync`。
3. Gateway 现在会在同一次同步流程内重试拉取 agent config，覆盖短暂 `404`、旧 `profile_version` 与临时异常响应。
4. Gateway live 注册 agent 后会丢弃该 agent 的旧 session binding，确保下一条消息创建新 kernel session 并吃到新 profile/prompt。

## Automated evidence
### IM shared-SQLite stability
- Test: `/Users/czj/Repos/nano-multiagent/.worktrees/M148/tests/im_service/unit/test_db_init.py`
- Key assertion:
  - `connect(...)` 返回的共享连接在多线程参数化 `SELECT ... WHERE id = ?` 读压下不会再出现错误 payload、`None` 行或 `sqlite3.InterfaceError`。
- Implementation entry:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/src/IM/infra/db.py`

### IM create/update now pushes config.sync to online gateways
- Tests:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/tests/im_service/integration/test_agent_create_flow.py::test_create_agent_pushes_config_sync_to_connected_gateway`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/tests/im_service/integration/test_m103_im_gateway_e2e.py::test_agent_config_sync_notifies_connected_gateway`
- Key assertions:
  - 在线 websocket 注册后，创建 agent 会立即收到 `{"type": "config.sync", "payload": {"agent_id": ..., "profile_version": 1}}`。
  - patch agent config 后无需手动 push，gateway 会自动收到 `profile_version=2` 的 `config.sync`。
- Implementation entry:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/src/IM/application/config_service.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/src/IM/api/deps.py`

### Gateway retries config fetch and refreshes stale sessions
- Tests:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/tests/unit/personal_assistant/test_main.py::test_im_config_sync_client_retries_until_live_agent_config_reaches_target_version`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/tests/unit/personal_assistant/test_gateway_pipeline.py::test_register_agent_resets_existing_sessions_for_profile_refresh`
- Key assertions:
  - `_IMConfigSyncClient` 在收到 `404 -> version 1 -> version 2` 序列时会连续重试，直到拿到目标版本并注册 live agent。
  - `register_agent(...)` 会清掉该 agent 的既有 session binding，因此同一 inbound key 的下一条消息会创建新 kernel session，而不是沿用旧 prompt 的旧 session。
- Implementation entry:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/src/personal_assistant/main.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/src/personal_assistant/gateway/inbound_pipeline.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M148/src/personal_assistant/gateway/session_keys.py`

## Commands run
- Targeted dynamic-sync regressions:
  - `pytest tests/unit/personal_assistant/test_gateway_pipeline.py::test_register_agent_resets_existing_sessions_for_profile_refresh tests/unit/personal_assistant/test_main.py::test_im_config_sync_client_retries_until_live_agent_config_reaches_target_version tests/im_service/integration/test_agent_create_flow.py::test_create_agent_pushes_config_sync_to_connected_gateway tests/im_service/integration/test_m103_im_gateway_e2e.py::test_agent_config_sync_notifies_connected_gateway`
- Full M148 targeted gate:
  - `PYTHONPATH=src pytest -q tests/im_service/unit/test_db_init.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_m102_gateway_im_connection.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - Result: `50 passed in 0.95s`

## Live acceptance handoff still required
The following items are not claimed as completed by this subagent and must be rerun by the main agent against the real acceptance stack:
1. In the real browser, update `agent-m146-live` prompt to v2 and send a new message without changing node-config or restarting Gateway.
2. Confirm Gateway no longer logs `LookupError: unknown agent_id: agent-m146-live`.
3. Confirm the reply content is `LIVE_AGENT_V2`.
4. Confirm the corresponding `relay_tasks` row advances from `dispatched` to `completed` in `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime/im.db`.
5. Confirm IM logs no longer show intermittent `sqlite3.InterfaceError` on the affected endpoints during the same live run.

## Current verdict
- Verdict: Code-level fix and automated regression coverage ready for main-agent live acceptance.
- Not completed in this pass:
  - Real browser / real acceptance-stack proof
  - Merge to `main`
  - Worktree cleanup
