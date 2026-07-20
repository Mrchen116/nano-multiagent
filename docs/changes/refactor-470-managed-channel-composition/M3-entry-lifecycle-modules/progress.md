# refactor-470-M3 — Progress

## 启动记录

- 已完成 `motivation.md`、`design.md`、项目约定、`LOGBOOK.md`、`docs/TESTING_GUIDE.md` 与现有源码/测试结构阅读。
- 基线：`PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_gateway_launch.py tests/unit/personal_assistant/test_gateway_pid_lifecycle.py tests/unit/personal_assistant/test_gateway_main_command.py tests/unit/personal_assistant/test_auto_bind.py tests/unit/personal_assistant/test_gateway_reconnect_registration_gate.py tests/contract/test_personal_assistant_main_contract.py`，39 passed。
- 环境说明：M3 worktree 未建立 `.venv`，已确认主仓 `/Users/czj/Repos/nano-multiagent/.venv` 可用；后续测试显式使用该解释器并设置 `PYTHONPATH=src`，不改动工作树配置或产品代码。

### R1 — 迁移 IM bootstrap 与 register-ready 编排

- Context: HTTP node binding/auto-bind 与 register ACK 后的跨 owner 收敛原本落在入口和构造函数闭包中。
- Decision: 将 IM bootstrap client、operator feedback 与 bind token 解析迁入 `gateway.im_bootstrap`；将 binding 失败隔离、managed-channel replay、Agent profile reconcile 的既有顺序迁入 `ConnectionReadyCoordinator`。
- Rationale: bootstrap 只拥有 HTTP binding，coordinator 只拥有跨 owner 顺序；连接 sender 由 IMConnectionManager 在 register ACK 后直接传入，不再捕获尚未构造的 manager。
- Evidence:
  - Tests: 聚焦 `test_auto_bind.py`、`test_gateway_reconnect_registration_gate.py`、`test_gateway_build_runtime.py`、`test_gateway_relay_lifecycle.py` 共 52 passed；完整 `pytest -q -m "not e2e"` 为 3614 passed, 1 skipped, 20 deselected。
  - Entry: R3 统一执行隔离 Gateway 真入口验证。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 既有 auto-bind、register gate 与 binding failure 后仍 reconcile regression 均从真实 owner import 并通过。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: `git revert aa0cc10a2` 后恢复 bootstrap 与收敛逻辑在入口的位置。
- Commits: C1=7e8a0f52a, C2=aa0cc10a2, C3=待提交。
- Next: R2 迁移后台进程生命周期 owner。
