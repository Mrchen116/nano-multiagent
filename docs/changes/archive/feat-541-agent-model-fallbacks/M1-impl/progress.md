# feat-541 M1 — Progress

## 测试策略

测可观察行为：失败气泡含模型 id、`run_status.error.kind` 经 SDK stream 可见、replay 不追加 user parts、候选链/粘性/第一次 admit、心跳/cron 显式 `model=candidates[0]`、kind 决定是否换、内核拒绝则收口、说明只发一次、配置保存清粘性、IM 读写校验、前端折叠入口、备用列表不进内核、PA 不 import `agent.core`。

Verifier R1 缺的回归：`failover_unattended_run` 的 quota / `context_length` / 拒绝 replay / 整链耗尽；心跳复用 canonical session 时 admit sticky 备用；聊天整链耗尽不发「已改用」。前端清空备用后 PATCH `model_fallbacks: []`。

优先扩展既有文件。新文件均未超 400 行。未 skip/xfail。

## 真实入口

隔离栈：worktree `scripts/e2e-up.sh --wt … --main-config ~/.nanoassistant/config.yaml`（必须用 worktree 脚本，主仓 `PYTHONPATH` 没有 `model_fallbacks_json` 列）。Vite 代理到本次 `IM_URL`。关键画面见 `acceptance.md` 文末归档证据，不另存 M1 过程截图。

编辑页 PATCH `plato`：`default_model=deepseek:deepseek-v4-flash`，`model_fallbacks=["kimiCoding:kimi-for-coding"]`，mirror GET 回读一致。console 无 pageerror。

## Commits

- `24ada38e8` 内核三条缝
- `44b02de9c` 配置层 `model_fallbacks`
- `6c1d51e1f` Gateway 粘性 failover、心跳/cron 显式 admit、前端折叠入口

## 命令结果

```
PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH python -m pytest \
  tests/unit/personal_assistant/test_unattended_model_admit.py \
  tests/unit/personal_assistant/test_chat_model_failover.py \
  tests/unit/personal_assistant/test_gateway_config_operations.py \
  tests/unit/personal_assistant/test_gateway_config_operation_validation.py \
  -q --tb=line
```

29 passed（含 unattended failover / canonical sticky / 整链耗尽 / apply 持久化备用链）。

```
cd src/IM/frontend && npm test -- --run src/features/settings/agents/agent-detail-page.test.tsx
```

20 passed（含清空备用后 PATCH `model_fallbacks: []`）。

## Changelog

- Gateway `_agent_operation_payload` 漏了 `model_fallbacks`，只改备用列表时指纹对不上、apply 可能空写。已补进 payload，并用 apply 单测锁住。

## 先前实现命令结果

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

聊天同轮切换截图留给 reviewer 真栈（需把主模型设成目录内会认证失败/欠费的 id）。配置卡 1440/375 已落盘。
