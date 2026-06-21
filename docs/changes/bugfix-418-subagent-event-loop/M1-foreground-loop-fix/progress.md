# bugfix-418-M1 — Progress

## 根因坐实（前置）

- `runtime.run` 入口 `runtime.py:286`：`self._session_locks.setdefault(session_id, asyncio.Lock())` 后 `async with lock`。该 Lock 在主 agent turn 首次跑时绑定到 RunsRegistry 专用循环。
- 旧前台路径 `agent.py:_run_subagent_turn_sync`（:611）在私有 ThreadPoolExecutor 工作线程里 `asyncio.run(runtime.run(...))` 起**瞬时新循环 L2**，L2 上 `async with` 那个绑定专用循环的 Lock → `<asyncio.locks.Event/Lock ...> is bound to a different event loop`。共享 httpx AsyncClient（绑专用循环，feat-335）同样跨循环 await。
- 缺陷二（故障隔离）：瞬时循环 L2 运行+close 污染共享单例，主循环 heartbeat/relay 下次操作即抛、协程静默死掉，进程在但失联。

## R1 — 前台 subagent 改走专用循环 + 删死代码 + 结构性单测

- Context: 前台 `agent` 工具经私有 ThreadPoolExecutor 里裸 `asyncio.run(runtime.run(...))` 起瞬时循环跑共享 runtime，await 绑定专用循环的 session Lock / httpx client 即抛 `bound to a different event loop`；瞬时循环还污染共享单例连带打挂常驻 heartbeat/relay（缺陷一+二）。
- Decision:
  - `RuntimeRunner.submit_foreground(coro)->Future`（runtime_runner.py）：复用后台同款 `run_coroutine_threadsafe` 把**裸** coroutine 提交到 `RunsRegistry` 专用循环，作独立 Task 跑；无 loop 时防御性 daemon-thread `asyncio.run`，不与主循环共享 runtime。
  - `BackgroundSubagentRunner` 协议（interfaces.py）+ `_NoOpSubagentRunner`（wiring.py）同步加 `submit_foreground`。
  - `agent.py:_run_foreground` 改提交裸 `runtime.run(...)`（不带 notifying on_complete），删 `_run_subagent_turn_sync` + 私有 `_executor` + 冗余 import。
  - 决策：design §接口扩展点选**路径 (ii)**（RuntimeRunner 加方法封装提交），比让 AgentTool 直接读 loop 更内聚、保 platform→core 分层。
- Rationale: 后台路径早已用 `run_coroutine_threadsafe(_worker, runs_loop)` 解同一问题，前台只是从未同步改造——复用既有机制而非另造。裸 coroutine（无完成回调）⇒ in-budget 结果绝不会被再当后台任务发 `<task-notification>`（结构性保住 bugfix-417 不变量，决策2）；in-budget 完成路径**不注册** registry，仅超时分支注册+watcher（沿用现结构）。
- Evidence:
  - Tests: `pytest tests/unit/agent/background_tasks/test_runtime_runner_foreground.py tests/unit/agent/tools/test_agent_tool.py tests/unit/agent/background_tasks/test_background_tasks.py` 全绿（42 passed）。新增结构性单测 `test_foreground_in_budget_does_not_register_subagent` 钉死决策2。
  - Entry: 最小复现脚本坐实根因——一个 await「绑定专用循环的 asyncio.Lock」的 coroutine：经 `submit_foreground` 提交到该循环返回 `subagent done`（修复有效）；OLD 裸 `asyncio.run` 在瞬时循环上 await 同一 loop-bound `Event` 则死锁/报跨循环错（坐实污染链）。
  - Frontend State Matrix: N/A（纯内核执行路径）
  - Browser QA: N/A
  - E2E/Regression: 见 R2
  - Visual/Interaction: N/A
- Rollback: `git revert` C2（fix commit）回到当前已知坏的前台路径；无数据迁移。
- Commits: C1=red `test(bugfix-418/M1/R1)`, C2=`fix(bugfix-418/M1/R1)`

## R2 — 真 LLM e2e 回归守卫

- Context: 本 bug 只有真正起子 agent 完整 turn 才炸，stub LLM 测不出；需真 LLM e2e 守住。
- Decision: 新增 `tests/e2e/test_subagent_foreground_e2e.py`，真 `RunsRegistry`(真专用循环) + 真 `AgentRuntime`(连本地代理 127.0.0.1:4000) + 真 `wire_background_tasks` —— 即生产同款装配路径，直接 `tool.run(前台 subagent)`。
  - 用例1 `test_foreground_subagent_completes_via_dedicated_loop`：派前台 subagent，断言 `status=completed`、内容含 pong、**不**含 `different event loop`。
  - 用例2 `test_failing_foreground_subagent_does_not_kill_dedicated_loop`：注入一个 `run()` 必抛的 `_FailingRuntime`（与健康 runtime 共享同一专用循环），断言失败被收敛为 `status=failed`，随后同一专用循环上的健康 subagent 仍跑通（`get_event_loop().is_running()`）——坐实「单 subagent 失败不拖垮节点」。
  - env gate `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1` + proxy health，沿用既有 e2e 约定（默认 `-m "not e2e"` 排除）。
