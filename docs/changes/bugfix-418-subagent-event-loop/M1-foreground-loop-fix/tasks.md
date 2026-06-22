# bugfix-418-M1: foreground-loop-fix — Tasks

> 对齐: ../design.md v1

## 目标

前台 `agent` 工具派生的 subagent 不再在私有 ThreadPoolExecutor 的瞬时事件循环上跑共享 runtime；改为复用内核专用循环（`RunsRegistry._async_loop`）上的独立 Task。外部可观察变化：前台 subagent 正常返回结果（不再 `bound to a different event loop`），且单次 subagent 失败被收敛在工具边界内、不拖垮常驻协程。

## 退出标准

- [x] 前台 subagent in-budget 完成走专用循环、返回结果文本（status=completed）— e2e 用例1 真 LLM 返 pong
- [x] 前台 in-budget 完成路径**不**调用 `BackgroundTaskRegistry.register_subagent`（保 bugfix-417「无注册即无 task-notification」不变量）— 单测 `test_foreground_in_budget_does_not_register_subagent`
- [x] 超时分支仍 register + watcher，行为不变 — `test_foreground_auto_backgrounds_on_timeout` 复用通过
- [x] 删除 `_run_subagent_turn_sync` + 私有 `_executor`，无残留引用 — `rg` 仅剩 docstring 历史提及
- [x] `event_loop is None` 的库装配 fallback 不与主循环共享 runtime（防御性）— `test_submit_foreground_without_loop_runs_in_isolated_thread`
- [x] 新增 `@pytest.mark.e2e` 真 LLM e2e：前台派 subagent 跑通一轮 + 失败隔离断言 — 2 passed
- [x] `pytest tests/ -m "not e2e"` 全绿 — 2710 passed, 2 skipped

## 测试策略

- 被测行为（来自退出标准）：
  1. 前台 in-budget 完成经专用循环返回结果（单测，用真实 RunsRegistry 专用循环）
  2. 前台 in-budget 完成**不**调用 register_subagent（结构性，单测 spy）
  3. 超时分支仍注册（已有 `test_foreground_auto_backgrounds_on_timeout` 覆盖，复用）
  4. RuntimeRunner.submit_foreground 把 coro 提交到注入的 loop 并返回 Future（单测）
  5. 前台 subagent 失败被收敛、专用循环存活、兄弟 run 可继续（e2e）
- 已有测试在：`tests/unit/agent/tools/test_agent_tool.py`（扩展）、`tests/unit/agent/background_tasks/test_background_tasks.py`（扩展 RuntimeRunner）。新建 e2e：`tests/e2e/test_subagent_foreground_e2e.py`，理由：现有 e2e 文件无 subagent 工具覆盖，本 bug 回归守卫需独立文件。
- 落层/目录/marker：tests/unit/（单测）、tests/e2e/（marker：e2e，由 conftest 按路径自动打）
- 可选依赖 importorskip：无（e2e 用 env gate + proxy health 跳过，沿用 test_agent_runtime_e2e.py 模式）
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：手动 Gateway e2e 截图/log（reviewer 旅程证据，记 progress.md，不进 pytest 套件）

前端 UI：N/A（纯内核执行路径改动）

## Roadpoints

### R1 — 前台 subagent 改走专用循环 + 删死代码 + 结构性单测 [DONE]

- 步骤:
  - C1: 写失败单测——(a) 前台 in-budget 完成经真实 RunsRegistry 专用循环返回结果；(b) 前台 in-budget 不调用 register_subagent；(c) RuntimeRunner.submit_foreground 提交到注入 loop 返 Future
  - C2: RuntimeRunner 加 `submit_foreground(coro)->Future`（loop 注入则 run_coroutine_threadsafe，否则防御性 daemon-thread asyncio.run）；agent.py `_run_foreground` 改用 `wiring.subagent_runner.submit_foreground(runtime.run(...))`；删 `_run_subagent_turn_sync` + `_executor`
  - C3: progress.md 补证据
- 验证: `pytest tests/unit/agent/tools/test_agent_tool.py tests/unit/agent/background_tasks/ -q` 全绿；`rg _run_subagent_turn_sync\|_executor src/` 无残留

### R2 — 真 LLM e2e 回归守卫 [DONE]

- 步骤:
  - C1: 写 `tests/e2e/test_subagent_foreground_e2e.py`——前台派 subagent 跑通一轮 + subagent 失败后专用循环/兄弟 run 存活断言（env gate skip）
  - C2: 无（e2e 验证 R1 实现）；本地 `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 pytest -m e2e` 实跑
  - C3: progress.md 补 e2e + Gateway 手动旅程证据
- 验证: 本地真 LLM e2e 实跑通过；`pytest tests/ -m "not e2e"` 全绿
