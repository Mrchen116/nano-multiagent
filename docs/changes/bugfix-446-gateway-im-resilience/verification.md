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

---

# Round 2

> Round 2 · 2026-06-29 · review_round=2 · mode=full

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks + round1 W1 closed |
| Correctness | incident/design/delta-spec covered; fix-r1 edge matrix covered |
| Coherence | Followed |

No critical issues. No warnings. 1 suggestion remains. Ready for PR (with noted documentation follow-up).

Verification run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider \
  tests/unit/personal_assistant/test_gateway_runtime_watchdog.py \
  tests/unit/personal_assistant/test_gateway_im_resilience.py \
  tests/unit/personal_assistant/test_gateway_build_runtime.py::test_reconcile_on_connect_continues_after_binding_failure_and_reports_degraded \
  tests/unit/personal_assistant/test_cron_polling_runner.py::test_polling_runner_survives_scheduler_tick_failure \
  tests/unit/personal_assistant/test_cron_polling_runner.py::test_polling_runner_start_attaches_done_callback -q
# 19 passed
```

## Completeness

**Tasks: 10/10 complete.** `M1-resilience/tasks.md:13-22` remains fully checked off and every listed exit criterion maps to code and tests.

**Round1 W1 closed.** The prior warning required a dedicated test for issue path 3: `finally` awaiting `im_task` must not let a stored/background task exception tear down shutdown. This is now covered by `tests/unit/personal_assistant/test_gateway_runtime_watchdog.py:394`, which monkeypatches `_await_background_task` to raise `asyncio.CancelledError`, then asserts `GatewayRuntime.run_forever()` still exits `0` and later cleanup (`kernel.stop`, resource closer) still runs (`test_gateway_runtime_watchdog.py:433-436`). The implementation catches `BaseException` around `_await_background_task(im_task)` at `src/personal_assistant/main.py:1659-1666`, so both `Exception` and `CancelledError` cleanup failures are contained.

**Round1 fix package complete.** The follow-up commits after round1 cover all requested hardening edges:

| Edge | Implementation evidence | Test evidence | Status |
|---|---|---|---|
| watchdog process-level exceptions re-raise | `src/personal_assistant/main.py:1689-1692` re-raises `CancelledError`, `SystemExit`, `KeyboardInterrupt` | `test_gateway_runtime_watchdog.py:147-169` | covered |
| watchdog backoff resets after stable runtime | `src/personal_assistant/main.py:1694-1697` and `1704-1707` reset delay after runtime reaches max window | `test_gateway_runtime_watchdog.py:172-210` | covered |
| clean stop return exits watchdog | `src/personal_assistant/main.py:1698-1703` returns when shutdown is requested or manager `_stop_requested` is true | `test_gateway_runtime_watchdog.py:213-245` | covered |
| crash/clean-exit logs are mutually exclusive | crash path logs exception at `main.py:1697`; clean manager stop logs info and returns at `main.py:1701-1703` | branch-specific tests above exercise crash vs clean paths | covered |
| shutdown interrupts watchdog backoff | `src/personal_assistant/main.py:1714-1720` waits on shutdown event with timeout instead of sleeping uninterruptibly | `test_gateway_runtime_watchdog.py:247-275` | covered |
| binding failure continues reconcile + degraded heartbeat | `_reconcile_on_connect` catches binding failure, sends `status="degraded"`, then still calls reconcile at `main.py:2431-2467` | `test_gateway_build_runtime.py:283-386` | covered |
| run_forever first-connect signal set on all exits | `src/personal_assistant/ws/im_connection.py:379-399` sets event in `finally` | `test_gateway_im_resilience.py:81-158` | covered |
| first-connect timeout warning | `src/personal_assistant/ws/im_connection.py:356-364` logs warning on bounded timeout | `test_gateway_im_resilience.py:191-203` | covered |
| cheap cleanup for ack future race | `src/personal_assistant/ws/im_connection.py:861-879` suppresses `InvalidStateError` | `test_gateway_im_resilience.py:238-265` | covered |

## Correctness

### Requirement: 瞬态故障后节点自动恢复 online

The implementation still satisfies the incident scenarios:

- Host sleep / network interruption / IM restart are handled by the same reconnect path: `IMConnectionManager.run_forever()` catches ordinary connection failures, marks disconnected, sleeps with exponential backoff, and retries (`src/personal_assistant/ws/im_connection.py:366-399`).
- If the IM maintenance loop exits unexpectedly instead of retrying internally, `GatewayRuntime._supervise_im_connection()` rebuilds it while shutdown is not requested (`src/personal_assistant/main.py:1672-1722`).
- The real-stack critical path remains registered in `docs/e2e-critical-paths.md:44` and is driven by `scripts/e2e-resilience.sh:176-208` for IM restart and Gateway-before-IM startup. Prior progress records a live pass in `M1-resilience/progress.md:137-144`.

### Requirement: 启动顺序不敏感

Startup no longer depends on eager IM connectivity. `_run_until_shutdown()` sets ready before the supervised IM loop (`src/personal_assistant/main.py:1602-1613`) and gates heartbeat startup only on a bounded first-attempt signal (`main.py:1614-1621`). `test_gateway_survives_unreachable_im_at_startup` uses a real `IMConnectionManager` with failing connect and asserts the Gateway stays alive and exits `0` on shutdown (`test_gateway_runtime_watchdog.py:278-316`).

### Requirement: 连接层故障永不致 Gateway 僵尸

The watchdog now has the expected split:

- Recoverable `Exception` from `manager.run_forever()` is logged and rebuilt (`main.py:1693-1698`).
- Clean return during shutdown or manager stop exits without rebuild (`main.py:1698-1703`).
- Process-control exceptions are not swallowed (`main.py:1689-1692`).
- Backoff is interruptible by shutdown (`main.py:1714-1720`).

The unit tests verify crash rebuild, process-level re-raise, stable-runtime reset, clean-stop return, and interruptible backoff (`test_gateway_runtime_watchdog.py:109-275`).

### Delta-spec

`docs/changes/bugfix-446-gateway-im-resilience/specs/gateway/spec.md` covers the required contract delta:

- MODIFIED `断线后自动重连...` adds host sleep, network interruption, and IM restart scenarios (`specs/gateway/spec.md:16-46`).
- ADDED startup-order-insensitive Gateway behavior (`specs/gateway/spec.md:50-56`).
- ADDED non-zombie connection maintenance behavior (`specs/gateway/spec.md:58-64`).

Implementation and test evidence above match these delta-spec requirements.

## Coherence

Design decisions remain followed:

- Decision 1 two-layer defense: inner reconnect loop in `im_connection.py:366-399`, outer watchdog in `main.py:1672-1722`.
- Decision 2 exception boundary: `CancelledError` cleanup/re-raise and `Exception` retry in `im_connection.py:386-396`; process-control `BaseException` handled by the outer supervisor without being swallowed.
- Decision 3 node-binding in `on_connected`: binding failure is degraded/non-fatal and does not skip reconcile (`main.py:2431-2467`).
- Decision 4 heartbeat tick guard: scheduler tick exceptions are logged and the loop continues (`main.py:1246-1257`), with `_consume_task_exception` registered on the heartbeat task (`main.py:1223-1228`).
- Decision 5 testing: deterministic unit tests cover path-level failures; real-stack e2e is registered for critical-path execution.
- Decision 6 cheap `InvalidStateError` defense: implemented in `im_connection.py:873-879`.

Architecture boundaries are preserved: production changes stay inside `personal_assistant`; Gateway continues to use `agent.sdk` rather than importing `agent.core` / `agent.platform` internals.

## Issues

### SUGGESTION

**S1: canonical `docs/specs/gateway/spec.md` still needs the delta-spec merged before final release documentation is considered current.**

This remains the same non-blocking documentation follow-up noted in round1. The delta-spec is complete at `docs/changes/bugfix-446-gateway-im-resilience/specs/gateway/spec.md:1-64`, but the canonical gateway contract does not yet include the new bugfix-446 scenarios. Merge the MODIFIED/ADDED sections into `docs/specs/gateway/spec.md` during orchestrator release-documentation cleanup so the long-lived contract matches the shipped behavior.

No critical issues. No warnings. Ready for PR (with noted documentation follow-up).

---

# Round 3

> Round 3 · 2026-06-30 · review_round=3 · mode=full/light recheck

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks + round2 code-review blockers closed |
| Correctness | incident/design scenarios still covered; W1 remains closed |
| Coherence | Followed |

No critical issues. No warnings. 1 suggestion remains. Ready for PR (with noted documentation follow-up).

Verification run:

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider \
  tests/unit/personal_assistant/test_gateway_runtime_watchdog.py \
  tests/unit/personal_assistant/test_gateway_im_resilience.py \
  tests/unit/personal_assistant/test_gateway_im_resilience_e2e_wrapper.py \
  tests/unit/personal_assistant/test_cron_polling_runner.py::test_polling_runner_survives_scheduler_tick_failure \
  tests/unit/personal_assistant/test_cron_polling_runner.py::test_polling_runner_start_attaches_done_callback \
  tests/unit/personal_assistant/test_gateway_build_runtime.py::test_reconcile_on_connect_continues_after_binding_failure_and_reports_degraded \
  -q
# 24 passed
```