- Rationale: 失败注入最初用「bogus model name」不可靠（registry/proxy 松散解析仍跑通），改为确定性子类抛错——既确定失败又仍走真专用循环提交路径，真正验证隔离。
- Evidence:
  - Tests: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 pytest tests/e2e/test_subagent_foreground_e2e.py -v` → **2 passed**（真端到端，真 LLM 返 pong）。
  - Entry: 即上面 2 条真 LLM e2e（真 RunsRegistry+AgentRuntime+proxy，用户可见结果=subagent 返回 pong / 失败后循环仍 is_running）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A（reviewer 走 Gateway/IM 前端旅程，见 design Runbook）
  - E2E/Regression: `tests/e2e/test_subagent_foreground_e2e.py`（2 用例，env-gated）；`pytest tests/ -m "not e2e"` → 2710 passed, 2 skipped。
  - Visual/Interaction: N/A
- Rollback: 删测试文件即可（纯新增守卫）。
- Commits: C1+impl=`test(bugfix-418/M1/R2)`

## R3 — create_session 创建路径同样改走专用循环（orchestrator follow-up）

- Context: orchestrator 复核时指出 `_create_subagent_session`(:471) 的裸 `asyncio.run(runtime.create_session(...))` 同属决策1「不在瞬时新循环上跑共享内核组件」该治的范围（前台+后台都走它）。要求最小复现脚本坐实是否真触碰绑定专用循环的共享单例，再决定路由或保留+证据。
- Decision: **路由到专用循环**——`_create_subagent_session` 改为经 `self._wiring.subagent_runner.submit_foreground(create_coro).result()` 把 create_session coroutine 提交到内核专用循环；仅在无 wiring/runner（纯库装配、无 RunsRegistry）时 fallback 裸 `asyncio.run`。前台+后台共用此方法，一处改两路径都覆盖。不动 `RuntimeRunner.start` 语义（只复用新增的 submit_foreground）。
- Rationale: 坐实证据见下——经验上 create_session 裸 run 当前不报错也不污染（背景路径一直如此），但 orchestrator 要求按决策1原则彻底落地、消除「靠它恰好不碰共享单例」的隐性依赖，而非留印象。架构上更干净：subagent 创建与执行两条路径都不再在瞬时循环上碰共享 runtime。
- Evidence:
  - 坐实脚本（最小复现，真 RunsRegistry 专用循环 + 真 AgentRuntime 共享 httpx client）：连续 5 次经裸 `asyncio.run(runtime.create_session(...))` 建 subagent session——0 报错；事后专用循环上的共享 `RetryingLLMClient` 仍可用、专用循环仍 `is_running()`。即 create_session 本身不创建绑定循环的 asyncio 原语、不 await 共享 httpx client（其唯一 await 点是 `_dispatch_observe`→hook，core 默认无 session_start 钩子）。结论：当前不污染，但按决策1原则统一路由消除隐性依赖。
  - Tests: 新增结构性单测 `test_create_subagent_session_routes_through_dedicated_loop`（红→绿：断言前台 dispatch 经 submit_foreground 提交两次=create+turn，钉死「create 不再裸 asyncio.run」）；修 `test_agent_tool_run_background_passes_workspace_root_to_registry` 的 stub 提供真 submit_foreground（否则 MagicMock 泄漏 coroutine——已用 `-W error::RuntimeWarning` 验证无泄漏）。
  - Entry: live e2e `test_subagent_foreground_e2e.py` 2 passed（create_session 改走专用循环后，前台 subagent 真 LLM 仍返回 pong + 失败隔离仍成立）。
  - E2E/Regression: `pytest tests/ -m "not e2e"` → 2711 passed, 2 skipped（较 R2 +1 = 新结构测试）。
  - Frontend/Browser/Visual: N/A
- Rollback: `git revert` 本 commit 回到「create_session 裸 asyncio.run」（已坐实当前不崩，纯架构加固）。
- Commits: `fix(bugfix-418/M1/R3)`（红测+实现+stub 修正自包含，§FL 单 commit 快车道）

## out-of-unit 发现（未顺手修，§0.8）

- `tests/e2e/test_agent_runtime_e2e.py` 已 stale：`create_llm_client()` 签名变更为 `create_llm_client(*, config)` 且返回的 `RetryingLLMClient` 不再支持 `with` 上下文管理器，该既有 live e2e 现会 `TypeError`。与本 bug 无关（pre-existing）。已立 issue #121，不在本 unit 范围内修。
