# M204 Task — 修复 canonical M170 重启后 Alpha/Beta 未物化

## 启动记录
- 已确认 Milestone：`M204 / 修复 canonical M170 重启后 Alpha/Beta 未物化`
- execution_mode：`parallel`
- worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M204`
- branch：`milestone/M204`
- test_command：`pytest tests/unit/test_m170_runtime.py tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m103_im_gateway_e2e.py`
- 已确认共享派工板：`/Users/czj/Repos/nano-multiagent/.worktrees/M204/data/dev-tasks.json -> /Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- prevention_rules：
  1. 真实群聊验收失败时先检查 canonical restart path 是否真的 seed 运行态，不复用旧结论。
  2. fresh runtime + 浏览器 participant picker 必须同时出现 Alpha/Beta。
  3. 不允许手工改 DB 伪造通过。

## Roadpoints

### R1 锁定 canonical restart 应 seed 的运行态契约
- Acceptance:
  - `scripts/acceptance/m170_runtime.py` 重建 fresh runtime 后会生成 canonical node config，而不是退回单 `assistant`。
  - fresh runtime DB 在未启动浏览器前就已包含 `assistant`、`agent-m170-alpha`、`agent-m170-beta` 三个 profile。
  - `agent-m170-alpha` / `agent-m170-beta` 保留 M170 期望的 display name 与 prompt snapshot。
  - 不依赖手工 DB 编辑或残留运行目录。
- Tests Plan:
  - unit：新增/改写 `tests/unit/test_m170_runtime.py`，覆盖 runtime config 与 DB seed。
  - contract：不新增；本 Roadpoint 不引入新外部契约。
  - integration：复用现有 `test_m103_im_gateway_e2e.py` 证明 pre-seeded profile 在 register 后仍保留 canonical label。
  - e2e：本 Roadpoint 不做真实浏览器，留到 R2。
- Expected Tests:
  - `tests/unit/test_m170_runtime.py::test_rebuild_runtime_clears_stale_artifacts_and_recreates_layout`
  - `tests/unit/test_m170_runtime.py::<new canonical seed tests>`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py::test_gateway_reregistration_preserves_canonical_agent_labels_after_restart`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 记录根因、方案、证据、回滚点、提交哈希。
- 状态：DONE

### R2 用 canonical restart 命令做 fresh 自证
- Acceptance:
  - 仅运行 `scripts/acceptance/m170_runtime.py stop/start/status` 后，`ACCEPTANCE/m170-runtime/im_service.sqlite3` 中可见 `assistant`、`agent-m170-alpha`、`agent-m170-beta`。
  - `http://127.0.0.1:18031/im/v1/nodes` 报告 `agent_count >= 3`。
  - 真实浏览器 `http://127.0.0.1:18031/chat` 的群聊参与者选择器能看到 Alpha/Beta。
  - 证据留存在 `PROGRESS`，且不通过手工改库达成。
- Tests Plan:
  - unit：不新增；复用 R1 保护 restart seed 语义。
  - contract：不新增。
  - integration：复用 `test_command` 作为回归门禁。
  - e2e：执行真实 canonical restart、SQLite 查询、HTTP `/im/v1/nodes`、Playwright 浏览器 picker 检查。
- Expected Tests:
  - `pytest tests/unit/test_m170_runtime.py tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `PYTHONPATH=... python scripts/acceptance/m170_runtime.py stop`
  - `PYTHONPATH=... python scripts/acceptance/m170_runtime.py start`
  - `PYTHONPATH=... python scripts/acceptance/m170_runtime.py status`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 写清 DB/nodes/browser picker 证据与截图/查询路径。
- 状态：DONE
