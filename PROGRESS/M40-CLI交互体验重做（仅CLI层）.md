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
