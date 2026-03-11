# M110 Coding CLI 完整态收口

## Baseline
- Gate: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/e2e/test_cli_managed_live_agent_e2e.py`
- Result: 113 passed, 1 skipped, 50 warnings
- Notes:
  - 当前门禁已绿，M110 重点是把 default UX / 验收覆盖 / smoke evidence 收到 SPEC 完整态。
  - `LOGBOOK.md` 中与本 milestone 直接相关的规则：REPL 事件必须保持 `event_id` 去重 + `run_id` 过滤；single-command stdout 只能输出最终 JSON；`/exit` 只能截断未开始的 queued tail，不能吞掉 active candidate。
  - `COMMENTING_GUIDE.md` 已确认遵守：public API/入口写契约型 docstring，注释只解释意图/边界/代价。

## Plan Commit
- Pending

### R1 默认启动路径切换到 Managed
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:

### R2 验收口径补齐与真实 smoke 证据固化
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
