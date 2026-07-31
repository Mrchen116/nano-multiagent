# M108 — REPL 粘贴与退出语义修复

## Milestone Context
- Milestone: M108 / Coding CLI REPL 粘贴与退出语义修复
- execution_mode: parallel
- use_worktree: true
- worktree_dir: /Users/czj/Repos/nano-multiagent/.worktrees/M108
- branch: milestone/M108
- test_command: `PYTHONPATH=src python3 -m pytest tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -q`
- allowed_scope: `src/coding_cli/**`、`tests/unit/test_cli_main.py`、`tests/integration/test_cli_http_flow_integration.py`、`TASKS/**`、`PROGRESS/**`、必要时 `LOGBOOK.md`
- forbidden_scope: 不改 `agent`/`IM`/`personal_assistant` 业务语义；不改其他 milestone 文档与状态；不提交 `data/dev-tasks.json` symlink
- prevention_rules:
  - 遵守 SPEC 与 `docs/CodingCLI-SPEC.md`，REPL 生命周期与退出约束以 SPEC 为准。
  - `commands.py` 只做编排，不回流输入/渲染细节。
  - REPL 异步事件消费继续遵守 `run_id/event_id` 语义，不在本 Milestone 扩散无关逻辑。
  - `/exit` 必须先停止接受与派发后续输入，再清理队列并关闭 managed 子进程。
  - 注释与 docstring 遵守 `COMMENTING_GUIDE.md`。
- baseline:
  - `PYTHONPATH=src python3 -m pytest tests/coding_cli -q` 失败，原因是仓库不存在该路径；调整为本里程碑 focused test 命令。

## Roadpoints

### R1 输入聚合：多行粘贴应作为一次用户输入提交
- Status: DONE
- Acceptance:
  - raw terminal 输入在一次粘贴中出现多个换行时，应聚合为单条逻辑输入，而不是逐行立即提交。
  - 最终提交给 `send_message` / `send_message_async` 的 text 保留换行内容。
  - 非粘贴的普通 Enter 提交仍保持单行提交语义。
  - slash 命令识别不被多行普通文本误伤。
- Tests Plan:
  - unit: 是。覆盖输入状态机/读取器对多行粘贴聚合行为。
  - contract: 否。HTTP 契约未变化。
  - integration: 是。覆盖 REPL 到 async client 的一次提交语义。
  - e2e: 否。本里程碑以 focused tests 为主，真实入口由 integration 近似覆盖。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_read_interactive_line_groups_multiline_paste_into_single_submission`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_async_multiline_paste_submits_single_message`
  - 如需入口级补强：`tests/integration/test_cli_http_flow_integration.py::test_cli_repl_multiline_paste_submits_single_async_message`
- DoD:
  - `test_command` 全绿
  - C1/C2/C3 齐全
  - PROGRESS 记录决策/证据/哈希

### R2 退出语义：/exit 立即止收止派并清队
- Status: DONE
- Acceptance:
  - `/exit` 一旦执行，REPL 不再等待 backlog 自然排空才允许退出。
  - `/exit` 后不再派发队列中尚未开始的消息，队列被清空。
  - managed 模式退出时仍调用子进程 stop，符合 SPEC 的 terminate/kill 生命周期。
  - focused tests 覆盖“已有排队消息时退出”和“退出后不再继续处理 queued message”。
- Tests Plan:
  - unit: 是。覆盖 run queue close/discard 与 REPL `/exit` 编排。
  - contract: 否。外部 API 契约未变。
  - integration: 是。覆盖 managed/async REPL 在退出时的清队与 stop 调用。
  - e2e: 否。已有 managed live e2e 成本较高，本 milestone 不扩张。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_exit_discards_queued_messages_before_processing`
  - `tests/unit/test_cli_main.py::test_repl_run_queue_close_can_discard_pending_messages`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_managed_exit_discards_queued_messages_and_stops_server`
- DoD:
  - `test_command` 全绿
  - C1/C2/C3 齐全
  - PROGRESS 记录决策/证据/哈希
