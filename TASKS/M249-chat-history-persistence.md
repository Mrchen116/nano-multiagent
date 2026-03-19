# TASKS: M249 personal_assistant 聊天历史落盘

## Milestone
- ID: M249
- Title: personal_assistant 聊天历史落盘到 workspace/chat_history/
- execution_mode: serial
- worktree: /Users/czj/Repos/nano-multiagent/.worktrees/M249
- branch: milestone/M249

## Baseline
- tests/unit/ 619 passed 全绿（baseline confirmed）
- tests/im_service/integration/test_m103_im_gateway_e2e.py::test_group_chat_uses_live_updated_profile_after_config_sync_in_same_conversation 预存在失败，与本 Milestone 无关

## SPEC 参考
- NodeGateway-SPEC §12 聊天历史落盘：path=`<agent_workspace>/chat_history/<session_id>.jsonl`，每行 `{"ts": "<ISO8601>", "role": "user"|"assistant", "content": "<text>"}`，hook 名称 `after_agent_reply`

## 设计说明
- `after_agent_reply` 不在 HookEventType（core/ 禁止修改）；用 3 个已存在事件组合实现等价语义：
  1. `input` intercept → 捕获用户输入 text，存入模块级 `_pending[session_id]["user_text"]`
  2. `message_end` observe → 捕获最后一条 assistant content，存入 `_pending[session_id]["assistant_text"]`
  3. `agent_end` observe → 从 `_pending` 取数据，写 JSONL，清理 `_pending[session_id]`
- workspace_root 来自 `ctx.metadata.get("cwd")`（runtime 注入）
- JSONL 路径：`<workspace_root>/chat_history/<session_id>.jsonl`

## Roadpoints

### R1 chat_history.py hook 实现（核心功能）

Acceptance:
1. `setup(hooks)` 正确注册 input/message_end/agent_end 三个 handler
2. `agent_end` 触发后，workspace/chat_history/<session_id>.jsonl 存在并含 user+assistant 两行
3. 目录不存在时自动 mkdir(parents=True, exist_ok=True)
4. 文件以追加模式打开，多轮对话不覆盖
5. 不修改 core/ 或 platform/ 任何文件

Tests Plan:
- unit: 正常写入/目录自动创建/多轮追加/missing-cwd-graceful-skip
- contract: JSONL 行字段验证（ts/role/content 存在且类型正确）
- integration: 不需要（hook 已通过 unit 测试 setup 调用链，无外部依赖）
- e2e: 不需要（hook 是文件 I/O，unit 覆盖全路径）

Expected Tests:
- `tests/unit/personal_assistant/test_chat_history_hook.py`
  - `test_writes_user_and_assistant_lines_after_agent_end`
  - `test_creates_directory_if_missing`
  - `test_appends_across_multiple_turns`
  - `test_skips_gracefully_when_no_cwd`
  - `test_jsonl_line_fields_valid`

DoD:
- test_command (`PYTHONPATH=src python -m pytest tests/unit/ -x -q`) 全绿
- C1/C2/C3 均已提交

Status: TODO

---

## Commits Log

（提交后补充）
