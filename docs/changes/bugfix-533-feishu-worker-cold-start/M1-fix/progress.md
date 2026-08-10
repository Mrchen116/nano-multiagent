# bugfix-533-M1 — Progress

## Baseline

- Claim: milestone 从可归因的 Feishu 绿基线开始，不吸收共享主机上的无关 heartbeat timing failure。
- Baseline: `fab6f75dde9c3d07eb6cb236fbffd9f1b829e0a5` (`unit/bugfix-533` dispatch head)，clean milestone worktree，macOS Python 3.12.9。
- Method: CI 等价 non-E2E 全量；随后按 orchestrator 授权串行复证唯一失败 exact test，并运行 Feishu worker/lifecycle focused baseline。
- Result: 全量 `1 failed, 3191 passed in 300.64s`，唯一失败为 `test_quiet_run_heartbeats_prevent_idle_reap` 的 40ms idle watchdog；串行 exact `1 passed in 4.38s`；Feishu focused `15 passed in 90.65s`。归类为 unrelated shared-host timing flake，禁止修改该 heartbeat test、production owner 或 timeout。
- Locator: `tests/unit/personal_assistant/test_session_run_coordinator_terminal.py::test_quiet_run_heartbeats_prevent_idle_reap`；`tests/unit/personal_assistant/test_feishu_worker_runtime.py`；`tests/unit/personal_assistant/test_channel_lifecycle_failures.py`。
- Limit: 初始 full-suite run 不是全绿；最终交付仍需重新运行完整 non-E2E。

## R1 — 固定轻量 import 与生产 spawn budget

- Context: `spawn` 重建 `_worker_bootstrap` 前必须初始化 `personal_assistant.channels.feishu` 包；包级 re-export 把 `client.py` 与完整 `lark_oapi` 提前挡在 `ready_event` 前。`worker.py` 中函数体内延迟 SDK target 与 bugfix-496 parent-sentinel 已是正确 seam，不应改 timeout 或 lifecycle。
- Decision: 将 `feishu/__init__.py` 收窄为轻量 package marker；仅有的两个正式 package-level `FeishuAdapter` 调用方改为直接从 `feishu.adapter` 导入。新建语义独立的 startup 测试文件，用 fresh interpreter 固定 import boundary，并用未替换 `_ready_event`、未传 `join_timeout` 的真实 spawn runtime 固定生产默认 ready budget。
- Rationale: 直接导入现有正式子模块即可恢复 feat-464 seam；不添加 lazy `__getattr__`、兼容 shim、新抽象或放宽 5 秒 budget。现有 worker/client、parent watcher、正常 stop/join、crash/status 与 IPC 代码零修改。
- Evidence:
  - Tests: Red 为 `pytest -xvs tests/unit/personal_assistant/test_feishu_worker_startup.py`，fresh interpreter 报出 `personal_assistant.channels.feishu.client, lark_oapi`（`1 failed in 45.35s`）；Green 为同文件 `2 passed in 0.42s`。随后 `test_feishu_worker_startup.py + test_gateway_build_runtime.py + test_managed_channel_control.py` 为 `16 passed in 5.29s`。
  - Entry: `test_spawn_worker_initializes_with_production_ready_budget` 真正使用 macOS `multiprocessing` spawn 启动、进入 child target、向 parent 投递事件并 stop/reap；没有测试专用 30 秒 wrapper。
  - Frontend State Matrix: N/A，非前端变更。
  - Browser QA: N/A，非前端变更。
  - E2E/Regression: 永久回归位于 `tests/unit/personal_assistant/test_feishu_worker_startup.py`；真实 Feishu 用户旅程留待 R3。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `03319c87a789e7d8f93cb677f93540fbc9a9537d` 可恢复修复前 package import 行为与测试状态。
- Commits: `03319c87a789e7d8f93cb677f93540fbc9a9537d`
- Next: R2 扩大到 Feishu lifecycle、相关 Gateway、静态/docs 与完整 non-E2E 门禁。

## R2 — 验证 Feishu lifecycle 与仓库门禁

- 状态: DOING

## R3 — 两轮 clean start 与真实飞书旅程

- 状态: TODO

## Promotion Candidates

None.
