# bugfix-402-M3: owned-run-shutdown — Tasks

> 对齐: ../design.md v1（决策 6 / 7）

## 目标

关闭路径安全：RunsRegistry 登记每个 Task 句柄，关闭时逐步排空 queued/running 任务后再停 loop；
Kernel 暴露 async-native `aclose()`，与同步 `close()` 共享幂等关闭状态；
Gateway 按生产者→消费者顺序关闭（先停 heartbeat/dispatch，再 `await Kernel.aclose()`，再等
run-stream/delivery consumers，最后关 IM）；coding_cli 退出路径改用 `await kernel.aclose()`；
`e2e-down.sh` 先等 Gateway grace exit 再停 IM，超时才强杀。

## 退出标准

- [x] Registry 登记并清空所有 owned Tasks
- [x] `Kernel.aclose()` 不阻塞 Gateway loop
- [x] sync/async close 共享幂等关闭状态，关闭后拒绝 submit
- [x] coding_cli 退出路径使用 `aclose()`，不在其 event loop 内阻塞
- [x] Gateway 等待 run-stream/delivery consumers 后再断 IM
- [x] e2e-down 先等 Gateway grace exit 再停 IM，超时才强杀
- [x] `bash -n scripts/e2e-down.sh` 语法检查通过
- [x] 全部测试文件绿通

## 测试策略

- 被测行为：
  1. Registry 关闭时等待活跃 Task 进入终态再停 loop（DRAINING）
  2. DRAINING 期间 submit 被拒绝并返回稳定 closed error
  3. `Kernel.aclose()` 可被 await（异步消费者路径）
  4. `Kernel.close()` 仍可同步调用（兼容路径）
  5. 重复 aclose/close 调用幂等，不抛出
  6. coding_cli `_async_main` finally 块 await aclose 而非 close
  7. Gateway 关闭顺序：heartbeat→Kernel→IM
  8. e2e-down.sh 有 grace wait 逻辑
- 已有测试在：`tests/unit/test_runs_registry.py`（扩展），`tests/unit/personal_assistant/test_gateway_stop_command.py`（扩展），`tests/unit/personal_assistant/test_gateway_pid_lifecycle.py`（扩展）
- 落层/目录/marker：tests/unit/，无 e2e marker
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据：无（纯后端逻辑，测试覆盖，无 UI）

## Roadpoints

### R1 — RunsRegistry Task 登记 + DRAINING 状态机

- 步骤:
  - 在 Registry 增加 `_tasks: dict[str, asyncio.Task]` 与状态枚举 `OPEN / DRAINING / CLOSED`
  - `submit()` 在 OPEN 时登记 Task，DRAINING/CLOSED 时抛出 `RegistryClosedError`
  - Task done callback 自动从 `_tasks` 清理
  - `drain_async()` 在 Registry loop 内等所有 owned Task 完成后关闭 loop
  - `shutdown()` 保留（同步兼容），内部调 drain_async 通过 future
- 验证: `pytest -xvs tests/unit/test_runs_registry.py` 全绿（含新用例）

### R2 — Kernel.aclose() + 幂等关闭

- 步骤:
  - `Kernel` 增加 `aclose()` async 方法，通过 `call_soon_threadsafe` 调 `drain_async()`，await future
  - `close()` 改为 `asyncio.run(aclose())` 的同步包装（仅在没有 running loop 时调）
  - 引入 `_closed` flag，重复调用直接返回
  - coding_cli `_async_main` finally 块改 `await kernel.aclose()`
- 验证: 新增 Kernel aclose/close 幂等测试 + coding_cli finally 路径测试；pytest 全绿

### R3 — Gateway 生产者→消费者关闭顺序

- 步骤:
  - `GatewayRuntime._run_until_shutdown` finally 块顺序：先关 heartbeat/dispatch，再 `await kernel.aclose()`（若有 kernel 引用），再等 run-stream/delivery consumers，最后关 IM
  - kernel 引用通过 `resource_closers` 改为显式 `async_kernel_closer` 列表（或直接在 runtime 持有）
- 验证: Gateway 关闭顺序测试；pytest 全绿

### R4 — e2e-down.sh grace wait

- 步骤:
  - 修改 `scripts/e2e-down.sh`：先向 Gateway 发 SIGTERM，sleep grace period（~5s），等其退出后再 kill IM；超时才强杀 Gateway
  - `bash -n scripts/e2e-down.sh` 验证语法
- 验证: `bash -n scripts/e2e-down.sh` 退出 0
