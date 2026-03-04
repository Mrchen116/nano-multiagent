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
  - M49 的事件链路虽然有去重窗口，但 preview/final 没有显式阶段约束，收口时机只靠散落条件，存在复读风险。
- Decision:
  - 新增 `ReplRenderPhaseMachine` 与 `ReplRenderPhase(STREAMING/FINALIZING/FINALIZED)`。
  - `consume_async_run_events` 接收阶段机并在终态 `run_status` 后切到 `FINALIZING`，后续批次禁止继续 live preview。
- Rationale:
  - 先把阶段机能力测试化并接入消费主路径，确保后续 summary 过滤收口有统一状态真源。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "render_phase_machine_transitions_and_guards or stops_preview_after_finalizing"` -> `2 failed`（缺少阶段机导出）。
    - 绿测：同命令 -> `2 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `115 passed, 42 warnings`。
  - Entry:
    - 阶段机已接入 `send_message_with_async_events` 与 `consume_async_run_events`，终态后预览发射由 `can_emit_preview()` 闸门统一控制。
- Rollback:
  - 回退到 `ed6435c`（R1 红测提交）。
- Commits: C1=`ed6435c`, C2=`396ae12`, C3=`本提交`
- Next:
  - 执行 R2：把 preview/final 去重过滤职责进一步收口到阶段机，减少散落状态与双写路径。

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
