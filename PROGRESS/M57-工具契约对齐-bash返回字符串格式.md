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
