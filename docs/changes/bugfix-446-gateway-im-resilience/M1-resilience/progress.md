# bugfix-446-M1 — Progress

> 单 M1。三提交循环 C1 红测 / C2 实现 / C3 文档，逐 roadpoint 推进。

## 启动澄清记录

- 范围理解无歧义，已向 orchestrator 报信「已读懂」。
- §0.13 决定：design Milestone 范围列含 `docs/specs/gateway/spec.md`（收尾归并 delta），但契约层
  canonical 归 orchestrator，delta-spec 自身也写明「收尾由 orchestrator 并入 canonical」。故本
  milestone 不写 `docs/specs/gateway/spec.md`，只保留 design-author 已写的
  `docs/changes/bugfix-446-gateway-im-resilience/specs/gateway/spec.md`。已知会 orchestrator。

## R1 — 连接层异常边界 + 首连落定信号 + InvalidStateError 防御

- Context: `run_forever` 的 `except Exception` 漏 `CancelledError`（BaseException），cancel 时跳过
  `_mark_disconnected` 清理（issue 路径 5）。移除 eager connect（R2）后还需一个「首次连接尝试落定」
  信号让心跳启动等握手（决策 3 配套护栏，防 feat-393 回退）。`set_exception` 理论 TOCTOU（决策 6）。
- Decision:
  - `run_forever` except 拆三路：`CancelledError`→`_mark_disconnected()` 清理后 `raise`；`Exception`→
    `_mark_disconnected(exc)` + 退避重试；其余 `BaseException` 不接，漏给外层 watchdog（R2）。
  - 新增 lazy `asyncio.Event` `_first_connect_resolved` + `_first_attempt_event()` + `wait_first_connect_attempt(timeout=)`；
    首次 connect resolve（成功或失败）即 `set()`，wait 带超时上限兜底（防 connect 挂死）。
  - `_mark_disconnected` 的 `set_exception` 包 `contextlib.suppress(asyncio.InvalidStateError)`。
