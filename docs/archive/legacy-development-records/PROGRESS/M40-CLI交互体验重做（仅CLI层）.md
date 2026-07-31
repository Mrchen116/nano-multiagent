# M40 - CLI交互体验重做（仅CLI层）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `86 passed, 34 warnings`

## Notes from LOGBOOK / M39 handoff
- 保留 `send-message` 单 JSON stdout 契约，REPL 事件噪声不得污染单命令模式。
- REPL 异步事件要继续保持 `event_id` 去重 + `run_id` 过滤，避免串线。
- 先实现“运行中输入排队”最小闭环，再增强渲染，降低回归风险。
- 已确认 M40 退出标准（当前范围）可 CLI-only 完成；仅审批/多线程/细粒度执行流属于未来内核候选。

### R1 运行中输入排队与顺序执行
- Context:
  - 旧 REPL 在一条消息发送期间会阻塞输入，无法在 run 进行中继续输入下一条需求。
  - 必须保持 CLI-only 边界，不引入内核接口改动；且不能破坏非交互 `send-message` JSON 契约。
- Decision:
  - 新增 `cli/repl_runtime.py`，提供后台队列 worker（`ReplRunQueue`）顺序处理发送任务。
  - `commands._run_repl` 在“支持 async 事件”的客户端模式下启用队列：主线程继续读输入，后台线程串行发送。
  - 若 backlog>0 且收到普通文本，立即输出 `Queued message #N ...`；`/exit` 与 EOF 前执行 drain。
  - 为避免 `/history` 等命令读取半状态，在存在 in-flight/backlog 时先 `wait_for_drain()` 再执行命令。
- Rationale:
  - 该设计只改 CLI 层即可实现“运行中可输入并排队”，并通过单线程 worker 保证发送顺序与会话一致性。
  - 将改动限定在 async REPL 路径，可降低对既有同步 REPL 与单命令模式的回归风险。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_run_cli_repl_queues_user_input_while_previous_async_run_is_in_progress`
    - 红测：`PYTHONPATH=src pytest -q tests/integration/test_cli_http_flow_integration.py::test_cli_repl_allows_queueing_next_input_while_previous_async_run_is_running`
    - 全绿：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - Entry:
    - REPL 在首条 run 未完成时可接受第二条输入并输出 `Queued message #1`。
    - 队列最终按 FIFO 顺序完成两条 `send_message_async` 调用。
- Rollback:
  - `81ad406`（R1 红测提交）
- Commits: C1=`81ad406`, C2=`5fcc73c`, C3=`0611562`
- Next:
  - R2：将 REPL 默认输出从 JSON/事件日志切换为结构化分区展示。

### R2 REPL 结构化渲染（状态/工具/回答/错误/用量）
- Context:
  - R1 完成后，REPL 仍保留“原始事件预览 + 旧错误文案”断言，导致门禁出现 10 条失败（旧断言与新交互目标冲突）。
  - 目标是默认输出结构化分区（Status/Tools/Answer/Error/Usage），且不破坏 `send-message` 的单 JSON 契约与 HTTP-only 边界。
- Decision:
  - 新增 `cli/repl_render.py`，统一渲染成功/失败轮次分区（状态、工具、回答、错误、用量、context budget）。
  - `commands._run_repl` 改为只调用 `print_repl_turn_summary/error`，移除直接打印 turn payload JSON 与 `print_actionable_error` 的旧路径。
  - `repl_events.send_message_with_async_events` 关闭逐事件实时预览（`emit_preview=False`），改为聚合 `run_status/tool_*` 事件并注入 `_repl_view` 给渲染器。
  - 将既有 unit/integration 断言迁移为结构化输出口径（仍校验 run_id/工具更新/错误根因/排队顺序等行为）。
- Rationale:
  - 渲染职责集中后，CLI 交互体验可统一演进，避免在 `commands.py` 内散落多套文本格式。
  - 保留异步事件去重与 run_id 过滤逻辑，仅调整展示层，可在不改内核前提下达成 M40 UI 目标。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（10 failed，定位旧断言与新渲染冲突）
    - 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（91 passed, 38 warnings）
  - Entry:
    - REPL 每轮默认输出 `Status/Tools/Answer/Usage` 分区；失败路径输出 `Error` 分区并携带 `layer/suggestion`。
    - 异步流程不再打印 `[text] ...` 逐字调试流，工具与状态进度改为结构化聚合行。
- Rollback:
  - `33ea52c`（R2 红测提交）
- Commits: C1=`33ea52c`, C2=`a679206`, C3=`e2d25d1`
- Next:
  - R3：补齐同步路径完成态边界回归，并完成 Milestone 收口文档。

### R3 CLI 层回归收口与边界固化
- Context:
  - R2 后发现同步 `send_message` payload 若仅有 `stop_reason`（无 `status/completed`）会展示 `state=unknown`，不利于结构化状态语义一致性。
  - 需要在不改协议字段的前提下，固化“同步 stop_reason 视作完成态”的 CLI 呈现规则。
- Decision:
  - 新增红测 `test_run_cli_repl_infers_completed_state_when_sync_payload_has_stop_reason` 锁定该缺口。
  - 在 `repl_render._resolve_state` 中新增 stop_reason 推断：存在非空 `stop_reason` 时将状态映射为 `completed`。
  - 全量复跑 unit/integration/contract 门禁作为 Milestone 收口。
- Rationale:
  - 该修复只影响 CLI 展示层，不改 HTTP 接口与内核行为，风险低且直接提升用户读屏一致性。
  - 用红测先锁定缺口，可防后续重构回退到 `state=unknown`。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_run_cli_repl_infers_completed_state_when_sync_payload_has_stop_reason`（1 failed）
    - 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（92 passed, 38 warnings）
  - Entry:
    - 同步路径在仅返回 `stop_reason` 时，`Status` 分区显示 `state=completed`。
    - 非交互命令 `send-message` 仍保持 stdout 单 JSON 契约（相关 contract/integration 全绿）。
- Rollback:
  - `c8ff0dc`（R3 红测提交）
- Commits: C1=`c8ff0dc`, C2=`499bf59`, C3=`e2d25d1`
- Next:
  - Milestone DONE：执行 rebase/main 集成与 `dev-tasks.json` DONE 回填。
