# bugfix-417-M6: generic-tool-liveness — Tasks

> 对齐: ../design.md（决策 11 + B 升级段 + 接口与数据流 B 增量 M6 行 + 风险表 M6 行 + Milestone M6 行）
> delta-spec: ../specs/kernel/spec.md「alive-but-quiet 窗口经 stream 持续发出 liveness 事件」（其「执行静默长工具」scenario 已泛化为任意工具，本 milestone 把实现从 bash 专属落到 executor 通用层兑现该泛化）
> 依赖: M3（承接其已活的 executor→_emit_execution_update→realtime_stream→run_heartbeat→两 watchdog 投影链）

## 目标

把工具执行 liveness 心跳从 **bash 专属** 上提到 **executor 通用层**，让所有长耗时 `to_thread` 工具（web_fetch 等）零代价继承心跳，不再因执行期静默被 watchdog 误杀（#115）。复用 M3 已建链路：executor 在 `await asyncio.to_thread(tool.run)` 外包一层 await-bound 通用 ticker，周期经既有 `_emit_execution_update` 发 `{phase:"executing", elapsed_ms}` → 既有 realtime_stream `on_tool_execution_update`（phase 非空即投影）→ `run_heartbeat` → 两 watchdog 重置。bash 自身 `phase:"running"` 更细粒度心跳并存（都投影 run_heartbeat、watchdog 幂等重置，不冲突）。

## 退出标准

- [x] R1 `liveness.py` 新增 await-bound `execution_update_ticker`（asynccontextmanager，与既有 `liveness_ticker` 同范式）：周期经注入的 `emit` callable 发 `{phase:"executing", elapsed_ms}`；`emit=None` 时 no-op；随 body 完成/异常/取消即停（不空转、不掩盖真死锁）；emit fail-open（sink 抛错不拖垮工具 run）
- [x] R1 `tools/registry.execute` 在 `await asyncio.to_thread(tool.run, ...)` 外 `async with execution_update_ticker(emit=_emit_execution_update, interval=_GENERIC_EXECUTION_HEARTBEAT_INTERVAL)`，复用既有 `_emit_execution_update` closure（与 bash 同一 observe→realtime_stream→run_heartbeat 投影链），间隔默认 10s（≤15s，`<<` watchdog 120s 窗口）
- [x] realtime_stream 无需改：`on_tool_execution_update` 已对任意非空 `phase` 投影 run_heartbeat，`executing` 直接吃到
- [x] DONE 硬闸：经真实 `build_kernel` wiring 的端到端集成测试断言「非 bash 长工具 → `kernel.stream` 真冒 `run_heartbeat`（executing phase）」
- [x] bash 自身 `phase:running` 不破 + B1 端到端守卫 2 passed 不破
- [x] 全树 `pytest -m "not e2e"` + `ruff check` + `ruff format --check`（全 diff 文件）全绿
- [x] live：真实 Gateway watchdog（`InboundPipeline._await_terminal_run_async`）面对一个 >窗口的非 bash 长工具，执行期不被误杀、run 正常完成

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

落层：

- **unit**（worker 红测 → 绿）：`tests/unit/test_bugfix_417_generic_tool_liveness.py` —— ticker 原语本身：executing phase + 递增 elapsed_ms、无 emit no-op、异常/取消即停、emit fail-open。
- **integration**（DONE 硬闸）：`tests/integration/test_bugfix_417_bash_engine_e2e.py` 扩 —— `_SlowSleepTool`（非 bash、run 内不调任何 `ctx.emit_execution_event`、纯阻塞）经真实 `build_kernel(tools=[...])` wiring，断言 `kernel.stream` 冒 executing-phase `run_heartbeat`。该工具自身零 phase 事件，故任何 run_heartbeat 都证明 executor 通用 ticker（而非工具）产生。
- **不测**：前端渲染（心跳仅 liveness，前端可忽略）；bash 进程组 / phase:running（M2/M3/M4 已覆盖，本 milestone 只验其不破）；两 watchdog 重定义本身（M3 已覆盖，本 milestone 经 live 验真实 watchdog 消费新增的通用心跳）。

## 推进顺序

单一内聚切片（一个 R）：ticker 原语 + executor 接线 + 端到端守卫不可横切拆分（liveness 通用化端到端垂直切片）。