## Completeness

**Tasks: 10/10 complete.** `M1-resilience/tasks.md:13-22` remains fully checked off. The latest merge `69d28e92` adds the requested round2 code-review fixes without reopening any task.

**Round2 code-review blockers closed.**

| Blocker | Implementation evidence | Test evidence | Status |
|---|---|---|---|
| Watchdog backoff no longer uses `asyncio.to_thread` / blocked executor threads | `_supervise_im_connection()` uses async `_wait_for_shutdown_request(timeout=delay)` at `src/personal_assistant/main.py:1748`, not thread-backed waits | `tests/unit/personal_assistant/test_gateway_runtime_watchdog.py:278` monkeypatches `asyncio.to_thread` to fail and verifies repeated rebuild backoff completes | closed |
| IM reconnect backoff close is interruptible | `IMConnectionManager.run_forever()` waits through `_sleep_until_stop()` at `src/personal_assistant/ws/im_connection.py:406`, which races sleep with `_stop_wait_event()` at `im_connection.py:414-428` | `tests/unit/personal_assistant/test_gateway_im_resilience.py:235` verifies `close()` wakes a 30s reconnect backoff within 0.25s | closed |
| `CancelledError` closes the live websocket | Cancel path calls `_disconnect_current_websocket()` before re-raise at `src/personal_assistant/ws/im_connection.py:397-400`; disconnect closes the socket at `im_connection.py:832-843` | `tests/unit/personal_assistant/test_gateway_im_resilience.py:82` verifies a connected blocking websocket gets `close()` exactly once after cancellation | closed |
| e2e script has no hard `yq` dependency | `scripts/e2e-resilience.sh:161-186` uses `yq` when present and a Python/YAML fallback when absent | `tests/unit/personal_assistant/test_gateway_im_resilience_e2e_wrapper.py:59` verifies `--prepare-only` mutates isolated config with `yq` absent | closed |
| pytest wrapper timeout kills the process group | e2e wrapper starts a new session at `tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py:49-56` and sends SIGTERM/SIGKILL via `os.killpg` at `test_gateway_im_resilience_critical_path.py:59-65` | `tests/unit/personal_assistant/test_gateway_im_resilience_e2e_wrapper.py:17` verifies `start_new_session=True` and process-group SIGTERM on timeout | closed |

