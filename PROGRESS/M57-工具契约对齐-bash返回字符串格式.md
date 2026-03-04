# M57 - 工具契约对齐-bash 返回字符串格式

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_bash_contract.py tests/integration/test_tools_bash_integration.py`
- Result:
  - `19 passed, 1 failed`（`tests/unit/test_tools_builtins.py::test_bash_without_timeout_does_not_inject_default`）

### Plan（一次性拆分）
- Context:
  - 当前 `bash` 工具返回 `stdout/stderr` 分离字段，与《工具设计细化》约定的“统一文本输出 + 尾部截断提示 + full output 文案”不一致。
  - 约束：仅改 `bash` 与其 safety 输出策略，不触达 CLI 及其它 builtins。
- Decision:
  - 拆为 `R1 成功输出收口` 与 `R2 错误文案收口` 两个 Roadpoint，均执行 C1/C2/C3。
  - 先红测锁定目标契约，再最小实现，最后文档收口。
- Rationale:
  - 通过测试先行可避免改动输出格式后出现“看起来对齐但结构不可解析”的隐性回归。
- Evidence:
  - Tests: 基线门禁已跑，存在 1 个失败且在 M57 范围内。
  - Entry: 主要改动面定位为 `src/nano_multiagent/tools/safety.py` 与 `src/nano_multiagent/tools/builtins/bash.py`。
- Rollback:
  - 回退到本计划提交前的稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1：补“成功统一文本 + 截断提示 + fullOutputPath 可追溯”的红测并进入实现。

### R1 成功输出收口（统一 text + 截断提示 + fullOutputPath）
- Context:
  - 现状返回 `stdout/stderr` 分离字段，且截断时缺少统一文本提示，不满足里程碑契约。
  - 需要在不改 CLI 的前提下，收口为单一 `content` 文本并保留可追溯路径。
- Decision:
  - `bash` 成功结果改为 `content + exitCode + truncated (+ fullOutputPath)`。
  - 在 `ToolSafety` 中按合并流生成尾部预览；截断时自动持久化全量输出并在文本末尾追加 `Showing lines ... Full output: ...` 提示。
  - `timeout=None` 路径改为通过 `run_command_stream` 透传测试桩验证，不再依赖 `subprocess.run`。
- Rationale:
  - 把“输出合并/截断提示”的逻辑集中在 safety 层可复用且更容易保证文本与落盘路径一致。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py::test_bash_success_merges_stdout_and_stderr_into_content tests/unit/test_tools_builtins.py::test_bash_truncation_returns_full_output_path tests/contract/test_tools_bash_contract.py::test_bash_truncation_contract_exposes_full_output_path tests/integration/test_tools_bash_integration.py::test_registry_executes_bash_with_truncation_and_persisted_output` -> `4 failed`。
    - 绿测（子集）：同上 + `tests/unit/test_tools_builtins.py::test_bash_without_timeout_does_not_inject_default` -> `5 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_bash_contract.py tests/integration/test_tools_bash_integration.py` -> `21 passed`。
  - Entry:
    - `bash` 成功输出返回统一字符串，截断文案可直接定位 `fullOutputPath`。
- Rollback:
  - `548238e`（R1 红测提交）。
- Commits: C1=`548238e`, C2=`9ff069d`, C3=`本提交`
- Next:
  - 进入 R2：锁定 non-zero / timeout / abort 错误 message 与 details 结构契约，再做最小实现收口。

### R2 错误文案收口（non-zero / timeout / abort）
- Context:
  - R1 完成后，错误路径仍沿用旧文案（`command exited with non-zero status` / `command timed out after ...s`）且字段命名混杂，不符合里程碑契约。
  - 需要保证错误 message 可读一致，并在 details 中保留可机读路径信息。
- Decision:
  - `BashTool` 对错误统一输出：
    - 非 0：`Command exited with code {exitCode}`
    - timeout：`Command timed out after {timeoutSecs} seconds`
    - abort：`Command aborted`
  - `ToolSafety.run_command_stream` 超时不再直接抛错，改为回传 `timed_out/aborted` 状态与已有输出，再由 `BashTool` 统一封装错误 message/details。
  - details 统一补齐 `exitCode/content/truncated/fullOutputPath`，并保留 `signal/signalNumber`（及兼容别名）供错误路径解析。
- Rationale:
  - 错误语义收口到 `BashTool` 可避免 safety 层与工具层分别拼文案导致契约分裂。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py::test_bash_reports_non_zero_exit tests/unit/test_tools_builtins.py::test_bash_handles_timeout tests/unit/test_tools_builtins.py::test_bash_aborted_contract_message_and_details tests/contract/test_tools_bash_contract.py::test_bash_timeout_contract_exposes_stable_details tests/contract/test_tools_bash_contract.py::test_bash_signal_contract_exposes_signal_details tests/integration/test_tools_bash_integration.py::test_registry_bash_signal_error_keeps_signal_details` -> `6 failed`。
    - 绿测（子集）：同上 -> `6 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/contract/test_tools_bash_contract.py tests/integration/test_tools_bash_integration.py` -> `22 passed`。
  - Entry:
    - non-zero/timeout/abort 均输出统一文案；timeout 与截断路径可在 details 中解析 `fullOutputPath`。
- Rollback:
  - `bf29f1a`（R2 红测提交）。
- Commits: C1=`bf29f1a`, C2=`9798530`, C3=`本提交`
- Next:
  - 执行里程碑收口：更新 `dev-tasks.json` 为 DONE 并回传 summary/tests/commits。
