# M52 - 交互与脚本双通道契约固化（TTY/non-TTY）

日期：2026-03-04  
分支：`milestone/M52`  
工作区：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M52`

## Milestone 启动记录
- Context:
  - 目标是固化 TTY 与非交互脚本输出边界，避免 REPL 终端控制序列污染非 TTY 输出。
  - 仅允许修改 CLI 与指定测试文件；不触碰内核与非 CLI 目录。
- Decision:
  - 采用单一 Roadpoint：先补红测锁定双通道边界，再最小实现输出策略分流。
  - 门禁以用户指定命令为准，且补充 managed CLI 实跑片段作为入口证据。
- Rationale:
  - 基线已全绿，必须通过新增失败测试证明本里程碑新增能力，而不是“只复跑已有测试”。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `106 passed`
  - Entry: 已完成 LOGBOOK / 蓝图 / COMMENTING_GUIDE 启动阅读。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits:
  - plan: `ac8e26c`
- Next:
  - 执行 R1：先红测，再实现输出策略分流与门禁回归。

### R1 双通道输出策略分离与契约护栏
- Context:
  - 基线下 REPL 异步输出统一走 `repl_input.emit_external_text`，即使 `stdout` 非 TTY 也会输出回车/控制序列，存在日志污染风险。
  - 里程碑要求固定 TTY/non-TTY 双通道边界，同时保持 `send-message` 单 JSON 契约与 REPL 可读性。
- Decision:
  - 新增红测：non-TTY 场景禁止调用 `emit_external_text`，并在 integration 断言输出不含 `\\r`/ANSI。
  - 在 `cli/app/commands.py` 增加输出能力判定：TTY 继续走 `emit_external_text`；non-TTY 走纯文本块输出函数 `_emit_plain_repl_block`。
  - 保持 `_run_single_command` 与 `send-message` 路径不变，确保单命令 JSON 契约不受影响。
- Rationale:
  - 非 TTY 使用终端控制序列没有收益且会污染机读/日志；TTY 路径仍需保留交互体验与提示行恢复能力。
- Evidence:
  - Tests:
    - 红测（C1）：
      - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_run_cli_repl_non_tty_async_output_avoids_emit_external_text_path tests/unit/test_cli_main.py::test_run_cli_repl_tty_async_output_uses_emit_external_text_path tests/integration/test_cli_http_flow_integration.py::test_cli_repl_non_tty_async_output_avoids_terminal_control_sequences`
      - 结果：`2 failed, 1 passed`（non-TTY 仍调用 `emit_external_text`，且输出含 `\\r`）。
    - 绿测（C2）：
      - 同命令结果：`3 passed`
    - 全量门禁（C2 前复跑）：
      - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
      - 结果：`109 passed, 44 warnings`
  - Entry:
    - non-TTY REPL 异步流输出不再包含回车/ANSI 污染。
    - TTY 路径仍通过 `emit_external_text` 输出交互块。
- Rollback:
  - 回退到 `3ff9c8a`（仅测试）可复现缺口并重做实现。
- Commits: C1=`3ff9c8a`, C2=`20c8a69`, C3=`TBD`
- Next:
  - 更新 LOGBOOK 规则并提交 C3，随后进行 rebase/merge 与 dev_tasks DONE 收口。
