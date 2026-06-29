# Verification Report: bugfix-446

> Round 1 · 2026-06-29

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks + spec 全覆盖 |
| Correctness | 全覆盖（6 条 design 决策、4 条 incident scenario、逃逸路径 5/6 有显式测试） |
| Coherence | Followed（含 feat-393 护栏、done-callback 模式、local-autonomy 不变量） |

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 10/10 complete**

tasks.md 全部标 `[x]`，逐条核实：

| Task | 实现证据 |
|---|---|
| run_forever 异常分流 (CancelledError / Exception / BaseException) | `im_connection.py:379-391` |
| 首连落定 Event + `wait_first_connect_attempt` | `im_connection.py:336-357` |
| `_mark_disconnected` suppress InvalidStateError | `im_connection.py:869` |
| GatewayRuntime 移除 eager connect + watchdog | `main.py:1602-1612` + `1671-1698` |
| node-binding 并入 on_connected 非致命 | `main.py:2408-2424` |
| 心跳 start 等首连落定 (feat-393 护栏) | `main.py:1618-1619` |
| 心跳 tick try/except + done callback | `main.py:1250-1256` + `1227` |
| finally 吞 im_task 异常 | `main.py:1662-1665` |
| e2e 脚本 + 登记 e2e-critical-paths.md | `scripts/e2e-resilience.sh` + `docs/e2e-critical-paths.md:44` |
| pytest -m "not e2e" + ruff 全绿 | 本轮验证实跑 3125 passed / ruff all pass |

**Spec 覆盖**

incident.md 4 条 Requirement / 4 个 Scenario 全部有实现（见 Correctness 表格）。

delta-spec 已写至 `docs/changes/bugfix-446-gateway-im-resilience/specs/gateway/spec.md`（MODIFIED 3 条 + ADDED 2 条）；progress.md §0.13 注明「契约层 canonical 归 orchestrator 收尾归并」，canonical `docs/specs/gateway/spec.md` 未动属预期行为，orchestrator 收尾前需执行合并。

---

## Correctness

### Requirement: 瞬态故障后节点自动恢复 online

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| Gateway 所在机器休眠唤醒后节点自动恢复 | `im_connection.py:373-391` run_forever 循环体捕获 Exception → `_mark_disconnected` + 退避重连；`main.py:1671-1698` watchdog 兜底重建 | e2e `test_gateway_im_resilience_critical_path.py` + `scripts/e2e-resilience.sh` Scenario A（kill IM 等价） | covered |
| 网络中断恢复后节点自动恢复 | 同上（本质相同故障路径） | 同上 | covered |
| IM 服务重启后节点自动重新注册 | on_connected `_reconcile_on_connect` (main.py:2408) 每次连上重跑 binding + reconcile | e2e Scenario A | covered |

### Requirement: 启动顺序不敏感

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| Gateway 先于 IM 启动不崩 | eager connect_once 已删除（main.py:1603-1608 注释说明）；im_task 由 `_supervise_im_connection` 监督，首连失败进退避重试 | `test_gateway_survives_unreachable_im_at_startup` (test_gateway_runtime_watchdog.py:145)：真 IMConnectionManager connect 恒失败 → gateway 不崩、exit 0 | covered |

### Requirement: 连接层故障永不致 Gateway 僵尸

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 出现超出已知范围的连接故障 | `_supervise_im_connection`(main.py:1684) `except BaseException` 兜底重建；run_forever `except Exception` 退避重试 | `test_watchdog_rebuilds_im_loop_after_abnormal_exit` (test_gateway_runtime_watchdog.py:107)：2 次 crash + 1 次稳定，crash 不外泄，exit 0 | covered |

### 6 条逃逸路径覆盖

| 路径 | 修复位置 | 测试 | 状态 |
|---|---|---|---|
| ①首连裸调用 | 删除 eager connect_once（decision 3）| `test_gateway_survives_unreachable_im_at_startup` | covered |
| ②`_post_im_connect` 只 catch GatewayStartupError | 删除 post_im_connect；binding 移入 on_connected 非致命（decision 3）| `test_on_connected_failure_does_not_tear_down_connection` | covered |
| ③finally `_await_background_task` 重抛 | `main.py:1662-1665` try/except 包裹 | 无专项测试（watchdog 测试间接验证 exit 0）| **WARNING** |
| ④`_scheduler.tick()` 裸 await | `main.py:1250-1256` try/except | `test_polling_runner_survives_scheduler_tick_failure` | covered |
| ⑤CancelledError 逃逸跳过清理 | `im_connection.py:379-382` cancel 先 `_mark_disconnected` 再 re-raise | `test_run_forever_cancelled_cleans_up_then_reraises` | covered |
| ⑥im_task 无 watchdog 静默死亡 | `main.py:1609-1611` watchdog + `1684-1698` supervisor | `test_watchdog_rebuilds_im_loop_after_abnormal_exit` | covered |

### feat-393 护栏（decision 3 配套）

| 行为 | 实现 | 测试 | 状态 |
|---|---|---|---|
| 心跳首 tick 等首连落定再放行 | `main.py:1618-1619` await `wait_first_connect_attempt()` 后再 `heartbeat_runner.start()` | `test_heartbeat_start_waits_for_first_connect_attempt`：events.index("im.connect.resolved") < events.index("heartbeat.start") | covered |
| 连挂死时心跳不永久阻塞 | `im_connection.py:342-357` 内部带超时上限，TimeoutError 吞掉继续 | `test_wait_first_connect_attempt_is_bounded_when_connect_hangs` | covered |
| IM 不可达时首次尝试失败也 set | `im_connection.py:385` except Exception 分支 set | `test_run_forever_first_connect_attempt_resolves_on_failure` | covered |

