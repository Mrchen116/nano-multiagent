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

### R1.1 edit/write 契约对齐与门禁收口
- Context:
  - `edit`/`write` 成功返回仍是内部字段，不满足设计稿要求的 Agent 文本反馈。
  - 基线门禁存在同文件旧测失败：`run_command` 已委托 `run_command_stream`，但测试仍 mock `subprocess.run`。
- Decision:
  - `edit` 成功返回改为 `content[0].text="Successfully replaced text in {path}."`，并在 `details` 提供 `diff` 与 `firstChangedLine`。
  - `write` 成功返回改为 `content[0].text="Successfully wrote {bytes} bytes to {path}"`。
  - `edit` 错误语义改为：未命中 `Could not find the exact text to replace`、非唯一 `Found multiple matches; text must be unique`、无变化 `No changes made`。
  - 最小修正 `test_bash_without_timeout_does_not_inject_default`：改为 mock `ToolSafety.run_command_stream` 并断言 `timeout is None`，不改 `bash.py`。
- Rationale:
  - 直接对齐工具输出契约可确保 Agent 端展示与设计稿一致。
  - 仅修正过期测试入口可恢复门禁，且不引入 scope 外行为改动。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_tools_builtins.py tests/integration/test_m8_agent_tool_hook_r81_integration.py` -> `22 passed`。
  - Entry: `test_write_overwrites_existing_file` 与 `test_edit_replaces_exact_text_once` 已断言新成功文本；`test_edit_fails_*` 已覆盖三类错误语义。
- Rollback:
  - 若需回退，优先回到 C1 `f3f0bf0`（仅测试红测锁定）；或回退到计划提交 `28f018b`。
- Commits: C1=`f3f0bf0`, C2=`6166a4f`, C3=`TBD`
- Next:
  - 提交文档 C3，随后执行 `rebase -> merge main -> push`，更新 `dev-tasks.json` 为 `DONE` 并清理 worktree。
