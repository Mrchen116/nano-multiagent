# bugfix-417-M6 — Progress

## 开工记录

- 上下文已读全：design.md（决策 11 + 「B 升级：中断收尾 + liveness 通用化」段 + 接口与数据流 B 增量 M6 行 + 风险表「M6 通用 ticker 空转 / 与 bash phase 冲突 / 心跳风暴」行 + Milestone M6 行 + changelog 顶条）、delta-spec specs/kernel/spec.md「alive-but-quiet 窗口经 stream 持续发出 liveness 事件」（其「执行静默长工具期间 stream 仍有事件」scenario 已是泛化措辞）、3 个范围文件 + 关联（bash.py:391 既有 phase:running 心跳样板、registry.py:213 `_emit_execution_update` closure + run_coroutine_threadsafe 桥、realtime_stream.py:120 phase 非空即投影、liveness.py 既有 `liveness_ticker` 范式、tool_executor.py:160 生产工具执行入口、inbound_pipeline.py:884 Gateway watchdog anext 重置逻辑）。
- 范围确认：仅 `src/agent/core/agent/liveness.py` + `src/agent/core/tools/registry.py` + `src/agent/platform/hooks/builtins/realtime_stream.py`（后者实测无需改）。**不碰** M5 的 runs/registry.py、kernel.py、runtime.py。worktree 从 unit/bugfix-417 HEAD（含 M1–M4 + 已加 M5/M6 文档）切出。
- 缺口确认：liveness 心跳 bash 专属——仅 bash `_run_foreground` 主动调 `ctx.emit_execution_event({phase:"running", elapsed_ms})`（bash.py:391）。其它长耗时 to_thread 工具执行期零 phase 事件 → 不投影 run_heartbeat → 超 watchdog 窗口被误杀（与 bash 修前同病根）。
- 通路辨析（决策 11 本意）：通用 ticker 走 `_emit_execution_update`（`tool_execution_update` 通路）经 realtime_stream 投影成 run_heartbeat，**不**直接复用 `liveness_ticker`（它直发 run_heartbeat、通路不同）。故在 liveness.py 同范式**新建** execution-update ticker。

## R1 — liveness 上提 executor 通用层（ticker 原语 + 接线 + 端到端守卫）

- Context: 工具执行 liveness 心跳是 bash 专属（bash 前台循环每 tick 自调 `ctx.emit_execution_event`）。任意其它长 to_thread 工具（web_fetch 等）在 `await asyncio.to_thread(tool.run)`（registry.py:251）阻塞期不产任何执行事件 → realtime_stream 无可投影 → 两 watchdog 看「输出静默」误杀活 run（#115）。
- Decision:
  - `agent/core/agent/liveness.py` 新增 `execution_update_ticker`（asynccontextmanager，与既有 `liveness_ticker` 同范式 + 伴生 `_emit_execution_updates`）：周期经注入的 `ExecutionEmitCallable` 发 `{phase:"executing", elapsed_ms}`（elapsed_ms 自 ticker spawn 起算，镜像 bash phase:running 形状，IM 可渲染「executing N s」）。`emit=None` 时 yield 即返回（CLI 无执行事件 sink → no-op，调用方无需分支）；body 完成/异常/取消时 finally 里 cancel+drain（await-bound，绝不空转、不掩盖真死锁——违反决策 2 不变量）；每 emit fail-open（sink 抛错丢该 tick、下个 tick/业务事件重建存活）。
  - `tools/registry.execute`：`await asyncio.to_thread(tool.run, ...)` 外 `async with execution_update_ticker(emit=_emit_execution_update, interval=_GENERIC_EXECUTION_HEARTBEAT_INTERVAL)` 包裹。复用既有 `_emit_execution_update` closure（registry.py:213，已捕获 base payload + loop + run_coroutine_threadsafe 桥）→ 与 bash 完全同一 observe→realtime_stream→run_heartbeat 投影链。新增模块级常量 `_GENERIC_EXECUTION_HEARTBEAT_INTERVAL = 10.0`（≤15s，`<<` watchdog 120s 窗口；模块级便于 e2e 守卫 patch 小值而不动生产 cadence）。
  - `realtime_stream.py`：无需改——`on_tool_execution_update`（:120）已对任意非空 `phase` 投影 run_heartbeat，`executing` 直接吃到；`elapsed_ms`（int）带上。