**Round1 W1 still closed.** The dedicated cleanup-path test remains at `tests/unit/personal_assistant/test_gateway_runtime_watchdog.py:449-491`; implementation catches `BaseException` from `_await_background_task(im_task)` at `src/personal_assistant/main.py:1667-1674`, so IM task cleanup cannot skip later shutdown steps.

## Correctness

### Requirement: 瞬态故障后节点自动恢复 online

Still covered. Ordinary socket/HTTP failures stay inside the reconnect loop (`src/personal_assistant/ws/im_connection.py:377-412`), mark the connection disconnected, and retry with capped backoff. If the maintenance loop exits instead of retrying internally, the outer watchdog rebuilds it (`src/personal_assistant/main.py:1707-1752`). The real-stack critical path remains registered at `docs/e2e-critical-paths.md:44` and exercised by `scripts/e2e-resilience.sh:202-217` for IM restart recovery.

### Requirement: 启动顺序不敏感

Still covered. Gateway readiness no longer depends on eager IM connectivity (`src/personal_assistant/main.py:1610-1629`), and heartbeat startup waits only for a bounded first connect attempt. The startup-before-IM scenario remains in `scripts/e2e-resilience.sh:221-232` and the unit regression `tests/unit/personal_assistant/test_gateway_runtime_watchdog.py:333-371`.

