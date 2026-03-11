# M111 Gateway 运行时装配为真正常驻进程

## 前置确认
- 已先阅读 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、`docs/NodeGateway-SPEC.md`、现有 `src/personal_assistant/` 运行时与相关测试。
- 本 Milestone 的代码与文档将遵守 `COMMENTING_GUIDE.md` 的 public API docstring / 注释规范。
- 参考 LOGBOOK：真实入口与生命周期能力必须经过可验证的入口测试，不能只凭设计层或局部单测判断“已接线完成”；本次验收将补 readiness/shutdown coverage 与 operator-facing smoke evidence。

## 当前处境
- Milestone: M111 / Gateway 运行时装配为真正常驻进程
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M111`
- branch: `milestone/M111`
- 测试门禁命令: `PYTHONPATH=src pytest -q tests/contract/test_personal_assistant_main_contract.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py tests/e2e/test_personal_assistant_main_e2e.py`
- 基线结果: `18 passed`；当前门禁已全绿，因此后续必须新增覆盖并保持门禁无回归。
- 允许改动范围: `src/personal_assistant/**`、`tests/**personal_assistant*.py`、`tests/contract/test_personal_assistant_main_contract.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、共享 `data/dev-tasks.json`
- 禁止改动范围: `src/coding_cli/**`、与本次 Gateway runtime assembly 无关的广泛 IM 特性扩展
- prevention / 注意事项:
  - 复用现有 `gateway/bootstrap.py`、`gateway/inbound_pipeline.py`、`scheduler/heartbeat_scheduler.py`、`ws/im_connection.py`、`config/local_store.py`，禁止整体重写。
  - 目标是把现有组件装配成长驻进程与优雅启停，不是引入新架构。
  - 必须补齐 readiness / shutdown 测试与 smoke script/evidence。
  - 配置驱动仅限本地静态配置，明确不做热重载与额外功能面。

## Roadpoints

### R1 运行时装配与优雅生命周期
- Status: DONE
- Acceptance:
  - `GatewayRuntime` 不再 start 后立即 stop，而是保持常驻直到收到退出信号/停止请求
  - 启动顺序符合 `docs/NodeGateway-SPEC.md:45-52`：load config → start kernel and probe health → start channels → start heartbeat scheduler → optional IM websocket → ready
  - 关闭顺序符合 `docs/NodeGateway-SPEC.md:54-60` 的逆序要求
  - 本地配置能驱动 heartbeat 调度与可选 IM websocket 生命周期
  - 运行时组件通过现有模块装配完成，不引入跨范围的新架构
- Tests Plan:
  - unit: 需要，验证常驻等待、signal/stop 触发、启动/关闭顺序、异常清理顺序
  - contract: 需要，扩展入口契约，确保 `main.py` 仍是产品入口
  - integration: 需要，使用 fake channels / fake heartbeat runner / fake IM task 验证完整装配与 graceful shutdown
  - e2e: 需要，经真实入口调用 `run_gateway()` 证明配置加载、运行时进入 ready 并在 stop 后退出
- Expected Tests:
  - `tests/unit/personal_assistant/test_main.py`
  - `tests/contract/test_personal_assistant_main_contract.py`
  - `tests/e2e/test_personal_assistant_main_e2e.py`
- DoD:
  - `PYTHONPATH=src pytest -q tests/contract/test_personal_assistant_main_contract.py tests/integration/test_personal_assistant_bootstrap_integration.py tests/integration/test_personal_assistant_server_integration.py tests/e2e/test_personal_assistant_main_e2e.py` 全绿
  - 完成 C1/C2/C3
  - `PROGRESS` 记录启动/关闭顺序证据、回滚点、提交哈希

### R2 Readiness / shutdown 回归与操作员 smoke 证据
- Status: TODO
- Acceptance:
  - 至少存在一条可验证 readiness/shutdown 的集成或 e2e 测试，覆盖常驻进程 ready 前后状态
  - 提供 operator-facing smoke script 或等价脚本化证据，证明本地配置可驱动启动、保持常驻、再优雅关闭
  - smoke 证据不依赖手工解释，输出能看出 ready / shutdown 完成
  - 相关文档写清如何复现与当前约束边界
- Tests Plan:
  - unit: 可选；仅在 smoke 支撑代码需要独立逻辑时补充
  - contract: 不新增；沿用 R1 入口契约
  - integration: 需要，覆盖 readiness / shutdown 观测点与顺序日志
  - e2e: 需要，补 smoke script 执行路径或脚本化验证
- Expected Tests:
  - `tests/unit/personal_assistant/test_main.py`（如需要）
  - `tests/e2e/test_personal_assistant_main_e2e.py`
  - 可能新增 `tests/integration/test_personal_assistant_main_runtime_integration.py` 或并入现有 `test_main.py`
- DoD:
  - 测试门禁命令全绿
  - 完成 C1/C2/C3
  - `PROGRESS` 记录 smoke 命令、ready/shutdown 证据、回滚点、提交哈希
