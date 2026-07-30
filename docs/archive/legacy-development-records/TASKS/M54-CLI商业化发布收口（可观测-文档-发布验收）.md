# M54 - CLI商业化发布收口（可观测/文档/发布验收）

## Milestone Contract
- Milestone: `M54`
- Title: `CLI商业化发布收口（可观测+文档+发布验收）`
- Goal: 完成 CLI 商业化发布前收口：可观测、操作文档、发布验收流程与回滚策略。
- Execution Mode: `parallel`（按并行工作区续跑）
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M54`
- Branch: `milestone/M54`
- Test Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、CLI 相关测试、`README.md`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: 非 CLI 目录（`src/nano_multiagent/{core,server,agent,runs,tools,session,llm,hooks}/**`）
- Prevention Rules:
  - 仅改 CLI 与指定测试/文档，不改内核 API 与服务实现。
  - 不回退他人并行改动，冲突仅做最小合并。
  - 维持 HTTP-only 边界、`send-message` 单 JSON 契约与 managed/remote 兼容。

## Startup Checklist
- [x] 已阅读：`LOGBOOK.md`
- [x] 已阅读：`内核设计蓝图.md`（边界参考）
- [x] 已阅读：`COMMENTING_GUIDE.md`，承诺遵守注释规范
- [x] Baseline Gate：`119 passed, 46 warnings`（2026-03-04）

## Roadpoints

### R1 可观测收口：指标契约 + 故障归因助手
- Acceptance:
  - 在 CLI 层提供稳定的 perf 指标解释结构（含等级/原因/建议）。
  - 指标解释器可把 `perf_metrics` 转为排障摘要，不依赖 server/core 代码。
  - 高优先级故障（throughput/redraw/sample_size）具备可读建议映射。
  - 单元测试锁定指标解释契约。
- Tests Plan:
  - unit: 选；逻辑集中在 CLI 模块，纯函数可稳定验证。
  - contract: 不选；R2/R3 统一回归。
  - integration: 不选；R2/R3 覆盖链路。
  - e2e: 不选；R3 执行 managed。
- Expected Tests:
  - `tests/unit/test_cli_refactor_boundaries.py::test_cli_release_observability_maps_guardrail_reason_to_actionable_hints`
  - `tests/unit/test_cli_refactor_boundaries.py::test_cli_release_observability_builds_summary_lines_from_perf_metrics`
- DoD:
  - C1/C2/C3 完整；C2 前全量门禁全绿。
- Commits:
  - C1: `8835e99`
  - C2: `4638ce1`
  - C3: `b4a7e5f`
- Status: `DONE`

### R2 发布验收与回滚流程：可执行脚本化
- Acceptance:
  - 新增 CLI 发布验收脚本（dry-run + execute）可生成并执行发布检查步骤。
  - 脚本内置回滚流程模板，覆盖分支回退、配置回退、验收重试。
  - 产物可被 README 与排障手册直接引用。
  - 单元测试锁定脚本参数与输出结构。
- Tests Plan:
  - unit: 选；脚本拼装与执行分支可 mock 校验。
  - contract: 不选；脚本不改变 API 契约。
  - integration: 不选；R3 统一执行门禁与 managed 实跑。
  - e2e: 不选；R3 managed 验收。
- Expected Tests:
  - `tests/unit/test_cli_refactor_boundaries.py::test_cli_release_playbook_dry_run_outputs_acceptance_and_rollback_steps`
  - `tests/unit/test_cli_refactor_boundaries.py::test_cli_release_playbook_execute_runs_steps_and_collects_status`
- DoD:
  - C1/C2/C3 完整；C2 前全量门禁全绿。
- Commits:
  - C1: `f54e86a`
  - C2: `89c3598`、`0e9182c`、`947e092`
  - C3: `c815d57`
- Status: `DONE`

### R3 文档收口 + 发布验收 + 集成
- Acceptance:
  - `README.md` 覆盖新架构能力、可观测与发布验收入口。
  - 新增 CLI 故障排查/发布手册文档并与 README 互链。
  - 全量门禁 + managed 实跑通过并留证据。
  - 完成 rebase/merge/push 与 `dev_tasks M54=DONE`。
- Tests Plan:
  - unit: 选；执行全量门禁。
  - contract: 选；执行全量门禁。
  - integration: 选；执行全量门禁。
  - e2e: 选；managed CLI 实跑。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - `PYTHONPATH=src /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - main 合并并 push。
  - `dev_tasks` 中 `M54` 为 `DONE` 且 result 完整。
- Status: `DONE`

### Delivery Notes
- 门禁：`123 passed, 46 warnings`（含 R2 脚本与 R3 文档变更后复跑）。
- 发布验收脚本：
  - dry-run：输出 `acceptance_steps/rollback_steps/status=pending`。
  - execute：输出 `status=passed`，并执行 `cli_gate_tests + managed_smoke_ping`。
- managed 实跑：
  - `--base-url http://127.0.0.1:8131 health` -> healthy JSON。
  - `--base-url http://127.0.0.1:8131 create-session` -> active session JSON。
