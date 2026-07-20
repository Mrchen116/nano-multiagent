# refactor-470-M1 — Progress

## 启动记录

- 已完成 design、motivation、项目约束、`docs/TESTING_GUIDE.md`、现有 managed-channel source 与测试结构阅读。
- 基线：`/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_channel_manager.py tests/unit/personal_assistant/test_channel_manifest_store.py tests/unit/personal_assistant/test_channel_status_ack_handling.py tests/unit/personal_assistant/test_channel_status_outbox.py tests/integration/test_channel_bootstrap.py tests/integration/test_channel_reconcile.py tests/integration/test_channel_removal_reconcile.py` → `24 passed`。
- 环境说明：milestone worktree 未含 `.venv`；已确认主仓共享虚拟环境存在并仅用于执行本 worktree 源码测试，未向 worktree 写入环境文件。

### R1 — 固化空 bootstrap 与移除 legacy bridge

- Context: standalone YAML 自动导入、明文 cleanup 与 export 不属于当前契约，却让 transport 依赖 provider callback 并让入口持有密钥迁移策略。
- Decision: transport 收到 `channels.bootstrap.request` 直接发送空 `items`；删除 bootstrap provider/applied callback、YAML credential-ref migration、export 脚本和仅覆盖该路径的测试。
- Rationale: bootstrap wire handshake 仍由 `IMConnectionManager` 正常结算，但不再从本地 standalone YAML 产生 managed manifest 或改写配置。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check src/personal_assistant/main.py src/personal_assistant/ws/im_connection.py src/personal_assistant/config/local_store.py tests/integration/test_channel_bootstrap.py tests/unit/personal_assistant/test_builtin_skill_bootstrap.py tests/unit/personal_assistant/test_sensitive_local_config.py` → passed；`/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/integration/test_channel_bootstrap.py tests/unit/personal_assistant/test_builtin_skill_bootstrap.py tests/unit/personal_assistant/test_sensitive_local_config.py` → 7 passed。
  - Entry: integration test 建立真实 FastAPI IM WebSocket 并走 `channels.bootstrap.request`，验证 Gateway 回 `items: []`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_channel_bootstrap.py::test_gateway_bootstrap_response_is_empty_without_legacy_yaml_bridge`，通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `2a1251207` 与 `49b93d276`。
- Commits: C1=`49b93d276`，C2=`2a1251207`，C3=`8c794b188`。
- Next: R2 建立 managed control、typed bindings 和 mailbox。

### R2 — 建立 managed control 边界与 typed bindings

- Context: managed-channel integration policy 原先以 closure 分散在 Gateway 入口，既捕获尚未构造的 IM connection，也让 transport 接收多个独立 callback。
- Decision: 新增 `ManagedChannelControl`，组合 credential opening、manifest apply、Feishu factory、status/metadata durable projection、ACK/retry 和 stale reconnect；`IMConnectionManager` 改为只接收不可变 `ManagedChannelBindings`。register ACK 将当前 sender 传入 `on_connected`，入口按 node binding → durable channel replay → Agent reconcile 编排；reconcile result 直接经当前 sender 的 FIFO 发送。mailbox union 只保留 status/metadata，emission 在断线、未注册或连接 epoch 已变更时丢弃，重连仅由 durable store replay。
- Rationale: `ChannelManager`、`ChannelManifestStore` 和 `IMConnectionManager` 分别继续独占 runtime、durable outbox 和 wire FIFO；control 没有 connection 引用，mailbox 也不成为第二个断线队列或 ACK owner。
- Evidence:
  - Tests: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_managed_channel_control.py tests/unit/personal_assistant/test_gateway_status_frame_ownership.py tests/unit/personal_assistant/test_gateway_build_runtime.py tests/integration/test_channel_bootstrap.py tests/integration/test_channel_reconcile.py tests/integration/test_channel_removal_reconcile.py` → `47 passed`。
  - Entry: `./scripts/e2e-up.sh` 后检查隔离 IM 的 `channel_manifest_heads`：Gateway 完成 bootstrap，`manifest_revision == 1`、`initialized_at` 非空、`agent_channels` 为 0；随后 `./scripts/e2e-down.sh` 清理 IM 与 Gateway。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_managed_channel_control.py` 覆盖 public control 的 fail-closed apply、status directive 和 durable register replay；`test_gateway_status_frame_ownership.py::test_pre_register_managed_emission_is_not_retained_in_wire_fifo` 与 `test_disconnected_managed_emission_is_not_retained_in_wire_fifo` 覆盖注册前和断线 mailbox 均不进入 wire FIFO；fatal status receive-stack close regression 继续通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `3cbd614a6` 与 `df9d6601a`。
- Commits: C1=`df9d6601a`，C2=`3cbd614a6`，C3=`44d8de526`；后续 race regression=`3c8b48015`。
- Next: R3 收口公开 skill activation 与入口 wiring。

### R3 — 收口 public skill activation 与入口 wiring

- Context: managed Feishu activation 从入口私有穿透 `IMAgentConfigSync`，无法由 control 通过稳定边界调用。
- Decision: 增加 `ensure_agent_skill_enabled(agent_id, skill_id)` public operation；control 只调用该 operation。register-ready 入口只使用 IM 提供的当前 sender，不再捕获 nullable `im_connection_manager`。
- Rationale: activation 和 local config 仍由 `IMAgentConfigSync` 自己管理，connection 仍由 `IMConnectionManager` 自己管理；composition 不再承接两者内部策略。
- Evidence:
  - Tests: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_build_runtime.py tests/unit/personal_assistant/test_gateway_status_frame_ownership.py tests/unit/personal_assistant/test_gateway_wire_liveness.py tests/unit/personal_assistant/test_gateway_reconnect_registration_gate.py tests/unit/personal_assistant/test_gateway_reconcile_callback.py tests/unit/personal_assistant/test_gateway_im_resilience.py` → `40 passed`；managed-channel focused suite → `51 passed`。
  - Entry: 同 R2 的 worktree 真 IM/Gateway bootstrap 路径；服务已由 `scripts/e2e-down.sh` 关闭，无残留 PID。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_ensure_agent_skill_enabled_updates_explicit_local_allowlist` 验证 explicit allowlist 更新与缺失 agent；`test_gateway_build_runtime.py::test_reconcile_on_connect_continues_after_binding_failure_and_reports_degraded` 验证当前 sender 在 binding failure 后投递 degraded heartbeat。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `e67e9fb74` 与 `51054aa31`。
- Commits: C1=`51054aa31`，C2=`e67e9fb74`，C3=本提交。
- Next: M1 完成，准备 rebase、完整 M1 验证和 unit 分支集成。
