# M42 - CLI界面收敛：对齐Codex交互观感（独立并行修复）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `94 passed, 38 warnings`

## Notes from LOGBOOK / M39 / M40
- `send-message` 必须保持 stdout 单 JSON，REPL 事件噪声不能污染单命令模式。
- REPL 异步事件必须保留 `event_id` 去重与 `run_id` 过滤，避免串线。
- M40 已有“运行中输入排队”能力，M42 重点是终端渲染稳定性与信息架构收敛，不改内核。
- 当输出链路涉及实时终端渲染时，优先保证“稳定可读”再追求视觉增强。

### R1 终端渲染稳定化（并发输出不串行错位）
- Context:
  - M40 的异步队列将后台结果直接写到同一终端流，和 `repl_input.render_interactive_line` 的 ANSI 行编辑并发时会产生错位与菜单残影。
  - `tool_end`/`text_delta` 预览未单行化，遇到多行文本会直接把换行注入 REPL，形成大段缩进噪声。
- Decision:
  - 在 `repl_input` 增加全局渲染锁与活动提示行快照，并新增 `emit_external_text`：外部输出前清理编辑行，输出后自动重绘当前提示行。
  - `commands._run_repl` 的后台队列输出路径改为通过 `emit_external_text` 注入，避免与输入光标竞争。
  - `repl_events._preview_event_value` 统一把 `\\r/\\n` 归一并转义为 `\\n`，确保预览永远单行。
- Rationale:
  - 只改 CLI 显示链路即可消除错位与缩进问题，不触碰内核协议。
  - 后台输出统一走安全注入口，能在保持“运行中可继续输入”前提下稳定终端表现。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_repl_input_external_output_replays_prompt_without_layout_break tests/unit/test_cli_main.py::test_send_message_with_async_events_sanitizes_multiline_tool_preview`（2 failed）
    - 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_repl_input_external_output_replays_prompt_without_layout_break tests/unit/test_cli_main.py::test_send_message_with_async_events_sanitizes_multiline_tool_preview tests/unit/test_cli_main.py::test_run_cli_repl_queues_user_input_while_previous_async_run_is_in_progress`
    - 全绿：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（94 passed, 38 warnings）
  - Entry:
    - 多行 `tool output` 被渲染成 `line1\\nline2` 单行文本，不再拆成多行污染终端。
    - 队列线程输出结束后，提示行可被重绘，输入排队流程仍可用。
- Rollback:
  - `05f39bc`（R1 红测提交）
- Commits: C1=`05f39bc`, C2=`b2c53ed`, C3=`79b8075`
- Next:
  - 进入 R2：重排 REPL 单轮摘要为答案优先、紧凑状态与工具过程。

### R2 输出信息架构收敛（答案优先 + 紧凑摘要）
- Context:
- R1 虽已消除错位/缩进，但单轮结果仍按 `Status/Tools/Answer/Usage` 大段分区，真实交互里读答案需要跨段扫描，观感偏“调试面板”而非会话。
- 约束是保留 `send-message` 单 JSON 契约与输入排队能力，因此只能在 REPL 打印层收敛，不改 HTTP 协议与内核结构。
- Decision:
- `repl_render.print_repl_turn_summary` 调整为“答案优先 + 紧凑标签行”：先打印 `Assistant`，再输出 `[status]`、`[progress]`、`[tool]`、`[usage]`。
- 新增 `_compact_status_updates` / `_compact_tool_updates` 去重与截断；`_normalize_tool_update` 将 `[tool x]` 统一规整为 `[tool] x ...`，降低噪声并保持关键语义。
- `print_repl_turn_error` 收敛为 `Assistant(empty) + [status]/[error]/[hint]/[usage]`，保留 `layer/suggestion` 诊断信息。
- Rationale:
- 以最小改动覆盖可读性问题：只动 CLI 渲染函数和断言，不引入新协议字段或跨层耦合。
- 工具与进度信息仍保留，避免“只剩答案看不到过程”；但通过去重/截断把默认输出控制在可扫读密度。
- Evidence:
  - Tests:
    - 红测提交：`26a4694`（新增紧凑摘要与错误摘要断言，针对旧格式失败）。
    - 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（94 passed, 38 warnings）。
  - Entry:
    - 成功流输出形态为 `Assistant -> [status] -> [tool] -> [usage]`，并保持 `final:...` 正文优先。
    - 失败流输出形态为 `Assistant: (empty)` + `[error]` + `[hint] suggestion=...`，仍可定位 layer 与建议。
- Rollback:
- `26a4694`（R2 红测提交）
- Commits: C1=`26a4694`, C2=`37d2935`, C3=`71d36b3`
- Next:
  - 进入 R3：rebase main、复跑门禁、整体合并并更新 `dev-tasks`。

### R3 收口与集成（门禁、文档、合并）
- Context:
- 主仓 `main` 有并行脏改动（`ROADMAP.md` 等），不能在主工作区直接执行合并，需避免触碰他人现场。
- 目标是在不影响并行开发前提下完成 M42 整体集成，并将派工板状态改为 `DONE`。
- Decision:
- 在 M42 worktree 执行 `git fetch origin` + `git rebase origin/main` 并复跑门禁；通过后获取 `data/locks/merge.lock`。
- 在 `/tmp` 建立临时集成 worktree（`integration/M42`）从 `origin/main` 合并 `milestone/M42`（`--no-ff`）并 push 到 `origin/main`。
- 里程碑状态通过 `dev_tasks.py update` 脚本写入 `data/dev-tasks.json`，不手改 JSON。
- Rationale:
- 临时 worktree 方案绕开主仓脏状态，同时满足“整体集成到 main”的要求，不回退或覆盖其他 agent 的变更。
- 使用共享 merge lock 可避免并行里程碑同时写 main 的竞态。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（94 passed, 38 warnings）。
  - Entry:
    - `git rebase origin/main`：`Current branch milestone/M42 is up to date.`
    - 临时集成 worktree merge+push：`origin/main` 从 `feb26ea` 更新到 `9fcedb2`。
- Rollback:
- `71d36b3`（R2 文档完成点，可重新执行 R3 集成流程）
- Commits: C1=`N/A（收口路标无独立红测提交）`, C2=`9fcedb2`, C3=`本提交（docs R3.1）`
- Next:
  - 更新 `data/dev-tasks.json` 的 M42 状态为 `DONE`，写入 commits/tests/result。
