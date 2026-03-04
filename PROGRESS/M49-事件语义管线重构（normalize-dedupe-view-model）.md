# M49 - 事件语义管线重构（normalize/dedupe/view-model）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `108 passed, 42 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - 现有 `cli/events/repl_events.py` 同时承担 normalize、去重、预览发射、摘要聚合，职责耦合高，后续并行改造风险大。
  - 约束：只改 CLI，不碰内核 API；必须保持队列能力、`run_id` 过滤、`send-message` 单 JSON 契约。
- Decision:
  - 拆分为 `R1 分层`、`R2 去重窗口稳态`、`R3 收口验收` 三个 Roadpoint，全部按 C1/C2/C3 执行。
  - 先以测试锁定行为，再做最小重构；不改对外 payload 结构。
- Rationale:
  - 将“行为回归风险”前置到红测可观测，避免架构重构引入隐性渲染偏差。
- Evidence:
  - Tests: 基线门禁全绿（`108 passed, 42 warnings`）。
  - Entry: 已确认主修改面在 `src/nano_multiagent/cli/events/repl_events.py`，调用入口在 `src/nano_multiagent/cli/app/commands.py`。
- Rollback:
  - 回退到本计划提交前的稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1：先补分层导向红测，再落地 normalize/dedupe/view-model 结构重构。

### R1 语义管线分层（normalize -> dedupe -> view-model）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 event_id + fallback 去重窗口稳态化
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 收口（全量门禁 + managed 实跑 + main 集成 + dev_tasks DONE）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