### Requirement: 连接层故障永不致 Gateway 僵尸

Still covered. `_supervise_im_connection()` rebuilds recoverable crashes/returns while shutdown is not requested, propagates cancellation and process-control exceptions, and uses interruptible async backoff (`src/personal_assistant/main.py:1718-1752`). The crash rebuild, process-signal re-raise, stable-runtime reset, clean stop, interruptible shutdown, and no-`to_thread` executor-regression tests all pass (`tests/unit/personal_assistant/test_gateway_runtime_watchdog.py:109-330`).

### feat-393 Guard

Still covered. Heartbeat does not start until first connect attempt resolution (`src/personal_assistant/main.py:1622-1629`), the wait is bounded/logged (`src/personal_assistant/ws/im_connection.py:356-375`), and success/failure/BaseException/hung-connect cases remain covered by `tests/unit/personal_assistant/test_gateway_im_resilience.py:110-232`.

## Coherence

Design decisions remain followed:

| Decision | Round 3 verification |
|---|---|
| Decision 1 two-layer defense | Inner reconnect loop (`im_connection.py:377-412`) + outer watchdog (`main.py:1707-1752`) remain intact. |
| Decision 2 exception boundary | `CancelledError` cleans up and re-raises; ordinary `Exception` retries; process-control exceptions are not swallowed. |
| Decision 3 node-binding in `on_connected` | Binding failure remains degraded/non-fatal and reconcile continues (`src/personal_assistant/main.py:2457-2475` plus round2-tested continuation). |
| Decision 4 heartbeat tick guard | Scheduler tick failure is caught and logged (`src/personal_assistant/main.py:1246-1257`); done callback remains attached (`main.py:1223-1228`). |
| Decision 5 unit + e2e coverage | Deterministic unit tests cover the edge matrix; real-stack e2e script and critical-path registration remain present. |
| Decision 6 `InvalidStateError` defense | `_mark_disconnected()` still suppresses future race errors (`src/personal_assistant/ws/im_connection.py:891-909`). |

Architecture boundaries remain intact for this unit: production changes stay in `personal_assistant`, the Gateway continues to use `agent.sdk` as the product/kernel boundary, and IM remains a separate service observed through HTTP/WS rather than direct agent access.

## Issues

### SUGGESTION

**S1: canonical `docs/specs/gateway/spec.md` still needs the delta-spec merged before final release documentation is considered current.**

Unchanged from round2. The unit-local delta-spec is complete at `docs/changes/bugfix-446-gateway-im-resilience/specs/gateway/spec.md:11-65`, but the canonical gateway contract still only has the pre-bugfix `断线后自动重连` scenarios at `docs/specs/gateway/spec.md:277-290` and does not yet include the host sleep/network interruption/IM restart/start-order/non-zombie scenarios. Merge those sections during release-documentation cleanup.

No critical issues. No warnings. Ready for PR (with noted documentation follow-up).
