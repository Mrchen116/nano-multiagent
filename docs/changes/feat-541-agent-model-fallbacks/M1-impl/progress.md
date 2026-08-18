# feat-541 M1 — Progress

## 测试策略

测可观察行为：失败气泡含模型 id、`run_status.error.kind` 经 SDK stream 可见、replay 不追加 user parts、候选链/粘性/第一次 admit、心跳/cron 显式 `model=candidates[0]`、kind 决定是否换、内核拒绝则收口、说明只发一次、配置保存清粘性、IM 读写校验、前端折叠入口、备用列表不进内核、PA 不 import `agent.core`。

优先扩展既有文件（`test_local_store.py`、IM repository/contract、vitest 详情/创建页）。新文件均未超 400 行。未 skip/xfail。未跑隔离端口真栈 e2e。

## Commits

- `24ada38e8` 内核三条缝
- `44b02de9c` 配置层 `model_fallbacks`
- 本提交：Gateway 粘性 failover、心跳/cron 显式 admit、前端折叠入口

## 命令结果

```
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH python -m pytest \
  tests/unit/agent/runs/test_model_error_kind.py \
  tests/unit/agent/test_replay_last_user.py \
  tests/contract/test_agent_sdk_surface_guard.py \
  tests/contract/test_agent_sdk_surface_contract.py \
  tests/contract/test_model_fallback_boundary.py \
  tests/contract/test_agent_sdk_boundary_contract.py \
  tests/unit/personal_assistant/test_model_candidate_chain.py \
  tests/unit/personal_assistant/test_chat_model_failover.py \
  tests/unit/personal_assistant/test_unattended_model_admit.py \
  tests/unit/personal_assistant/test_heartbeat_scheduler.py \
  tests/unit/personal_assistant/test_session_run_coordinator_admission.py \
  tests/unit/personal_assistant/test_cron_run_origin.py \
  tests/unit/personal_assistant/test_local_store.py \
  tests/im_service/unit/test_agent_config_operations.py \
  tests/im_service/unit/test_repositories_agent_profile.py \
  tests/im_service/unit/test_repositories_schema.py \
  tests/im_service/contract/test_agent_config_contract.py \
  tests/im_service/contract/test_agent_create_contract.py \
  -q --tb=line
```

162 passed.

```
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH python -m pytest \
  tests/unit/personal_assistant/test_gateway_im_config_sync.py \
  tests/unit/personal_assistant/test_gateway_config_operations.py \
  tests/unit/personal_assistant/test_gateway_config_operation_validation.py \
  tests/unit/personal_assistant/test_session_run_coordinator_terminal.py \
  tests/unit/personal_assistant/test_cron_delivery_chain.py \
  tests/unit/personal_assistant/test_heartbeat_reply_visibility.py \
  tests/unit/personal_assistant/test_cron_polling_runner.py \
  tests/unit/personal_assistant/test_agent_config_sync_ownership.py \
  tests/im_service/integration/test_agent_config_operation_flow.py \
  tests/unit/agent/test_kernel_manual_compact.py \
  -q --tb=line
```

81 passed.

```
cd src/IM/frontend && npm test -- --run \
  src/features/settings/agents/agent-detail-page.test.tsx \
  src/features/settings/agents/agent-create.test.tsx \
  src/features/settings/agents/im-agent-config-api.test.ts
```

3 files / 50 tests passed。worktree 前端无独立 `node_modules`，vitest 临时借用主仓依赖，未提交。

## Changelog

（无实施偏差）