- Rationale: liveness 必须落在共享基础设施的正确高度（executor 通用层），而非每个工具贴特例（altitude 反模式，永远漏覆盖——web_fetch 当前就漏）。所有长工具零代价继承。bash 自身 `phase:running` 是更细的同源信号，叠加无害（都投影 run_heartbeat、watchdog 幂等重置）。ticker await-bound 保住决策 2 不变量（心跳证明「穿过此 await 的 progress」，非「Task 对象还在」——后者会掩盖 to_thread 里的真死锁）。
- Evidence:
  - ticker 单测 `tests/unit/test_bugfix_417_generic_tool_liveness.py`：5 passed —— executing phase + 递增 elapsed_ms、无 emit no-op、异常即停、取消即停、emit fail-open。
  - **DONE 硬闸** 端到端集成 `tests/integration/test_bugfix_417_bash_engine_e2e.py`（扩）：`_SlowSleepTool`（非 bash、`run()` 纯 `time.sleep`、不调任何 `ctx.emit_execution_event`）经真实 `build_kernel(tools=[_SlowSleepTool()])` wiring，fake LLM 调它，断言 `kernel.stream` 冒 `run_heartbeat` 且 `phase=="executing"`。该工具自身零 phase 事件，故任何 run_heartbeat 都证明 executor 通用 ticker（而非工具）产生。`PYTHONPATH=src pytest tests/integration/test_bugfix_417_bash_engine_e2e.py` → **3 passed**（含原 B1 两条 bash 守卫：silent long bash 冒 run_heartbeat、bash timeout 报 reason_code=tool_timeout，均不破）。
  - 相邻回归：`test_realtime_stream_heartbeat.py` + `test_bugfix_417_liveness_ticker.py` + `agent/tools/test_bash_tool.py` → 21 passed（bash phase:running + realtime_stream 投影 + 既有 liveness ticker 均不破）。

## 收口验证

- 全测试树：`PYTHONPATH=src python -m pytest -m "not e2e"` → **2668 passed, 2 skipped, 0 failed**。
- `ruff check`（全 4 个 diff 文件：liveness.py / registry.py / 两测试文件）→ No issues found；`ruff format --check`（同 4 文件）→ all formatted（测试文件首轮经 `ruff format` 自动修一次行宽换行后复检通过）。
- **live**（PA watchdog 不误杀 >窗口非 bash 长工具，#115 修复实证）：以真实 Gateway watchdog 源码 `InboundPipeline._await_terminal_run_async`（idle 窗口设 3s）面对一个 `time.sleep(5s)` 且自身零 phase 事件的非 bash 工具（经真实 `build_kernel` + fake LLM 调起）→ run 正常 `status=completed`、未被 watchdog cancel。证实 M6 generic ticker 持续冒 run_heartbeat 经 anext 重置 watchdog idle 计时。验证脚本临时、验毕已删，未提交。
  - 验证中确认的真实约束（非缺陷，已落注释）：默认间隔 10s 必须 `<<` watchdog 窗口（生产 120s，满足）；若间隔 > 工具时长则第一个 tick 来不及发——这正是间隔须 ≤15s 的硬约束依据。live 脚本按 interval<window<tool-duration 的真实比例缩放（1s/3s/5s）。

## Commits

- `dfa6d39` test(bugfix-417/M6): 通用工具 liveness 红测 — ticker 单测 + 非bash长工具端到端守卫
- `6072463` feat(bugfix-417/M6): liveness 上提 executor 通用层 — 所有长工具继承(#115)
- `docs(bugfix-417/M6): tasks+progress 回填`（本次）
