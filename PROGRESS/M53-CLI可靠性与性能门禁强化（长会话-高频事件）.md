# M53 - CLI可靠性与性能门禁强化（长会话/高频事件）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `112 passed, 44 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - 当前 CLI 事件链路已具备阶段机与去重窗口，但缺少“长会话 + 高频事件”性能护栏的可观测指标与阈值门禁。
  - 并行约束要求优先在 `events/render` 内闭环，避免改动 `app/commands.py`。
- Decision:
  - 拆分 `R1 红测回归集`、`R2 指标/阈值落地`、`R3 收口集成`。
  - 以 `events` 层为主引入性能追踪器，输出到 `_repl_view`，维持既有 REPL 文案与契约兼容。
- Rationale:
  - 先测后改可避免性能门禁改造引入行为回归，并减少与并行里程碑冲突面。
- Evidence:
  - Tests: 基线门禁全绿（`112 passed, 44 warnings`）。
  - Entry: 改造面锁定 `src/nano_multiagent/cli/events/**` 与 `src/nano_multiagent/cli/render/**`。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1：新增高频/长会话性能门禁红测并提交 C1。

### R1 长会话/高频事件回归红测集
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 性能护栏落地（指标观测 + 阈值判定 + 重绘基线）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 收口（门禁 + managed + main + dev_tasks DONE）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
