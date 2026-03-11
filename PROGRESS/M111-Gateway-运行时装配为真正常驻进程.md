# M111 Gateway 运行时装配为真正常驻进程

## 启动记录
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`docs/NodeGateway-SPEC.md`、现有 `src/personal_assistant/` 运行时与相关测试。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M111，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M111`，branch=`milestone/M111`。
- 测试门禁：`PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M111/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/contract/test_personal_assistant_main_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/integration/test_personal_assistant_server_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/e2e/test_personal_assistant_main_e2e.py`。
- 基线结果：开始前门禁 `18 passed`，无既有失败可继承；后续改动必须保持全绿。
- prevention / 注意事项：
  - 严格按 NodeGateway-SPEC 装配现有组件，不重写 gateway/channel/scheduler/ws 现有模块。
  - 真实入口必须验证“常驻 + 就绪 + 优雅关闭”，不能只看 start/stop 被调用。
  - 本地配置只驱动静态生命周期参数，不扩展热重载等未来能力。
  - worktree 内 `data/dev-tasks.json` 与 `data/locks/` 已链接主仓共享路径，避免运行态分叉。

### R1 运行时装配与优雅生命周期
- Context: `main.py` 仍停留在 M98 骨架，启动内核后立刻 stop；M111 要在不重写现有 gateway/channel/scheduler/ws 模块的前提下，把它们装配成可常驻、可优雅关闭的进程。
- Decision: 在 `main.py` 内新增 `PollingHeartbeatRunner`、`_InboundDispatcher` 与完整 `GatewayRuntime` 生命周期，按 SPEC 顺序装配 `GatewayProcessManager` → `start_channels()` → heartbeat runner → optional `IMConnectionManager`，并以 `request_shutdown()` / `wait_until_ready()` 暴露可测控制面。
- Rationale: 现有核心模块已经具备单点能力，缺的是运行时编排与常驻等待；通过薄装配层补齐生命周期，既满足 M111 验收，又避免把实现扩散成新架构。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M111/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/contract/test_personal_assistant_main_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/integration/test_personal_assistant_server_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/e2e/test_personal_assistant_main_e2e.py`
  - Entry: `GatewayRuntime` 现已在 ready 后保持线程存活，收到 `request_shutdown()` 后按 `heartbeat -> channels -> IM -> kernel` 顺序收口退出。
- Rollback: 45ab588dbc306263719af25872f8c5c43a674df9
- Commits: C1=45ab588, C2=5a9efe4, C3=89243c9
- Next: 进入 R2，补 operator-facing smoke script 与脚本化 readiness/shutdown 证据。

### R2 Readiness / shutdown 回归与操作员 smoke 证据
- Context: R1 已让运行时常驻，但还缺少面向操作员的“真启动/真常驻/真关闭”证据；同时需要把测试门禁收敛到 M111 worktree 自身，避免用相对 `PYTHONPATH` 误跑到调用者 worktree。
- Decision: 新增 `personal_assistant.smoke_runtime`，用真实 `python -m personal_assistant.main --config ...` 子进程 + `httpx` 轮询 `/v1/health` 做 smoke；e2e 里临时写入使用 `uvicorn agent.platform.http_api.app:app` 的本地配置，并断言输出 `READY` / `RUNNING alive=true` / `SHUTDOWN exit_code=0`。
- Rationale: 这样能在不改现有运行时架构的前提下，直接证明本地配置、子进程内核、Gateway 常驻等待与优雅退出都已经接线完成，而且 smoke 命令可被操作员复用。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M111/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/contract/test_personal_assistant_main_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/integration/test_personal_assistant_bootstrap_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/integration/test_personal_assistant_server_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M111/tests/e2e/test_personal_assistant_main_e2e.py`
  - Entry: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M111/src python -m personal_assistant.smoke_runtime --config <node-config.yaml> --ready-timeout 20 --steady-seconds 0.2 --shutdown-timeout 10` 输出 `READY pid=...`、`RUNNING steady_seconds=0.2 alive=true`、`SHUTDOWN exit_code=0`。
- Rollback: 034d3e61d5e2f8d1b710c37695922f8ea6c6e8e3
- Commits: C1=034d3e6, C2=f258314, C3=<pending>
- Next: 全部 Roadpoint 已完成，可进入 milestone rebase / merge / dev-tasks 更新。
