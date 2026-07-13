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

- Status: DONE
- Context: active AGENTS/scripts/acceptance helpers/sample configs 仍描述独立 Kernel 端口、health 与 `.api.pid`；`e2e-up.sh` 还用 buffered log 关键词冒充 readiness，并混用系统 `python3`，导致真实 worktree 环境缺 PyYAML 时无法起栈。
- Decision: 清理 allowlist 内全部旧拓扑与 sample `kernel:`；M170 helper 改用 Gateway state PID/liveness + IM node-online；e2e finalizer 只追真实 Gateway 入口。`e2e-up.sh` 统一选择可 import PyYAML 的项目 Python，并用“Gateway PID 存活 + 认证 `/im/v1/nodes` 返回本 node online”作为 transport startup 检查，明确不把它提升为用户旅程 readiness；`e2e-down.sh` 只回收 IM/Gateway 并删除 worktree migration backup。
- Rationale: buffered stdout 在非 TTY 子进程可保持空文件，日志关键词不是稳定协议；项目依赖必须由既有环境提供。PID + IM node-online 与真实所有权/拓扑一致，最终 readiness 仍由黑盒消息和主动任务证明。
- Evidence:
  - Tests: C1 contract guard `2 failed, 1 passed`，失败精确命中 active narrative/sample config；Green 后 guard + runtime helper + finalizer 15 passed。受影响合集（contract、runtime helper/finalizer、全部 PA unit、provider error integration）最终 `791 passed`；ruff check/format、`bash -n` 全绿。
  - Entry: `e2e-up.sh` 在持久 tmux 中启动 ephemeral IM `58666` + Gateway PID `87603`，认证 node board 返回本 node online；`.api.pid` 与旧 app 进程均不存在。主机同时有主仓 Gateway PID `80740` 占用 8089，worktree Gateway 的 internal-dispatch bind 冲突未阻断 Web IM 主链路。
  - Frontend State Matrix: N/A；本 unit 不改 UI。
  - Browser QA: N/A；以 Web IM 客户端使用的同一 HTTP/WebSocket 黑盒接口驱动。
  - E2E/Regression: LLM proxy `/health` 200；`test_tool_call_reply_critical_path` 通过，真实工具读取随机哨兵并由 Agent 回复到 IM。cron 首轮被 pytest 全局 120s（短于用例 180s 业务窗口）中断；以 `--timeout=240` 原样单独重跑后 `1 passed in 44.87s`，用户收到新的 cron 主动推送。两条均在 8089 冲突存在时成立。
  - Config migration: 分别以 legacy-only 和 mixed config 启动真实后台 Gateway，再 load/save；legacy 三项解析为 `9/4/0.4`，mixed 逐字段解析为 `12/4/0.3`；两次 backup 都与启动前原文 `cmp` 一致，canonical 文件均无 `kernel:` 且只写非默认 `gateway:`，随后按各自 config state 成功 stop 并删除隔离目录。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Cleanup: `e2e-down.sh` 后 PID 87603 已退出，`.gateway.pid`、`.im.pid`、`.api.pid`、`.gateway-config.yaml`、migration backup 与旧 app/migration 测试进程均无残留；tmux session 已删除。
- Rollback: 回退到 C1 `02766572` 可恢复 R3 Green 前的 active entrypoint 内容；配置回退按 design 先恢复对应 migration backup。
- Commits: C1=`02766572`, C2=`d3399998`, C3=本 docs commit。
- Next: milestone 全量 non-e2e、rebase/锁校验与 unit branch 集成。
