# M43 - CLI发布级界面收口（低噪声+可读状态线+命令交互收敛）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `98 passed, 40 warnings`

## Constraints / Notes
- 仅改 CLI 层与相关测试，禁止触碰内核与 server/runtime/tool/hook/agent/core 模块。
- `send-message` stdout 单 JSON 契约必须保持。
- REPL 异步消费必须保留 `event_id` 去重与 `run_id` 过滤。
- 目标是“发布级默认阅读体验”：答案优先、低噪声状态线、工具过程可读且不过载。

### R1 默认 REPL 输出降噪（状态线+工具摘要发布化）
- Context:
  - M42 仍保留 `[status]/[progress]/[tool]/[usage]` 标签式摘要和 `[tool xxx]` 事件预览，默认观感接近调试日志。
  - M43 目标是在不改内核协议前提下，把默认 REPL 改为发布态可读状态线，且保持异步 run 过滤/去重行为。
- Decision:
  - `repl_render` 输出改为 `State/Progress/Tool/Usage` 文案行，移除默认裸标签前缀。
  - `repl_events` 事件预览改为 `Tool <name> ...` / `Run <id>: ...` 文案，保留原始事件语义和字段信息。
  - `_normalize_tool_update` 兼容 `Tool ...` 与旧 `[tool ...]` 格式，避免聚合路径回归。
- Rationale:
  - 仅改 CLI 渲染层即可达成“低噪声+可读状态线”，不会影响 HTTP 契约、run_id 过滤与 event_id 去重核心行为。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_run_cli_repl_prints_turn_llm_usage_when_available tests/unit/test_cli_main.py::test_run_cli_repl_prints_compact_answer_first_summary_for_async_flow tests/unit/test_cli_main.py::test_run_cli_repl_prints_compact_error_summary_for_failed_run tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_async_run_tool_and_text_events tests/integration/test_cli_http_flow_integration.py::test_cli_repl_prints_compact_sections_in_async_turn_output tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_started_running_chunk_and_exit_for_bash_tool`（6 failed）
    - 绿测（全量门禁）：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（98 passed, 40 warnings）
  - Entry:
    - 成功流：`Assistant -> State -> Tool -> Usage`，不再出现 `[status]/[tool]/[usage]` 裸日志。
    - 失败流：`Assistant: (empty)` + `State: failed | layer=...` + `Error:` + `Hint:` + `Usage: unavailable`。
- Rollback:
  - `ca4ec09`（R1 红测提交）
- Commits: C1=ca4ec09, C2=189acff, C3=本提交（docs R1.1）
- Next:
  - 进入 R2：收敛 `/` 命令菜单交互，消除菜单刷屏和输入行污染。

### R2 `/` 命令提示交互收敛（不刷屏、不污染输入行）
- Context:
  - `/` 命令候选当前通过多行 `Commands ↓ ...` 面板实时重绘，终端里容易刷屏并污染输入区。
  - 事件摘要仍有高频碎片（queued/chunk）和原始结构痕迹，需要对齐“event -> semantic -> render”三层并降低噪声。
- Decision:
  - `repl_input` 将斜杠菜单改为输入行内提示（保留 ↑/↓ + Enter 选择），移除多行菜单输出。
  - `repl_events` 引入最小语义化渲染：raw event 映射到自然状态/工具文案，不直接暴露原始事件名。
  - 默认静默低价值高频事件（如 queued/running 常规状态、chunk 明细）；保留关键阶段（tool start/started/exit、error、retry progress）。
  - 工具输出预览改为 head+ellipsis+tail 截断；多工具按 `call_id/name` 分组后聚合摘要，避免同名工具互相覆盖。
- Rationale:
  - 只在 CLI 文本渲染层做最小等价实现即可落地交互体验目标，同时保留异步队列、run_id/event_id 契约。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_repl_input_engine_slash_menu_does_not_render_multiline_panel tests/integration/test_cli_http_flow_integration.py::test_cli_repl_slash_menu_selects_command_and_executes_it`（1 failed）
    - 绿测（全量门禁）：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（101 passed, 40 warnings）
  - Entry:
    - `/` 交互不再出现 `Commands ↓ ...` 多行刷屏，补全仍可用。
    - 工具摘要默认不再输出 chunk 碎片，展示 `Tool ... start/exit` 关键阶段。
    - 长工具输出显示 `head...tail`，可读且不刷屏。
- Rollback:
  - `8dbe722`（R2 红测提交）
- Commits: C1=8dbe722, C2=6390566, C3=本提交（docs R2.1）
- Next:
  - 进入 R3：真实 managed CLI 验收、rebase/main 集成、push 与 dev-tasks DONE 更新。

### R3 收口与验收（真实 managed 交互 + 集成）
- Context:
  - R1/R2 已完成且门禁全绿，但里程碑缺少最终收口记录（managed 真实交互验收 + 主干集成证据）。
  - 验收阶段出现环境差异：TTY 默认 `python3` 指向系统 3.9，缺少 `httpx`；改为与测试一致的 `/Users/czj/miniforge3/bin/python3` 后可正常验收。
- Decision:
  - 保持 R1/R2 代码不再新增改动，仅执行 R3 验收与集成：复跑全量门禁、执行 managed 模式真实终端交互抽检、随后集成到 main。
  - managed 抽检重点验证：默认输出是语义状态线（`State/Tool/Usage`）且 `/` 命令提示已改为行内提示，不再出现多行 `Commands ↓` 刷屏。
- Rationale:
  - R3 目标是“可发布验收”，不是追加功能；冻结实现可降低回归风险并保证里程碑快速收口。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（`101 passed, 40 warnings`）
  - Entry:
    - managed 抽检命令：`PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
    - 关键观测：
      - `/` 输入时显示行内提示 `(/help)`，不再渲染多行菜单；
      - 单轮结果为 `Assistant + State + Tool + Usage` 语义摘要，不再输出 `[status]/[tool]/[usage]` 裸标签；
      - 运行中输入排队提示 `Queued message #1 ...` 仍可用。
- Rollback:
  - `9e4de5f`（R2 文档完成点，可回退并重新执行 R3 集成）
- Commits: C1=N/A, C2=N/A（R3无实现代码提交）, C3=本提交（docs R3.1）
- Next:
  - rebase `origin/main`、合并 `milestone/M43` 到 `main`、push `origin/main`，并将 `data/dev-tasks.json` 的 M43 标记为 `DONE`。
