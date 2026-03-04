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
  - 当前异步事件链路缺少“性能门禁”可观测结构，无法稳定验证高频批次和长会话下的吞吐/重绘比例是否退化。
  - M53 要求把门禁变成可测试指标快照，且不改 `app/commands.py`。
- Decision:
  - 新增 3 条红测覆盖：高频批次指标、长会话多批次稳定性、`send_message_with_async_events` 暴露指标快照。
  - 在 `event_pipeline` 新增 `ReplPerfTracker`，在 `consume_async_run_events` 记录批次指标并随 `_repl_view.perf_metrics` 回传。
- Rationale:
  - 保持改动集中在 `cli/events`，用最小接线实现“门禁可观测 + 阈值可判定”，避免并行冲突。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "high_frequency_batch_records_perf_baseline or long_session_batches_keep_perf_guardrails_stable or exposes_perf_metrics_snapshot"` -> `3 failed`。
    - 子集绿测：同命令 -> `3 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `115 passed, 44 warnings`。
  - Entry:
    - `_repl_view.perf_metrics` 现已包含 `sample_ready/throughput_ok/redraw_ratio_ok/stable` 与批次计数。
- Rollback:
  - 回退到 `cd73353`（R1 红测提交）可重做实现。
- Commits: C1=`cd73353`, C2=`cf8242a`, C3=`TBD`
- Next:
  - 执行 R2：补充阈值不达标场景判定与原因字段，强化门禁可解释性。

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
