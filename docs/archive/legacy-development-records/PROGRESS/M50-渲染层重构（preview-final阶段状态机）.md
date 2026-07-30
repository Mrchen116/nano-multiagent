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
- Commits: C1=`ed6435c`, C2=`396ae12`, C3=`e2a9cca`
- Next:
  - 执行 R2：把 preview/final 去重过滤职责进一步收口到阶段机，减少散落状态与双写路径。

### R2 状态机落地与文案统一（preview/final 分离）
- Context:
  - R1 接入基础阶段机后，preview 幂等与 summary 过滤仍分散在 `repl_events` 的外部集合，状态真源不集中。
- Decision:
  - 为阶段机新增 `should_emit_tool_preview/record_tool_preview/filter_summary_tool_updates`，将 preview 发射幂等和 final 摘要过滤收口到同一对象。
  - `send_message_with_async_events` 改为由阶段机统一过滤 `tool_updates`，减少外部散落状态。
  - 终态 `run_status` 的阶段切换在批次末尾生效，避免同批次事件顺序抖动导致合法 preview 被误吞。
- Rationale:
  - 状态集中后可明确“STREAMING 只负责 preview；FINALIZING/FINALIZED 只负责 summary 过滤”，降低双写复读与维护复杂度。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "filters_previewed_tool_lines_from_final_summary"` -> `1 failed`（阶段机缺少预期 API）。
    - 绿测子集：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "render_phase_machine_ or dedupes_replayed_tool_start_with_changed_event_id_and_nonsemantic_metadata or streams_started_running_chunk_and_exit_for_tool_execution"` -> `4 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `116 passed, 42 warnings`。
  - Entry:
    - preview/final 去重已由 `ReplRenderPhaseMachine` 统一控制；CLI 输出仍保持 `Assistant/State/Progress/Tool/Usage` 风格。
- Rollback:
  - 回退到 `7dca46b`（R2 红测提交）。
- Commits: C1=`7dca46b`, C2=`3c14eda`, C3=`0f7640d`
- Next:
  - 执行 R3：managed 实跑、rebase/merge/push、dev_tasks DONE 回填。

### R3 收口（门禁 + managed + main + dev_tasks DONE）
- Context:
  - R1/R2 完成后需要最终收口，验证渲染阶段机在真实 managed 入口下无双写复读，并完成 main 集成与任务面板回填。
- Decision:
  - 复跑全量门禁，执行两组 managed 实跑（`ping` 与 `bash echo`）。
  - 记录关键输出计数（start/started/exit/progress 各 1）作为 preview/final 分离验收依据。
- Rationale:
  - 单测可验证逻辑边界，managed 入口验证可证明实际交互观感稳定且无重复关键线。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `116 passed, 42 warnings`。
  - Entry:
    - managed `ping` 片段：`Assistant: pong`、`State: completed | stop=stop | run=...`。
    - managed 工具片段：
      - `Tool: bash start args={"command": "echo M50_TOOL", ...}`
      - `Tool: bash started status=started elapsed=0ms`
      - `Tool: bash exit code=0 status=completed duration=...`
      - `Tool: bash progress chunks=2 (stdout=1, stderr=1)`
      - `Assistant: M50_TOOL`
    - 计数：`start args=1, started=1, exit=1, progress=1`。
- Rollback:
  - 回退到 `0f7640d`（R2 文档收口提交）。
- Commits: C1=`N/A`, C2=`N/A`, C3=`本提交`
- Next:
  - 执行 `rebase origin/main`、合并 `main` 并 push，然后更新 `data/dev-tasks.json` 的 `M50=DONE`。
