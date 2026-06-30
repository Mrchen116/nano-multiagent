# bugfix-446-M1: Gateway-IM 连接韧性 — Tasks

> 对齐: ../design.md v1

## 目标

Gateway 在断网/休眠/IM 重启/启动早于 IM 等瞬态故障下都能自动恢复 online，连接维护过程的任何
瞬态故障都不会让 Gateway 停在「既不重连也不退出」的僵尸态。用户在 IM `/im/v1/nodes` 上能观察到：
故障期间节点 offline、故障消除后无需人工重启即自动回 online。

## 退出标准

- [x] 连接层 `run_forever` 异常分流：`CancelledError` 清理后 re-raise；`Exception` 退避重试；其余 `BaseException` 漏给外层 watchdog（决策 2）— R1
- [x] 连接层暴露「首次连接尝试落定」信号（Event + `wait_first_connect_attempt`），成功或失败均 set（决策 3 配套护栏）— R1
- [x] `_mark_disconnected` 的 `set_exception` 包 `suppress(InvalidStateError)`（决策 6）— R1
- [x] `GatewayRuntime` 移除 eager `connect_once()` + eager `post_im_connect`；`im_task` 由 watchdog 监督，非 stop 退出即重建（决策 1）— R2
- [x] node-binding 并入 `on_connected`，幂等且非致命（决策 3）— R2
- [x] 心跳 `start()` 等「首次连接尝试落定」再放行首 tick（feat-393 护栏）— R2
- [x] 心跳 `_run_loop` 的 `tick()` 包 try/except + task 挂 done callback（决策 4）— R3
- [x] finally 清理块吞掉 `im_task` 异常，清理流程不被其炸穿（issue 路径 3）— R2
- [x] e2e 真栈脚本覆盖 kill/restart IM + 启动早于 IM 两场景，真跑到节点回 online；登记 `docs/e2e-critical-paths.md`— R4
- [x] `pytest -m "not e2e"` 相关子树 + `ruff check` / `ruff format` 全绿

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为（来自退出标准）：
  - run_forever 异常分流（cancel re-raise + 清理 / Exception 退避 / BaseException 漏出）
  - 首次连接尝试落定 Event（连成功即 set / 连失败也 set / wait 超时兜底）
  - `_mark_disconnected` 对已 resolve 的 ack future 不抛 InvalidStateError
  - watchdog：im_task 非 stop 退出 → 重建（run_forever 被再次调用）
  - 启动顺序不敏感：连接失败不致 Gateway 崩，Gateway 持续运行到 shutdown
  - 心跳 start 等到首连落定再放行首 tick（feat-393 护栏回归）
  - 心跳 tick 抛异常 → 循环不死，下一 interval 继续
  - on_connected 并入 node-binding：调用且幂等、binding 失败非致命
  - finally 吞 im_task 异常不炸穿清理
- 实际落点（收尾对账）：
  - 新建 `tests/unit/personal_assistant/test_gateway_im_resilience.py`（连接层：cancel 清理+re-raise / 首连 Event / wait 有界 / on_connected 非致命 / InvalidStateError）
  - 新建 `tests/unit/personal_assistant/test_gateway_runtime_watchdog.py`（GatewayRuntime：watchdog 重建 / 启动不敏感（真 manager）/ 心跳首连门）
  - 改写 `tests/unit/personal_assistant/test_gateway_process_manager.py`（旧启动顺序断言去 im.connect/im.bootstrap；删被反转的 cleanup-on-im-fail 测试）
  - 扩展 `tests/unit/personal_assistant/test_cron_polling_runner.py`（tick 兜底存活 / start 挂 done callback）
  - 更新 fakes：`_main_helpers._FakeIMManager` / `test_gateway_shutdown_order._FakeIMManager` 加 `wait_first_connect_attempt`
  - 删除 `tests/unit/personal_assistant/test_gateway_heartbeat.py`（唯一测试断言已删除的 fail-fast bootstrap 契约）
  - 新建 `tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py`（真栈 e2e，subprocess 驱动 `scripts/e2e-resilience.sh`）
- 落层/目录/marker：tests/unit/personal_assistant/（无 marker）；tests/e2e/critical_paths/（`@pytest.mark.e2e`）
- 可选依赖 importorskip：无（e2e 用门控 skip：缺主 config / 未设 live 开关时干净 skip）
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：手动跑 `scripts/e2e-resilience.sh` 的日志输出（贴 progress）

前端：N/A（本 unit 不改客户端面，行为经 `/im/v1/nodes` 节点状态 API 可观察）。

## Roadpoints

### R1 — 连接层异常边界 + 首连落定信号 + InvalidStateError 防御（im_connection.py）  [DONE]

- 步骤: run_forever except 拆 CancelledError/Exception；新增 `_first_connect_resolved` Event 与 `wait_first_connect_attempt`；`_mark_disconnected` 包 suppress(InvalidStateError)
- 验证: 新建/扩展连接层单测全绿

### R2 — GatewayRuntime watchdog + 移除 eager connect + 心跳首连门 + finally 硬化（main.py）  [DONE]

- 步骤: 删 eager connect_once/post_im_connect；im_task 上 watchdog supervisor；心跳 start 前 await 首连落定；finally 包 try/except 吞 im_task 异常
- 验证: 改写 process_manager 启动顺序测试 + 新增 watchdog/不敏感/首连门红测全绿

### R3 — 心跳 tick 兜底 + done callback（决策4）  [DONE]

> 注：决策 3 的 on_connected 并入 node-binding 已并入 R2（与移除 post_im_connect 不可拆），见 progress「重新分组」。

- 步骤: `_run_loop` tick 包 try/except（记录后等下一 interval）；`start()` task 挂 done callback
- 验证: 心跳兜底单测全绿

### R4 — e2e 真栈脚本 + 登记 e2e-critical-paths.md  [DONE]

- 步骤: 写 `scripts/e2e-resilience.sh`（kill/restart IM + 启动早于 IM，轮询 /nodes online）；pytest 包装 `test_gateway_im_resilience_critical_path.py`；登记 catalog 一行
- 验证: 本地真跑脚本到「节点回 online」可见结果（贴 progress）