---

## Coherence

### design.md 关键决策遵守

| 决策 | 核实 | 状态 |
|---|---|---|
| 决策 1: 两层防御（内层自愈 + 外层 watchdog）| run_forever 退避重试（内层）+ `_supervise_im_connection` 兜底重建（外层）；拒绝"只内层"/"只外层"已在 design 明确说明并在代码中体现 | Followed |
| 决策 2: CancelledError 清理后 re-raise；Exception 退避；BaseException 漏给 watchdog | `im_connection.py:379-391` 三路 except 边界精确 | Followed |
| 决策 3: node-binding 移入 on_connected，幂等且非致命 | `main.py:2408-2415` 只 catch GatewayStartupError 记 feedback，不 re-raise；连接层 on_connected 包装本就吞 Exception | Followed |
| 决策 3 配套：watchdog 退避参数复用 IMConnectionConfig | `main.py:1513-1514` `im_watchdog_initial_seconds=1.0` / `im_watchdog_max_seconds=60.0` 与 `IMConnectionConfig` 默认值对齐 | Followed |
| 决策 4: tick try/except + done callback 沿用既有 `_InboundDispatcher` 模式 | `main.py:1225-1227` add_done_callback(`_consume_task_exception`) | Followed |
| 决策 5: 单测注入异常 + e2e 真栈 kill/restart IM | 单测覆盖全 6 条路径（除路径③见 WARNING）；e2e `scripts/e2e-resilience.sh` 验场景 A+B，已真跑到节点回 online | Followed |
| 决策 6: set_exception suppress(InvalidStateError) 纯防御 | `im_connection.py:869` | Followed |

### 架构自洽性

- 所有改动限于 `personal_assistant` 内部；产品层未反向 import `agent.core` / `agent.platform`（contract 全绿 132 passed）
- local-autonomy 不变量：`_ready_event` 仍在 connect 前 set（`main.py:1601`），连接故障不打断本地执行，不变量保住
- 无新增公开 API 或数据结构变更，无跨机假设

---

## Issues

### WARNING

**W1: 缺逃逸路径③专项测试（finally 吞 im_task 异常，issue 路径 3）**

tasks.md 退出标准要求「每条逃逸路径有单测覆盖」，issue 路径 3（finally 清理块被 `_await_background_task` 重抛炸穿）在现有测试中无专项覆盖。

实现位置：`main.py:1658-1665`
```python
if im_task is not None:
    try:
        await _await_background_task(im_task)
    except Exception as exc:  # noqa: BLE001
        _log.warning("IM task await raised during shutdown: %s", exc)
```

缺的测试：构造一个 im_task 在 shutdown 期间 `_await_background_task` 会 raise 的场景，断言：(a) 异常不逃逸出 `_run_until_shutdown`；(b) shutdown 流程继续完成（其他清理步骤执行）。

**补测建议**（`tests/unit/personal_assistant/test_gateway_runtime_watchdog.py` 追加一个测试）：

1. 创建一个 `_FailingAwaitIMManager`，其 `run_forever` 正常阻塞直到 shutdown，但在 shutdown 后 task 状态让 `_await_background_task` raise `RuntimeError`。
2. 可通过 monkeypatch `_await_background_task` 使其在 im_task await 时 raise RuntimeError 来简化。
3. 断言 `GatewayRuntime.run_forever()` 仍返回 exit code 0，其余清理步骤（heartbeat.stop、channel.stop 等）正常执行。

注：设计上 watchdog（`_supervise_im_connection`）本身 absorbs 所有 BaseException，im_task 基本不携带存储异常；此 try/except 为纯防御层，触发概率极低——但属 exit criteria 显式要求，应补测。

---

### SUGGESTION

**S1: canonical `docs/specs/gateway/spec.md` 待合并 delta-spec（orchestrator 收尾项）**

delta-spec `docs/changes/bugfix-446-gateway-im-resilience/specs/gateway/spec.md` 已写完（MODIFIED「断线重连」新增 3 Scenario + ADDED「启动顺序不敏感」「连接维护故障永不致不可恢复」2 Requirement）。progress.md §0.13 注明由 orchestrator 执行合并。

**合并方式**：将 delta-spec 中 MODIFIED Requirement 下的 3 条新 Scenario 追加到 canonical `docs/specs/gateway/spec.md:287-294` 后；将 2 条 ADDED Requirement + Scenario 追加到 `spec.md` 末尾；删除 delta-spec 草案（或保留作历史）。

**S2: `ensure_node_binding` docstring 不准确（预存问题）**

`main.py:864` docstring 写 `Raises: RuntimeError`，但实际所有失败分支均 raise `GatewayStartupError`（非本次引入）。建议更新为 `Raises: GatewayStartupError`。

**S3: `test_watchdog_rebuilds_im_loop_after_abnormal_exit` docstring 混淆路径编号**

`test_gateway_runtime_watchdog.py:110` 注释写 "(issue path 3 / 'silent death')"，但路径 3 是 finally 块问题，'silent death' 对应路径 6（watchdog 缺失）。建议改为 "(issue path 6 / 'silent death')"。

---

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).
