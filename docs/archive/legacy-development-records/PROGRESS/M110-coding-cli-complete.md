# M110 Coding CLI 完整态收口

## Baseline
- Gate: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/e2e/test_cli_managed_live_agent_e2e.py`
- Result: 113 passed, 1 skipped, 50 warnings
- Notes:
  - 当前门禁已绿，M110 重点是把 default UX / 验收覆盖 / smoke evidence 收到 SPEC 完整态。
  - `LOGBOOK.md` 中与本 milestone 直接相关的规则：REPL 事件必须保持 `event_id` 去重 + `run_id` 过滤；single-command stdout 只能输出最终 JSON；`/exit` 只能截断未开始的 queued tail，不能吞掉 active candidate。
  - `COMMENTING_GUIDE.md` 已确认遵守：public API/入口写契约型 docstring，注释只解释意图/边界/代价。

## Plan Commit
- `f04f9c6` `docs(M110): 建立执行计划`

### R1 默认启动路径切换到 Managed
- Context: SPEC 要求无参数即进入 Managed，但现状是隐式 remote；同时大量既有 CLI 测试把“提供 --base-url 但未写 --mode”的路径当作 remote 调试入口使用，不能为了修默认 UX 直接改写全部含 `--base-url` 的隐式语义。
- Decision: 仅在“未显式给 `--mode`、未给 CLI `--base-url`、也没有 `NANO_MULTIAGENT_API_BASE_URL`”时，把默认 mode 解析为 managed；其它隐式带 URL 的路径继续落到 remote，显式 `--mode remote` 仍最高优先。
- Rationale: 这样既满足 SPEC 的无参数 front-door，又不破坏现有 `--base-url` 调试/远端调用面和 single-command JSON 合约。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/e2e/test_cli_managed_live_agent_e2e.py` → `117 passed, 1 skipped`
  - Entry: 新增 unit 覆盖无参数 REPL / 无参数单命令默认 managed，以及“带 `--base-url` 但未指定 mode 时仍走 remote”。
- Rollback: `a5b4279`（R1 C1 红灯测试）
- Commits: C1=`a5b4279`, C2=`9484fce`, C3=`383c4ad`
- Next: R2 补 live/default 验收覆盖，并记录真实 CLI smoke 证据与 §10 对应关系。

### R2 验收口径补齐与真实 smoke 证据固化
- Context: R1 修完后，默认路径已符合 SPEC，但还存在一个真实产品风险：若用户机器上设置了 `NANO_MULTIAGENT_API_BASE_URL`，无参数入口仍会被劫持成 remote 语义；另外本 milestone 需要把 §10 的 10 条验收标准、M108 的 multiline paste 与 `/exit` 清队行为，以及真实启动/退出 smoke evidence 串成一套可复核记录。
- Decision: 新增 unit 红灯锁定“无显式 mode 的 REPL/单命令默认入口忽略 `NANO_MULTIAGENT_API_BASE_URL`，继续落到内建 localhost managed front-door”；同时在文档中给出 §10 验收矩阵与两组真实 smoke：一组证明 no-arg 的确走 managed 启动分支（当前环境因 8000 被占用而明确报 managed 端口冲突），一组证明显式 managed + 空闲端口可真实启动并在 `/exit` 后清理监听。
- Rationale: 这既把“默认 managed”从测试语义提升到真实操作语义，也避免通用 HTTP env 把产品前门变成隐藏 remote 模式；对用户来说，可解释、可复现，比只看单元测试更可靠。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/e2e/test_cli_managed_live_agent_e2e.py` → `119 passed, 1 skipped`
  - Entry:
    - Real smoke 1（无参数真实入口，当前机器 8000 已占用，但可证明默认走 managed 启动支路）：`python -m coding_cli.main` → `{"error": "managed mode cannot start local API: port 8000 already in use on 127.0.0.1.", "layer": "runtime", "suggestion": "free the port, choose another local --base-url, or switch to --mode remote."}`
    - Real smoke 2（真实启动/退出与清理）：`python -m coding_cli.main --mode managed --base-url http://127.0.0.1:52324`，stdin=`/exit`，结果 `RETURN_CODE=0`、`STDOUT='nano> '`、`PORT_BUSY_AFTER=0`
  - Acceptance matrix:
    1. 无参数启动 managed：自动化 `tests/unit/test_cli_main.py::test_run_cli_without_mode_defaults_repl_to_managed_lifecycle`、`::test_run_cli_without_mode_defaults_command_path_to_managed_when_base_url_is_omitted`；手工 smoke 1/2
    2. remote + base-url 可用：自动化 `tests/unit/test_cli_main.py::test_run_cli_explicit_remote_mode_overrides_managed_default`、`::test_run_cli_remote_mode_requires_base_url_with_actionable_error` 与 `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_flow_supports_key_commands_in_both_modes`
    3. single-command JSON：自动化 `tests/integration/test_cli_http_flow_integration.py::test_cli_send_message_command_keeps_single_json_stdout_contract_with_async_capable_client`
    4. `/new` `/use` `/tools` `/compact` `/history`：自动化 `tests/unit/test_cli_main.py::test_run_cli_repl_supports_required_commands` 与 `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_flow_supports_key_commands_in_both_modes`
    5. slash 菜单上下选择/填充：自动化 `tests/unit/test_cli_main.py` 中命令菜单相关 scripted reader 用例
    6. 输入历史上下回溯/会话隔离：自动化 `tests/unit/test_cli_main.py` 中 history recall / per-session history 用例
    7. 实时事件流工具进度与文本增量：自动化 `tests/unit/test_cli_main.py::test_run_cli_repl_uses_async_events_with_run_filter_and_dedup` 与相关 event pipeline 回归
    8. 上下文预算与 `/compact` 刷新：自动化 `tests/unit/test_cli_main.py`、`tests/integration/test_cli_http_flow_integration.py::test_cli_repl_flow_supports_key_commands_in_both_modes`
    9. layer + suggestion 错误输出：自动化 `tests/integration/test_cli_http_flow_integration.py::test_cli_timeout_error_surfaces_root_cause_and_trace_id_evidence` 与 `tests/unit/test_cli_main.py::test_run_cli_remote_mode_requires_base_url_with_actionable_error`
    10. non-TTY 可用：自动化 `tests/unit/test_cli_main.py` 中 non-TTY / plain block 输出相关用例
  - M108 release gate absorption:
    - multiline paste：`tests/integration/test_cli_http_flow_integration.py::test_cli_repl_multiline_paste_submits_single_async_message`
    - `/exit` 清队：`tests/integration/test_cli_http_flow_integration.py::test_cli_repl_managed_exit_discards_queued_messages_and_stops_server` + `tests/unit/test_cli_main.py` 的 drain/remaining in-flight 回归
- Rollback: `92d8adf`（R2 C1 红灯测试）
- Commits: C1=`92d8adf`, C2=`767f437`, C3=`858885e`
- Next: rebase/merge main，更新 `data/dev-tasks.json`，再清理 worktree。
