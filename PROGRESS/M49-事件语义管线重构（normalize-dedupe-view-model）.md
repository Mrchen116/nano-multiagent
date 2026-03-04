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
  - `repl_events.py` 既做 normalize/dedupe，又做摘要视图聚合，职责耦合导致后续 M50/M51 难以并行演进。
  - 需要在不改 CLI 外部契约前提下落地可复用的语义管线层。
- Decision:
  - 新增 `src/nano_multiagent/cli/events/event_pipeline.py`，提供 `NormalizedSessionEvent`、`EventDedupeWindow`、`consume_event_for_run`、`build_repl_view_model`。
  - `repl_events.consume_async_run_events` 改为委托管线层处理 normalize+dedupe；`_build_repl_view` 改为委托 view-model 构建。
  - `events/__init__.py` 显式导出 `event_pipeline`，保留旧入口兼容。
- Rationale:
  - 通过“调用方不变、职责下沉”的方式重构，能在不改变 `run_cli`/REPL 输出结构下完成架构解耦。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "event_pipeline_layer_exposes_normalize_dedupe_and_view_model"` -> `1 failed`（`ImportError: cannot import name 'event_pipeline'`）。
    - 绿测（子集）：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "event_pipeline_layer_exposes_normalize_dedupe_and_view_model or uses_async_events_with_run_filter_and_dedup or streams_started_running_chunk_and_exit_for_tool_execution or dedupes_replayed_tool_start_without_event_id"` -> `4 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `109 passed, 42 warnings`。
  - Entry:
    - `send-message` 与 REPL 输出契约保持不变，异步事件摘要仍输出 `status_updates/tool_updates`。
- Rollback:
  - `5bbb835`（R1 红测提交）。
- Commits: C1=`5bbb835`, C2=`b285862`, C3=`本提交`
- Next:
  - 进入 R2：补“fallback 去重窗口有界 + 非语义字段漂移去重稳定”红测并实现。

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