- Rationale: cancel 必须先清理再尊重取消语义；普通异常是瞬态退避重试；进程级信号不强吞（强吞会破坏
  shutdown）。首连信号只 gate 首 tick、不改 local-autonomy（IM 不可达时首尝试失败也 set，心跳照常起步）。
  Event lazy 创建以绑定真正运行 run_forever / waiter 的事件循环。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_gateway_im_resilience.py test_gateway_im_connection_behavior.py test_gateway_connect_once.py` → 27 passed。
    新增 5 红测：cancel 清理+re-raise / 首连成功 set / 首连失败 set / wait 超时有界 / InvalidStateError 不外泄。
  - Entry: N/A（连接层纯逻辑；真栈入口验证在 R4 e2e）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 连接层回归（既有 22 例）全绿；真栈 e2e 在 R4。
  - Visual/Interaction: N/A
  - Lint: `ruff check` + `ruff format --check` 两文件通过。
- Rollback: 回退到 C1 commit abd55a02（红测在、实现未上）。
- Commits: C1=abd55a02, C2=8a138850, C3=(本提交)
- Next: R2 — main.py GatewayRuntime watchdog + 移除 eager connect + 心跳首连门 + finally 硬化。

## [Roadpoint 重新分组] R2/R3

- 原计划 R2=决策1+finally、R3=决策3(on_connected binding)+决策4(心跳 tick)。
- 实际：决策 3 的「移除 eager post_im_connect」与「node-binding 并入 on_connected」是同一处不可拆的
  改动（删 post_im_connect 必须同时给 binding 找新家），故把决策 3 整体并入 R2，R3 收窄为决策 4
  （心跳 tick try/except + done callback）。非 design 偏差，仅 roadpoint 边界微调。

## R2 — GatewayRuntime watchdog + 移除 eager connect + node-binding 并入 on_connected + 心跳首连门 + finally 硬化

- Context: 主循环编排上 issue 路径 1/2/3/6——eager `connect_once()` 裸调用 + `_post_im_connect` 只
  catch `GatewayStartupError`（启动期瞬态故障直接打死 Gateway）；`im_task` 无 watchdog（静默死亡即僵尸）；
  finally 内 `_await_background_task` 会重抛任务异常炸穿清理。
- Decision:
  - 删除 eager `connect_once()` + eager `_post_im_connect` 块；`im_task` 改为 `_supervise_im_connection`
    watchdog：`run_forever` 非 stop 退出（return 或 raise）即按退避重建（`im_watchdog_initial/max_seconds`
    构造参数，默认 1s/60s 镜像 IM 退避策略），`CancelledError` 透传、其余 `BaseException` 吸收后重建。
  - node-binding（`ensure_node_binding`）从 `post_im_connect` 移入 `_reconcile_on_connect`（on_connected），
    幂等且非致命：`GatewayStartupError` 仅 `_emit_gateway_feedback` degraded，不 re-raise；连接层 on_connected
    包装本就吞异常不断连，下次连上自愈重试。删 `post_im_connect` 参数 + `_publish_startup_failure` 方法。
  - 心跳 `start()` 前 `await manager.wait_first_connect_attempt()`（有界）放行首 tick（feat-393 护栏）。
  - finally：`_im_connection_manager.close()` 后 `_await_background_task(im_task)` 包 try/except 吞异常。
- Rationale: 把「连接」全部入口（首连/重连/binding）收进可自愈循环，supervisor 成唯一裁决退出处（只
  stop_requested 退出，其余重试/重建）。binding 移出启动关键路径 → 启动顺序不敏感。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/ tests/contract/test_personal_assistant_main_contract.py` → 662 passed,1 skipped；
    `tests/contract/` 全量 132 passed（白名单行号未失配）。
    新增红测：watchdog 重建（2 crash+1 stable 共 3 次 run_forever、crash 不外泄、exit 0）、
    启动不敏感（真 IMConnectionManager connect 恒失败 → Gateway 不崩、exit 0）、心跳首连门（im.connect.resolved 先于 heartbeat.start）、
    on_connected 失败非致命（连接不断、记 on_connected_error）。
    改写：`test_gateway_runtime_keeps_running_until_shutdown_requested`（去 im.connect/im.bootstrap）；
    删 obsolete `test_gateway_heartbeat.py`（其唯一测试断言已删除的 fail-fast bootstrap 契约）+
    `test_gateway_runtime_cleans_up_reverse_order_when_im_start_fails`（契约被决策 3 反转，新行为由 watchdog 文件覆盖）。
  - Entry: N/A（真栈入口验证在 R4 e2e）。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: 真栈 e2e 在 R4。
  - Lint: `ruff check` + `ruff format` 全通过。
- Rollback: 回退到 C1 commit（R2 C1 红测 hash 见下）。
- Commits: C1=abce4a3a, C2=852851c3, C3=(本提交)
- Next: R3 — 心跳 `_run_loop` tick try/except + `start()` done callback（决策 4）。

## R3 — 心跳 tick 兜底 + done callback（决策4）

- Context: `_run_loop` 的 `await self._scheduler.tick()` 为裸 await（issue 路径 4）——tick 抛异常会让
  整个心跳/cron 调度循环静默死亡且 Gateway 不自知；相邻 cron tick 已有 try/except，唯独 tick 本身没有。
- Decision: `_scheduler.tick()` 包 try/except（记 `_log.exception`、`summary=None` 跳过本轮投递、靠循环尾
  `wait_for` 自然进入下一 interval）；后续 heartbeat-run 消费块加 `summary is not None` 守卫（cron 块独立
  不受影响）。`start()` 创建的 task 挂 `_consume_task_exception` done callback（沿用 `_InboundDispatcher` 模式）。
- Rationale: tick 失败是瞬态，不该拖垮调度循环；done callback 让「循环真崩了」可观测而非静默吞掉。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/` → 662 passed,1 skipped。
    新增红测：tick 首次抛异常后循环存活并再 tick（fail_times=1 → tick_count≥2）；start 后 task 挂有 `_consume_task_exception`。
  - Entry: N/A（真栈在 R4）。
  - Frontend / Browser QA / E2E / Visual: N/A（R4 真栈）。
  - Lint: `ruff check` + `ruff format` 通过。
- Rollback: 回退到 C1 commit（R3 红测）。
- Commits: C1=(R3 红测), C2=cc931fbd, C3=(本提交)
- Next: R4 — e2e 真栈脚本（kill/restart IM + 启动早于 IM）+ 登记 docs/e2e-critical-paths.md。
