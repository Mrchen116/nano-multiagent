# M57 - 工具契约对齐-bash 返回字符串格式

## Milestone Contract
- Milestone: `M57`
- Title: `工具契约对齐-bash 返回字符串格式`
- Goal: 将 `bash` 工具输出与错误文本收口到《内核设计细化/工具设计细化.md》要求，包含尾部截断提示与 `fullOutputPath` 文案。
- Scope:
  - Allowed: `src/nano_multiagent/tools/builtins/bash.py`、`src/nano_multiagent/tools/safety.py`（仅当 bash 截断/输出策略需要）、`tests/unit/test_tools_builtins.py`、`tests/contract/test_tools_bash_contract.py`、`tests/integration/test_tools_bash_integration.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: `src/nano_multiagent/cli/**`、`src/nano_multiagent/tools/builtins/read.py`、`src/nano_multiagent/tools/builtins/edit.py`、`src/nano_multiagent/tools/builtins/write.py`、`src/nano_multiagent/tools/builtins/task.py`
- Prevention Rules:
  - 严格按 C1/C2/C3 执行。
  - 仅解决 M57，不做额外重构。
  - 保持改动最小且限定在允许范围内。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_bash_contract.py tests/integration/test_tools_bash_integration.py`
- Result:
  - `19 passed, 1 failed`（失败：`tests/unit/test_tools_builtins.py::test_bash_without_timeout_does_not_inject_default`）

## Roadpoints

### R1 成功输出收口（统一 text + 截断提示 + fullOutputPath）
- Acceptance:
  - `bash` 成功返回单一 `content` 字符串（合并 stdout/stderr，空输出返回 `(no output)`）。
  - 发生截断时，`content` 末尾追加 `Showing lines ... Full output: ...` 提示。
  - 截断提示按触发类型区分行数截断/字节截断文案，且可从结果中追溯 `fullOutputPath`。
  - 不注入默认 timeout（仅透传用户显式 timeout）。
- Tests Plan:
  - unit: 选；覆盖成功/截断/timeout 透传行为。
  - contract: 选；锁定返回字段与提示文本契约。
  - integration: 选；通过 registry 验证落盘可追溯。
  - e2e: 不选；本里程碑只涉及工具内核契约，不新增 CLI/HTTP 入口行为。
- Expected Tests:
  - `tests/unit/test_tools_builtins.py::test_bash_without_timeout_does_not_inject_default`
  - `tests/unit/test_tools_builtins.py::test_bash_truncation_returns_full_output_path`
  - `tests/contract/test_tools_bash_contract.py::test_bash_truncation_contract_exposes_full_output_path`
  - `tests/integration/test_tools_bash_integration.py::test_registry_executes_bash_with_truncation_and_persisted_output`
- DoD:
  - R1 的 C1/C2/C3 完整。
  - `test_command` 全绿。
  - PROGRESS 记录决策、证据、回退点、提交哈希。
- Status: `TODO`

### R2 错误文案收口（non-zero / timeout / abort）
- Acceptance:
  - 非 0 退出抛错 message 使用 `Command exited with code {exitCode}` 样式，并保留前置输出文本。
  - timeout 抛错 message 使用 `Command timed out after {timeoutSecs} seconds`，结构中可解析 timeout 与路径。
  - abort 抛错 message 使用 `Command aborted`，结构中可解析 `aborted` 状态与路径。
  - 错误 details 统一包含可机读字段（`exitCode/truncated/fullOutputPath/...`）。
- Tests Plan:
  - unit: 选；覆盖 non-zero/timeout/abort message 与 details。
  - contract: 选；固定 tool error message 与 details 字段。
  - integration: 选；验证 registry 路径下错误字段不丢失。
  - e2e: 不选；同 R1。
- Expected Tests:
  - `tests/unit/test_tools_builtins.py::test_bash_reports_non_zero_exit`
  - `tests/unit/test_tools_builtins.py::test_bash_handles_timeout`
  - `tests/unit/test_tools_builtins.py::test_bash_aborted_contract_message_and_details`
  - `tests/contract/test_tools_bash_contract.py::test_bash_timeout_contract_exposes_stable_details`
  - `tests/integration/test_tools_bash_integration.py::test_registry_bash_signal_error_keeps_signal_details`
- DoD:
  - R2 的 C1/C2/C3 完整。
  - `test_command` 全绿。
  - PROGRESS 记录关键取舍与回退点。
- Status: `TODO`
