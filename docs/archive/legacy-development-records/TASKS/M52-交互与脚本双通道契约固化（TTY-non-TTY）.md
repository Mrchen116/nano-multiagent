# M52 - 交互与脚本双通道契约固化（TTY/non-TTY）

## Milestone Contract
- milestone_id: `M52`
- title: `交互与脚本双通道契约固化（TTY/non-TTY）`
- goal: 固化 TTY 与非交互脚本输出边界，防止相互污染。
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M52`
- branch: `milestone/M52`
- test_command: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- dev_tasks_path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- allowed_scope:
  - `src/nano_multiagent/cli/**`
  - `tests/unit/test_cli_main.py`
  - `tests/unit/test_cli_refactor_boundaries.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/contract/test_cli_error_contract.py`
  - `TASKS/**`
  - `PROGRESS/**`
  - `LOGBOOK.md`
- forbidden_scope:
  - `src/nano_multiagent/core/**`
  - `src/nano_multiagent/server/**`
  - `src/nano_multiagent/agent/**`
  - `src/nano_multiagent/runs/**`
  - `src/nano_multiagent/tools/**`
  - `src/nano_multiagent/session/**`
  - `src/nano_multiagent/llm/**`
- prevention_rules:
  - 只改 CLI 与指定测试文件；不改内核/API/工具/agent/server/session/llm。
  - 非交互命令保持 stdout 单 JSON；REPL 人类输出仅在交互通道。
  - 忽略并行里程碑改动，不回退无关文件。

## Startup Checklist
- [x] 已阅读 `LOGBOOK.md`
- [x] 已阅读 `内核设计蓝图.md`
- [x] 已阅读 `COMMENTING_GUIDE.md` 并承诺遵循
- [x] 已确认分支/工作区：`milestone/M52` @ `.../worktrees/M52`
- [x] 已确认范围约束与门禁命令
- [x] 已跑基线门禁：`106 passed`

## Roadpoints

### R1 双通道输出策略分离与契约护栏
- Acceptance:
  - REPL 输出路径按终端能力分流：TTY 使用交互渲染；non-TTY 使用纯文本块输出。
  - `send-message` 单 JSON stdout 契约保持稳定，不受 REPL 事件路径影响。
  - 在 non-TTY REPL 场景下，不输出 ANSI/回车覆写序列污染日志。
  - TTY REPL 下错误/状态/工具预览仍保持一致可读。
- Tests Plan:
  - unit: 选；验证 non-TTY 输出不含控制序列、TTY 路径仍走交互渲染。
  - contract: 选；复跑 CLI error/http-only 契约，锁定单 JSON 与边界不回归。
  - integration: 选；验证 non-TTY REPL 异步流输出契约与 `send-message` 单 JSON 保持。
  - e2e: 不选；本里程碑已有 managed CLI 实跑作为入口验收。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_non_tty_async_output_avoids_emit_external_text_path`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_tty_async_output_uses_emit_external_text_path`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_non_tty_async_output_avoids_terminal_control_sequences`
  - 以及门禁命令全量回归
- DoD:
  - `test_command` 全绿。
  - R1 完成 C1/C2/C3 三提交。
  - `PROGRESS` 写清决策、证据、回滚点、提交哈希。
- Status: `DONE`

## Delivery Notes
- C1 红测已锁定 non-TTY 不得走 `emit_external_text`，并新增 integration 护栏断言无 `\\r`/ANSI 污染。
- C2 已在 `src/nano_multiagent/cli/app/commands.py` 实现输出策略分流：TTY 走交互渲染，non-TTY 走纯文本块输出。
- 全量门禁：`109 passed, 44 warnings`。
