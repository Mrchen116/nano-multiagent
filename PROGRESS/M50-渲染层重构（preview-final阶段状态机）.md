# M50 - 渲染层重构（preview/final阶段状态机）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `113 passed, 42 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - M49 已完成 normalize/dedupe/view-model 分层，但 preview 发射与 summary 过滤仍缺显式阶段机，存在“收口阶段重复发射/重复汇总”风险。
  - 边界约束：仅改 CLI，不能触碰内核 API 与 server/agent/session/tools 等目录。
- Decision:
  - 拆分 `R1 阶段状态机红测`、`R2 状态机落地与文案统一`、`R3 收口验收与集成`。
  - 统一按 `STREAMING -> FINALIZING -> FINALIZED` 管控 preview 与 summary 的职责边界。
- Rationale:
  - 先以红测明确阶段边界，再做最小实现，可降低异步事件链路回归风险。
- Evidence:
  - Tests: 基线门禁全绿（`113 passed, 42 warnings`）。
  - Entry: 主改造面锁定 `cli/events/repl_events.py` 与 `cli/events/event_pipeline.py`。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 红测并提交 C1。

### R1 渲染阶段状态机红测（STREAMING/FINALIZING/FINALIZED）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 状态机落地与文案统一（preview/final 分离）
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
