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
  - Tests: 第一条 Red 为 `pytest -xvs tests/unit/personal_assistant/test_feishu_worker_startup.py`，fresh worker import 报出 `personal_assistant.channels.feishu.client, lark_oapi`（`1 failed in 45.35s`）；移除 package re-export 后先得到 `2 passed in 0.42s`。首次真实 live start 又证明 spawn 会重执行 `personal_assistant.main`，新增的 entry import contract 稳定报出相同两个重依赖（`1 failed in 15.65s`）；把 Gateway 两个 adapter import 移到实际构造点后，startup 文件最终 `3 passed in 1.91s`。
  - Entry: `test_spawn_worker_initializes_with_production_ready_budget` 真正使用 macOS `multiprocessing` spawn 启动、进入 child target、向 parent 投递事件并 stop/reap；没有测试专用 30 秒 wrapper。
  - Frontend State Matrix: N/A，非前端变更。
  - Browser QA: N/A，非前端变更。
  - E2E/Regression: 永久回归位于 `tests/unit/personal_assistant/test_feishu_worker_startup.py`，同时固定 worker 模块与 Gateway spawn 入口两个 import boundary；真实 Feishu 用户旅程留待 R3。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `03319c87a789e7d8f93cb677f93540fbc9a9537d` 可恢复修复前 package import 行为与测试状态。
- Commits: `03319c87a789e7d8f93cb677f93540fbc9a9537d`、`045373db0b07dcea18a0b44602965501822d1f89`
- Next: R2 扩大到 Feishu lifecycle、相关 Gateway、静态/docs 与完整 non-E2E 门禁。

## R2 — 验证 Feishu lifecycle 与仓库门禁

- Context: package import 收窄不能改变 bugfix-496 parent-sentinel、正常 stop/join、crash status、IPC 顺序、ChannelManager retry/reap 或 Gateway 两个 composition 入口；交付还需区分 milestone diff 与 dispatch base 已有门禁问题。
- Decision: 扩大到全部 Feishu 命名 tests、worker/lifecycle/ChannelManager/Gateway composition tests，再跑 CI 等价完整 non-E2E。静态门禁全仓执行；全仓 formatter 唯一失败按 orchestrator 明确授权记录为 dispatch base caveat，保持 touched Python files 的 focused formatter 绿且不改 out-of-scope eval fixture。
- Rationale: related suite 验证既有生命周期和消息路径没有因导入重定向退化；完整 non-E2E 证明 fresh-import seam 对全仓收集/运行兼容。base-owned formatter drift 必须可见，但不能越权吸收到本 milestone。
- Evidence:
  - Tests: follow-up 后最终 Feishu/Gateway/lifecycle focused suite `167 passed in 15.19s`；CI 等价 `pytest -m "not e2e" -n 4 --dist worksteal --durations=20 --durations-min=0.5` 为 `3195 passed, 20 warnings in 51.67s`。
  - Entry: R1 的真实 spawn 回归保持绿；R3 继续验证真 Gateway + 真飞书入口。
  - Frontend State Matrix: N/A，非前端变更。
  - Browser QA: N/A，非前端变更。
  - E2E/Regression: `tests/unit/personal_assistant/test_feishu_worker_startup.py` 与现有 worker/lifecycle suites 均进入固定 non-E2E gate；外部平台旅程待 R3。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Static: `ruff check .`、`git diff --check`、`./scripts/docs-check` 通过；本 milestone 4 个 touched Python files 的 `ruff format --check` 通过。
  - Base caveat: 全仓 `ruff format --check .` 仅报告 `evals/spec_design_alignment/base_repo/materialize.py`、`evals/spec_design_alignment/base_repo/tests/test_materialize.py`、`evals/spec_design_alignment/base_repo/tests/test_suite_recipes.py`、`evals/spec_design_alignment/validate_dataset.py`；这些路径相对 `origin/unit/bugfix-533` 的 diff 为 0，未修改、未放宽或绕过 formatter，最终 main sync 前需重判。
- Rollback: R2 无产品代码变更；R1 回滚仍为 revert `03319c87a789e7d8f93cb677f93540fbc9a9537d`。
- Commits: 验证基线为 `03319c87a789e7d8f93cb677f93540fbc9a9537d`，本段记录见后续 docs commit。
- Next: R3 使用专用非 default Feishu profile 完成两轮 clean start、真实消息与唯一 shadow 验收并清理。

## R3 — 两轮 clean start 与真实飞书旅程

- Context: 第一轮真实启动仍复现 `feishu worker did not initialize`，证明只移除 package re-export 不足：macOS spawn 重执行 `personal_assistant.main` 时，`composition.py` 与 `managed_channel_control.py` 的顶层 adapter import 仍会在 child bootstrap 前加载 provider。该失败作为有效 live evidence 保留；不改 5 秒 worker-ready budget。
- Decision: 将两个 `FeishuAdapter` import 分别下沉到静态 channel 与托管 channel 的实际构造点，并用 fresh `personal_assistant.main` import contract 防回归。随后所有产品 cold start 均进入 ready；以同一受控 shell 完成两轮完整观察，避免测试宿主在 launcher 返回后回收子进程。
- Rationale: 这恢复 feat-464 的轻量 spawn seam，而不改变 worker target、bugfix-496 parent watcher、stop/join、crash/status、IPC 或消息气泡语义。真实旅程按 current spec 允许一个 run 产生多个可见 assistant 气泡，唯一性固定在 external conversation、user shadow 与 saga。
- Evidence:
  - Tests: 专用、已验证且非 default 的 Feishu E2E profile 与测试 App/Bot identity 一致；LLM proxy 健康。两轮无预热 clean start 均由生产 `e2e-up.sh --feishu` 进入 ready，Gateway 与直属 `multiprocessing.spawn` listener 同时存活，日志均无 `feishu worker did not initialize` 或 `worker_crashed`。
  - Entry: 最终轮由测试 user 向专用 Bot 发出一条 nonce；Lark 历史新增 `user=1, app=2`，两个 app 气泡对应本轮允许的两个完整 assistant 气泡。
  - Frontend State Matrix: N/A，非前端变更。
  - Browser QA: N/A，外部平台与 IM durable state 直接取证。
  - E2E/Regression: IM durable state 为 `external_source=feishu`、`config_agent_id=e2e` 的 conversation `1`、user shadow `1`、completed agent bubbles `2`、failed agent bubbles `0`；external shadow saga `1`。证据摘要见 `evidence/cold-start-live-validation.md`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Cleanup: 两轮均配对执行 `e2e-down.sh`；最终确认 Gateway/IM PID、listener 子进程、IM 端口、listener lock、临时 JWT/config/channel credential/manifest 文件均已清理。
- Rollback: revert `045373db0b07dcea18a0b44602965501822d1f89` 与 `03319c87a789e7d8f93cb677f93540fbc9a9537d` 可恢复修复前 import 行为。
- Commits: `03319c87a789e7d8f93cb677f93540fbc9a9537d`、`045373db0b07dcea18a0b44602965501822d1f89`；本段证据见后续 docs commit。
- Next: milestone 完成，等待合入 `unit/bugfix-533`。

## Promotion Candidates

None.
