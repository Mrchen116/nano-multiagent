# M51 - 工具时间线聚合与异常隔离（call_id/orphan）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `106 passed, 42 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - M49 完成了 normalize/dedupe/view-model 分层，M50 完成 preview/final 阶段机；但工具摘要仍偏“字段覆盖模型”，orphan 终态隔离不显式，存在跨调用串味风险。
  - 边界：只改 CLI 与指定测试文件，不改内核/API/agent/server/session/llm/tools。
- Decision:
  - 拆分 `R1 call_id聚合+orphan隔离`、`R2 高频可读性+异常指标`、`R3 收口验收+main集成+dev_tasks`。
  - 以 `event_pipeline` 为主改造点，保持 `repl_events` 与 `repl_render` 契约稳定。
- Rationale:
  - 先锁语义（R1），再锁可读性（R2），最后统一门禁与实跑（R3），能最小化异步链路回归面。
- Evidence:
  - Tests: 基线门禁全绿（`106 passed, 42 warnings`）。
  - Entry: 计划文档已创建于 `TASKS/M51-工具时间线聚合与异常隔离（call_id-orphan）.md`。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: Plan=`8e1d155`; C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 红测并提交 C1。

### R1 call_id 时间线聚合与 orphan 隔离（核心语义）
- Context:
  - 现有工具摘要聚合按 group_key 覆盖字段，`tool_exec_exit` 缺少 start 匹配时会静默并入普通组，无法显式识别 orphan。
  - 需求要求“orphan 终态独立呈现 + 指标可见”，避免跨调用串味。
- Decision:
  - 在 `build_repl_view_model` 内新增 orphan 终态判定：`tool_end/tool_exec_exit` 若槽位无 `start/exec_started` 即标记 orphan。
  - orphan 工具线增加 `orphan ` 前缀，并在 `status_updates` 追加 `orphan_events=<count>`。
  - 新增 REPL 回归测试，验证 active call 与 orphan exit 并存时输出隔离。
- Rationale:
  - 保持改动集中在 CLI 聚合层，不触碰内核与 server；同时让异常链路在人类可读输出中可直接识别。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "orphan_exec_exit_from_active_call_timeline or renders_orphan_tool_exit_as_isolated_timeline"` -> `2 failed`。
    - 子集绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "orphan_exec_exit_from_active_call_timeline or renders_orphan_tool_exit_as_isolated_timeline or groups_same_tool_name_events_by_call_id"` -> `3 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `108 passed, 42 warnings`。
  - Entry:
    - REPL 摘要可输出 `Tool: orphan ...` 与 `Progress: orphan_events=1`。
- Rollback:
  - 回退到 `c0f7d1f`（R1 红测提交）可重做实现。
- Commits: C1=`c0f7d1f`, C2=`753e8a8`, C3=`TBD`
- Next:
  - 执行 R2：补高频可读性与 call_id 稳定呈现红测与实现。

### R2 高频事件可读性与异常指标收口
- Context:
  - `repl_render._compact_tool_updates` 以文本去重会把“不同 call_id 但同文案”折叠成一条，弱化时间线可读性。
  - 需要在保持现有输出风格的前提下，让跨调用同文案仍可区分。
- Decision:
  - 工具类 preview/summary 行统一追加 ` [call_id=...]` 后缀（仅 `call_id` 存在时）。
  - 保留现有文本前缀，避免破坏既有断言与阅读流；同步更新阶段机相关断言。
- Rationale:
  - 在不改渲染总线结构的情况下，最小改动即可让文本去重键天然包含调用身份，防止跨调用串味。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "keeps_same_tool_output_lines_for_distinct_call_id"` -> `1 failed`（仅输出 1 条）。
    - 子集绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "keeps_same_tool_output_lines_for_distinct_call_id or renders_orphan_tool_exit_as_isolated_timeline or groups_same_tool_name_events_by_call_id or streams_started_running_chunk_and_exit_for_tool_execution"` -> `4 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `109 passed, 42 warnings`。
  - Entry:
    - REPL 输出可见 `Tool: ... [call_id=...]`，同名同输出不同调用不再被折叠。
- Rollback:
  - 回退到 `426dc1d`（R2 红测提交）。
- Commits: C1=`426dc1d`, C2=`4d3c8cc`, C3=`TBD`
- Next:
  - 执行 R3：managed 实跑、main 集成、dev_tasks DONE 回填。

### R3 收口验收与集成
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`N/A`, C2=`N/A`, C3=`TBD`
- Next:
