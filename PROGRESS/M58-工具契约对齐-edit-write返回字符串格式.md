# M58 - 工具契约对齐（edit/write 返回字符串格式）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/integration/test_m8_agent_tool_hook_r81_integration.py`
- Result:
  - `1 failed, 19 passed`（2026-03-04）
  - 失败用例：`test_bash_without_timeout_does_not_inject_default`（`bash` 既有问题，超出 M58 scope）

### Plan（一次性拆分）
- Context:
  - 当前 `edit`/`write` 返回结构仍偏向内部字段（如 `bytes_written`、`first_changed_line`），与设计稿期望的 Agent 可读文本 + `details` 结构存在偏差。
  - 约束：只改 builtins 与相关测试，不触碰 CLI/read/bash/task。
- Decision:
  - 单 Roadpoint（R1）完成 edit/write 契约对齐：先用测试锁定成功文本与错误语义，再最小实现对齐。
- Rationale:
  - 该里程碑目标集中于工具协议层，单 Roadpoint 可避免过度拆分并保持变更原子性。
- Evidence:
  - Tests: 基线门禁显示 1 个非本 scope 既有失败，其余通过。
  - Entry: 设计锚点来自 `内核设计细化/工具设计细化.md` 中 edit/write 返回契约。
- Rollback:
  - 回退到本计划提交前的稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 Red：先补/改 `tests/unit/test_tools_builtins.py`，锁定目标契约并观察红测。
