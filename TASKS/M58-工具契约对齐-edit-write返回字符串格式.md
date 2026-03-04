# M58 - 工具契约对齐（edit/write 返回字符串格式）

## Milestone Contract
- Milestone: `M58`
- Title: `工具契约对齐-edit/write 返回字符串格式`
- Goal: 对齐 `edit`/`write` 工具成功返回文本与 `details` 结构，让 Agent 侧拿到与设计稿一致的反馈。
- Scope:
  - Allowed: `src/nano_multiagent/tools/builtins/edit.py`、`src/nano_multiagent/tools/builtins/write.py`、`tests/unit/test_tools_builtins.py`、`tests/integration/test_m8_agent_tool_hook_r81_integration.py`（仅必要补测）、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: `src/nano_multiagent/cli/**`、`src/nano_multiagent/tools/builtins/read.py`、`src/nano_multiagent/tools/builtins/bash.py`、`src/nano_multiagent/tools/builtins/task.py`
- Prevention Rules:
  - 严格按 C1/C2/C3 执行。
  - 仅解决 M58 契约对齐，不做额外重构。
  - 不回滚/覆盖他人与本 Milestone 无关改动。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/integration/test_m8_agent_tool_hook_r81_integration.py`
- Result:
  - `1 failed, 19 passed`（2026-03-04）
  - 失败点：`tests/unit/test_tools_builtins.py::test_bash_without_timeout_does_not_inject_default`（`captured["timeout"]` KeyError），属于 `bash` 现存问题，超出 M58 允许范围。

## Roadpoints

### R1 edit/write 成功文本与 details 契约对齐
- Acceptance:
  - `edit` 成功返回 `Successfully replaced text in {path}.`。
  - `edit` 在 `details` 暴露 `diff` 与 `firstChangedLine`（camelCase）。
  - `write` 成功返回 `Successfully wrote {bytes} bytes to {path}`。
  - `edit` 的“未命中/非唯一/无变化”错误语义与设计一致。
- Tests Plan:
  - unit: 选；主变更在 builtins，直接锁定返回结构与错误语义。
  - contract: 不单列；本仓当前对 builtins 契约通过 unit 覆盖即可。
  - integration: 选；执行指定门禁，确保 hook 链路对 output/content 兼容。
  - e2e: 不选；本里程碑仅工具层契约对齐，不涉及入口行为变更。
- Expected Tests:
  - `tests/unit/test_tools_builtins.py::test_write_overwrites_existing_file`
  - `tests/unit/test_tools_builtins.py::test_edit_replaces_exact_text_once`
  - `tests/unit/test_tools_builtins.py::test_edit_fails_on_multiple_matches`
  - `tests/unit/test_tools_builtins.py`（新增 edit 未命中/无变化语义测试）
  - `tests/integration/test_m8_agent_tool_hook_r81_integration.py`
- DoD:
  - R1 按 C1/C2/C3 完成。
  - `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/integration/test_m8_agent_tool_hook_r81_integration.py` 满足门禁结论（允许保留基线同源、且不在 M58 scope 的既有失败）。
  - `PROGRESS` 记录设计取舍、证据、回退点、提交哈希。
- Status: `TODO`
