# M63 - REPL命令屏障与在途消息排空一致性

## Milestone Contract
- milestone_id: `M63`
- title: `REPL命令屏障与在途消息排空一致性`
- goal: 修复 `/history` 与 `/exit` 在 in-flight 消息场景下的误报超时与收口一致性。
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M63`
- branch: `milestone/M63`
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
  - `src/nano_multiagent/events/**`（深层逻辑不改）
  - `src/nano_multiagent/render/**`（深层逻辑不改）
- prevention_rules:
  - 仅修改 CLI 入口编排与队列等待相关模块，不触碰内核/API。
  - `send-message` 单 JSON stdout 契约不可破坏。
  - TTY/non-TTY 输出分流规则保持不变，仅增强 REPL 队列屏障信息与一致性。
  - 忽略并行里程碑变更，不回退非本里程碑内容。

## Startup Checklist
- [x] 已阅读 `LOGBOOK.md`
- [x] 已阅读 `COMMENTING_GUIDE.md` 并承诺遵守
- [x] 已阅读 `内核设计蓝图.md`（用于边界约束）
- [x] 已确认 worktree/branch：`M63` / `milestone/M63`
- [x] 已跑 baseline：`112 passed, 44 warnings`

## Roadpoints

### R1 /history 与 /exit 的 in-flight 屏障一致性修复
- Acceptance:
  - `/history` 在在途消息已完成后，不因等待路径误判而出现假阳性 timeout。
  - `/exit` 在 timeout 场景明确打印剩余在途消息数量，并优先等待排空。
  - 命令屏障等待提示格式统一（等待中/超时均可读且一致）。
  - `send-message` 单 JSON 契约不被 REPL 队列状态文案污染。
  - 增加 unit + integration 回归并通过全量门禁。
- Tests Plan:
  - unit: 选择。覆盖 `commands.py` 在 false-timeout 竞态与 `/exit` 超时剩余信息场景。
  - contract: 选择。复核 `send-message` JSON 契约不被队列状态文本影响（回归不破坏）。
  - integration: 选择。覆盖真实 REPL 输入链路下 `/history` 屏障误判场景。
  - e2e: 不选。已有 managed 实跑作为入口补充证据，避免引入新 e2e 桩复杂度。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_history_command_ignores_false_timeout_when_queue_already_drained`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_exit_reports_remaining_inflight_messages_after_timeout`
  - `tests/integration/test_cli_http_flow_integration.py::test_cli_repl_history_wait_barrier_ignores_false_timeout_after_drain`
  - 门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- DoD:
  - C1/C2/C3 三提交完整。
  - `test_command` 全绿。
  - `PROGRESS` 记录 Context/Decision/Evidence/Rollback/Commits。
  - managed CLI 实跑补充前后对比片段。
- Status: `DONE`

### Delivery Notes
- C1 红测：新增 3 条回归并稳定复现（`3 failed`）。
- C2 绿化：`commands.py` 统一 in-flight 屏障等待逻辑，`repl_runtime.py` 修复 drain deadline 边界竞态，新增回归全部通过。
- 全量门禁：`115 passed, 46 warnings`。
