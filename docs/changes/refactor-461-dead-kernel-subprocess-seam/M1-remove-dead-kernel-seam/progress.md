# refactor-461-M1 — Progress

## Baseline

- 首次 untouched 全量 `pytest -m "not e2e"`：`1 failed, 3495 passed, 1 skipped, 23 deselected`；唯一失败为范围外 `test_competing_handlers_relay_and_ack_only_the_durable_winner`。
- Orchestrator 在 main 与 milestone worktree 各连续复跑该测试 8 次，合计 16/16 通过；按其继续条件再次运行 untouched 全量，结果 `3496 passed, 1 skipped, 23 deselected`（110.29s）。当前只证实一次瞬态失败，不纳入 M1 实现范围。

## R1 — 收口 Gateway lifecycle 配置与迁移备份

- Status: DONE
- Context: `KernelConfig` 把六项死连接/HTTP 字段与三项仍控制 Gateway supervisor 的 timing 混在一起；任意 config 被 canonical save 裁掉 `kernel:` 前必须可恢复原字节。
- Decision: 以 `GatewayLifecycleConfig` / `LocalConfig.gateway` 承载三项 timing；parser 对新旧 mapping 逐字段取值，新值优先；死字段完全忽略。save 仅写非默认 `gateway:`，检测磁盘顶层 `kernel:` 后排他创建 `<config>.pre-refactor-461.bak`，保存原字节与权限，内容一致复用、冲突/IO 失败中止覆盖。
- Rationale: 兼容只停留在 parser edge，不把旧 schema 包装回 runtime；确定性 per-file backup 独立于默认 config 的 timestamp retention，覆盖默认、自定义与 worktree config。
- Evidence:
  - Tests: C1 新增 6 个行为测试均按预期失败；Green 后 `test_local_store.py` 47 passed；config 与受影响 fixture consumers 共 102 passed；narrow ruff check/format 全绿。
  - Entry: 真实文件 load → save → reload 路径验证旧 timing 迁到 `gateway:`，自定义路径生成原字节 migration backup；完整 operator CLI/config save 将在 R3 Runbook 验收。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_local_store.py` 覆盖默认、旧值迁移、逐字段优先级、死字段忽略、backup 创建/权限/复用/冲突阻断；无 e2e marker。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `5244f1e3` 可移除 R1 Green，恢复旧 config runtime。
- Commits: C1=`5244f1e3`, C2=`bc5e8d2f`, C3=本 docs commit。
- Next: R2 删除 runtime manager/health/state interface，并以 PID/start confirmation 测试锁定行为。

## R2 — 删除 runtime subprocess/health seam 并保持 lifecycle 行为

- Status: DONE
- Context: `GatewayRuntime` 仍接受无生产构造点的 manager，background result/state/stop 又把 PID 或 IM URL 伪装成 Kernel health/readiness，测试因此能维持不存在的部署形态。
- Decision: 删除 manager/factory/optional constructor 与 start/stop 死调用；background parent 只等待 PID file + child liveness，并将 waiter 命名收口为 start confirmation。result/state 只保留 PID/config/log/独立 IM URL，stop 只按 PID/process-group 终止；读取旧 state 时自然忽略额外 `health_url`。保留的 skill-maintenance cases 迁入 runtime lifecycle 测试。
- Rationale: Gateway 后台 supervisor 与进程内 Kernel 各自只有一个真实所有者；不新增 readiness IPC，也不把 child 内 `_ready_event` 暴露给 parent。process-group 仍用于回收 Gateway 拥有的 channel/tool descendants。
- Evidence:
  - Tests: C1 targeted suite 17 failed/14 passed，失败点命中旧 waiter/health/result/constructor；Green 后 targeted lifecycle 82 passed，`tests/unit/personal_assistant` 770 passed；narrow ruff check/format 全绿。
  - Entry: 用 worktree `.operator-config.yaml` 实际执行默认 start → restart → stop：start 输出 `Gateway started (pid=47289)` + Log，新 state 仅含 config/log/pid；restart 得到新 PID 48131；stop 输出 `STOPPED pid=48131 state=...`，PID/state 均清理。隔离 config/workspace/log 已删除。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_gateway_launch.py`、`test_gateway_pid_lifecycle.py`、`test_gateway_main_command.py`、`test_gateway_runtime_lifecycle.py`、`test_gateway_shutdown_order.py`；operator 子进程真入口补充验证 start/restart/stop。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `7dec9880` 可恢复 R2 Green 前接口。
- Commits: C1=`7dec9880`, C2=`7052b33f`, C3=本 docs commit。
- Next: R3 清理 active scripts/docs/config residue、落 contract guard，并按 Runbook 真栈完成消息与主动任务证据。
- Env caveat: 主机已有其他 Gateway 占用固定 internal-dispatch 端口 8089（PID 80740）；R2 隔离实例沿用既有“dispatch bind 失败不阻断 Gateway”策略。因此本段 live 证据只证明 operator lifecycle，不计作消息/heartbeat/cron 主路径证据；R3 必须另用 worktree 真栈跑通用户可观察结果。

## R3 — 清理 active 入口残留并完成真栈验收

- Status: TODO
