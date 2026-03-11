# M111 Gateway 运行时装配为真正常驻进程

## 启动记录
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`docs/NodeGateway-SPEC.md`、现有 `src/personal_assistant/` 运行时与相关测试。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M111，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M111`，branch=`milestone/M111`。
- 测试门禁：`PYTHONPATH=src pytest -q tests/contract/test_personal_assistant_main_contract.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py tests/e2e/test_personal_assistant_main_e2e.py`。
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
  - Tests: `PYTHONPATH=src pytest -q tests/contract/test_personal_assistant_main_contract.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py tests/e2e/test_personal_assistant_main_e2e.py`
  - Entry: `GatewayRuntime` 现已在 ready 后保持线程存活，收到 `request_shutdown()` 后按 `heartbeat -> channels -> IM -> kernel` 顺序收口退出。
- Rollback: 45ab588dbc306263719af25872f8c5c43a674df9
- Commits: C1=45ab588, C2=5a9efe4, C3=<pending>
- Next: 进入 R2，补 operator-facing smoke script 与脚本化 readiness/shutdown 证据。

### R2 Readiness / shutdown 回归与操作员 smoke 证据
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/contract/test_personal_assistant_main_contract.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py tests/e2e/test_personal_assistant_main_e2e.py`
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
