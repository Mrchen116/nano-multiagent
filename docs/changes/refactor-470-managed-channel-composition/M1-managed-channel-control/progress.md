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
- Commits: C1=`49b93d276`，C2=`2a1251207`，C3=待提交。
- Next: R2 建立 managed control、typed bindings 和 mailbox。
