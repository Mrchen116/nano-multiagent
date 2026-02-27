# TASKS (Current Milestone: M8)

## [DONE] R8.1 runtime/loop/tools Hook 深度集成
- Steps:
  - 先补 hooks 集成失败测试：runtime `input/before_agent_start` + tools `tool_call/tool_result`（Red）
  - 在 `agent.runtime.run()` 接入 `input -> before_agent_start -> agent_start`
  - 在 `agent.loop` 接入 `turn_start -> message_start/update/end -> turn_end`
  - 在 `tools.registry.execute()` 接入 `tool_call -> tool_execution_start/update/end -> tool_result`
  - 让拦截结果生效：`input transform/handled`、`tool_call block`、`tool_result rewrite`
  - 保持 fail-open：hook 异常/超时不崩主流程
  - 运行新增四类测试与 `pytest -q` 全量验收
- Expected Tests:
  - `tests/unit/test_agent_runtime_hooks.py`
  - `tests/contract/test_hook_integration_contract.py`
  - `tests/integration/test_hooks_runtime_tools_integration.py`
  - `tests/e2e/test_hooks_runtime_http_e2e.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R8.1 hash 与证据
  - 不进入 M9 skills 与 M13 hooks 查询 API

## [DONE] R8.2 agent-tool-hook 深度集成补强（专项回归 + output 改写接线）
- Steps:
  - 增加专项集成红测 `tests/integration/test_m8_agent_tool_hook_r81_integration.py`（Red）
  - 修正 `tool_result` 拦截后的 `output` 改写接线（Green）
  - 验证 `tool_call block` 发生在工具执行与参数校验前
  - 验证 runtime `input transform/handled` 与 fail-open 语义保持正确
  - 执行 `pytest -q tests/integration/test_m8_agent_tool_hook_r81_integration.py` 与 `pytest -q`
  - 四文档写入 R8.1 基线链与 R8.2 补强链双映射并补齐 C3
- Expected Tests:
  - `tests/integration/test_m8_agent_tool_hook_r81_integration.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R8.2 hash 与证据
  - 不进入 M9 skills 与 M13 hooks 查询 API

## Milestone M8 状态
- R8.1 基线链已闭环：`296e21b` -> `fb77fe1` -> `2aa5fae`。
- R8.2 补强链已闭环：`7e7fd18` -> `532f34a` -> `(this docs commit)`。
- 范围严格限定在 runtime/loop/tools Hook 深度接线。
