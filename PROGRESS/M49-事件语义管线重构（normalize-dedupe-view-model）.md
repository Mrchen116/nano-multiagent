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
  - 分层后仍存在“去重窗口与 legacy set 双轨判重”问题：即便窗口淘汰了旧语义键，legacy set 仍会永久拦截，导致窗口失效。
  - 该问题会让长会话 fallback 去重退化为无界行为。
- Decision:
  - 新增红测验证“窗口容量淘汰后旧语义键可重新消费”。
  - `consume_event_for_run` 改为仅使用 `EventDedupeWindow` 进行判重；`seen_event_ids/seen_event_fingerprints` 仅做兼容镜像，不再参与准入判断。
  - `send_message_with_async_events` 默认不再维护 legacy 去重集合，避免无界增长。
- Rationale:
  - 将判重真源收敛到有界窗口，才能同时满足“缺失 event_id 去重稳定”与“窗口内存可控”。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "fallback_dedupe_window_evicts_old_semantic_keys"` -> `1 failed`（消费计数 `[1,1,1,0]`）。
    - 绿测（子集）：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "fallback_dedupe_window_evicts_old_semantic_keys or event_pipeline_layer_exposes_normalize_dedupe_and_view_model"` -> `2 passed`。
    - 回归子集：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "dedupes_replayed_tool_start_without_event_id or dedupes_replayed_tool_start_with_changed_event_id or dedupes_replayed_tool_start_with_changed_event_id_and_nonsemantic_metadata or uses_async_events_with_run_filter_and_dedup"` -> `4 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `110 passed, 42 warnings`。
  - Entry:
    - fallback 去重在缺失/漂移 `event_id` 场景保持稳定，且窗口淘汰语义生效。
- Rollback:
  - `1a346c3`（R2 红测提交）。
- Commits: C1=`1a346c3`, C2=`f92212a`, C3=`本提交`
- Next:
  - 进入 R3：执行 managed CLI 实跑留证、更新文档收口并完成 main 集成与 dev_tasks DONE。

### R3 收口（全量门禁 + managed 实跑 + main 集成 + dev_tasks DONE）
- Context:
  - 需要在真实 managed CLI 场景确认事件语义管线重构无行为回归，并给出“前后对比”证据用于发布验收。
- Decision:
  - 执行两次 managed CLI 脚本化验收：基础问答链路与工具事件链路（`bash echo`）。
  - 以 R2 红/绿测试结果作为“窗口策略前后对比”，并结合 managed 实跑观察关键线次数。
- Rationale:
  - 单测可证明逻辑正确，managed 实跑可验证真实入口链路（server lifecycle + REPL queue + event render）可用。
- Evidence:
  - Tests:
    - 全量门禁（最终）：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `110 passed, 42 warnings`。
    - 前后对比（窗口策略）：
      - Before（R2 红测）：`consumed_counts == [1,1,1,0]`（旧语义键被 legacy set 永久拦截）。
      - After（R2 绿测）：`consumed_counts == [1,1,1,1]`（窗口淘汰后旧键可重新消费）。
  - Entry:
    - managed 验收 1（`/new -> ping -> /exit`）：
      - `Assistant: pong`
      - `State: completed | stop=stop | run=run_84a4c52ab7d4bfb1 | session=sess_e5dd2183c61656a3`
    - managed 验收 2（`/new -> 请使用bash工具执行: echo M49_TOOL -> /exit`）：
      - `Tool: bash start ...`、`Tool: bash started ...`、`Tool: bash exit ...` 各 1 次
      - `Assistant: M49_TOOL`
      - `State: completed | stop=stop | run=run_f12150dba07373a5 | session=sess_c11327c0c8761693`
- Rollback:
  - `db5c31a`（R2 文档收口提交）。
- Commits: C1=`N/A`, C2=`N/A`, C3=`本提交`
- Next:
  - 执行 `rebase origin/main`、`merge --no-ff`、`push origin main`，并用 `dev_tasks.py` 更新 `M49=DONE`。
