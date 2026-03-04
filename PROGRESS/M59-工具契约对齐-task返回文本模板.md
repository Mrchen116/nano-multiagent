# M59 - 工具契约对齐-task 返回文本模板

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_task_tool_blocking.py tests/unit/test_task_tool_non_blocking.py tests/contract/test_task_tool_contract.py tests/integration/test_task_blocking_integration.py tests/integration/test_task_non_blocking_integration.py tests/e2e/test_task_tool_blocking_e2e.py tests/e2e/test_task_tool_non_blocking_e2e.py`
- Result:
  - `14 passed, 14 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - 当前 `task` 返回结构化 payload，与设计稿“直接返回字符串模板”不一致。
  - 约束：仅改 task 工具与指定测试，不触碰 CLI 范围。
- Decision:
  - 将 M59 收敛为单一 Roadpoint `R59.1`，以“先红后绿”一次完成四路径模板 + 错误模板 + 校验优先级验证。
- Rationale:
  - 变更核心集中在 `task.py` 输出层，单 Roadpoint 可最小化并行冲突与回滚成本。
- Evidence:
  - Tests: 基线门禁全绿（`14 passed`）。
  - Entry: 目标入口均通过 `tool.run` 与 `tool_registry.execute` 可直达验证。
- Rollback:
  - 回退到本计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 进入 R59.1：先补红测锁定字符串模板契约。
