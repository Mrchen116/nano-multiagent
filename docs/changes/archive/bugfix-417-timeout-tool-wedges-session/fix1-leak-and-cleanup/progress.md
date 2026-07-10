# bugfix-417-fix1: leak-and-cleanup — Progress

> 提 PR 前 code-review 收敛后的 fix 轮（复用 M5 worker 热上下文）。从 unit HEAD
> (origin/unit/bugfix-417 = a6a544cb) 起 milestone/bugfix-417-fix1。
> 全部为本 diff 引入的内部泄漏/效率/cleanup，**非用户可观察改动**（#114 用户面由 reviewer2b 并行验）。
> 状态：**DONE**。

## 修复项结构化记录

### A — _foreground_task_ids 终态 discard（必修·泄漏）

- **Context**：`BackgroundTaskRegistry._foreground_task_ids`（M5 加）只在 `set_stop_handle(foreground=False)`
  降级时 discard；前台任务正常 complete/fail/kill 时**不** discard → 集合随进程寿命无界增长
  （同 M4 `_stopped` 泄漏教训）。
- **Decision**：`complete` / `fail` / `kill` 三终态方法内（持锁、set record 后）
  `self._foreground_task_ids.discard(task_id)`。
- **Rationale**：终态是唯一保证经过的清理点；`_guard_terminal` 早返回路径是已终态（首次转换时已 discard），幂等安全。
- **Evidence**：单测 `test_foreground_marker_discarded_on_{complete,fail,kill}` —— 前台任务终态后集合不残留。
- **Rollback**：移除三处 discard 回退到泄漏（pre-existing fix-轮前状态）。
- **Files**：`src/agent/core/background_tasks/registry.py`、`tests/unit/agent/background_tasks/test_background_tasks.py`。

### B — _user_interrupted_runs 全终态 discard（必修·泄漏）

- **Context**：`InboundPipeline._user_interrupted_runs`（M5 加）只在 `_emit_terminal_reconcile`
  fire 时 discard；run 走 watchdog 收尸/崩溃/正常完成等**不触发 reconcile** 的终态路径则永久泄漏。
- **Decision**：在 `_run` 的 `finally`（`_active_runs` pop 的同一 per-run 终态 chokepoint）
  `self._user_interrupted_runs.discard(run_id)` —— 所有终态路径都经过此 finally，保证有界。
- **Rationale**：reconcile-time discard 仍保留（消费 content 时清）；finally 是兜底的「保证经过」点，二者叠加无害。
- **Evidence**：单测 `test_user_interrupt_marker_cleared_on_terminal_without_reconcile` —— 预标记 run 完成（无 reconcile）后集合清空。
- **Rollback**：移除 finally discard 回退到泄漏。
- **Files**：`src/personal_assistant/gateway/inbound_pipeline.py`、`tests/unit/personal_assistant/test_inbound_pipeline_user_interrupt_leak.py`。

### D — bash 心跳双发：通用 ticker 跳过自发工具（顺手·效率）

- **Context**：M6 通用 ticker 对 bash **双发**心跳——bash 前台循环自发 `phase:running` +
  executor 通用 ticker 发 `phase:executing` → 每 interval 2x `run_heartbeat` 写（crv CONFIRMED）。
- **Decision**：给 `BashTool` 加类属性 `emits_own_execution_events = True`；executor 据此用
  `contextlib.nullcontext()` 跳过通用 ticker（`getattr(tool, "emits_own_execution_events", False)`）。
  bash 仍由自身 phase:running 覆盖；非自发工具（web_fetch 等）照常套通用 ticker。
- **Rationale**：在共享 executor 层按工具能力分流，不在工具层贴特例；属性默认 False，对其它工具零影响。
- **Evidence**：单测 `test_self_emitting_tool_skips_generic_executing_ticker`（bash 类工具无 phase:executing）
  + `test_non_self_emitting_tool_gets_generic_executing_ticker`（普通工具仍有）；
  回归：M6 SlowSleepTool 端到端守卫 + bash phase:running + interrupt-reap e2e 共 12 passed 不破。
- **Rollback**：移除属性 + 条件，回退到无条件套通用 ticker（双发，pre-existing）。
- **Files**：`src/agent/core/tools/registry.py`、`src/agent/platform/tools/builtins/bash.py`、
  `tests/unit/test_bugfix_417_fix1_generic_ticker_skip.py`。

### cleanup — 合并 10.0 心跳间隔常量

- **Context**：三处 10.0 散落：`liveness.DEFAULT_LIVENESS_HEARTBEAT_INTERVAL_SECONDS` /
  `tools-registry._GENERIC_EXECUTION_HEARTBEAT_INTERVAL` / `bash._FOREGROUND_HEARTBEAT_INTERVAL`，易漂移。
- **Decision**：单一真源 = `liveness.DEFAULT_LIVENESS_HEARTBEAT_INTERVAL_SECONDS`；另两处改为
  import 该常量赋值（保留模块级名字作 alias，使既有 monkeypatch 目标不破）。
- **Rationale**：消重复字面量、防漂移；保留 module-level 别名兼容测试 monkeypatch（registry/bash 的 e2e 守卫按名 patch）。
- **Evidence**：import 校验三处同源 = 10.0，无循环 import；相关 e2e/单测全绿。
- **Rollback**：还原三处独立字面量。
- **Files**：`src/agent/core/tools/registry.py`、`src/agent/platform/tools/builtins/bash.py`。

## 不修（已 refute / 无害，code-review 裁定）

- C auto-bg 竞态（REFUTED：同锁原子）、completed_event 幂等双 set、双 force-cancel 幂等、
  CancelledError（py3.12 安全）、CLI 装饰性交错。

## docs/证据

- 带入 M5 per-R `progress.md`（Context/Decision/Rationale/Evidence/Rollback/Commits）+ IM 卡真浏览器
  取证截图 `ACCEPTANCE/bugfix-417-M5/im-tool-card-interrupted-zh.png`（从 71cac91b 恢复，原 M5 milestone
  分支被合并后清理）。

## 验收

- 全树 `pytest -m "not e2e"`：见收口 commit（全绿）。
- `ruff check src/ tests/` + `ruff format --check src/ tests/`：clean。
- 关键回归：M5 interrupt-reap e2e 守卫、M6 SlowSleepTool 守卫、bash phase:running 不破（12 passed 复核）。
- 用户面 #114 不必本轮重跑双产品 live（reviewer2b 并行验）。
