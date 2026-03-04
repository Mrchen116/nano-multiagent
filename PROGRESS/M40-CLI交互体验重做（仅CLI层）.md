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
  - `af06611`（R1 红测提交）
- Commits: C1=`af06611`, C2=`43d4d1e`, C3=`<this-doc-commit>`
- Next:
  - R2：将 REPL 默认输出从 JSON/事件日志切换为结构化分区展示。

### R2 REPL 结构化渲染（状态/工具/回答/错误/用量）
- Context:
  -
- Decision:
  -
- Rationale:
  -
- Evidence:
  - Tests: `待补`
  - Entry: `待补`
- Rollback:
  -
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  -

### R3 CLI 层回归收口与边界固化
- Context:
  -
- Decision:
  -
- Rationale:
  -
- Evidence:
  - Tests: `待补`
  - Entry: `待补`
- Rollback:
  -
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  -
