# M110 Coding CLI 完整态收口

## Baseline
- Gate: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/e2e/test_cli_managed_live_agent_e2e.py`
- Result: 113 passed, 1 skipped, 50 warnings
- Notes:
  - 当前门禁已绿，M110 重点是把 default UX / 验收覆盖 / smoke evidence 收到 SPEC 完整态。
  - `LOGBOOK.md` 中与本 milestone 直接相关的规则：REPL 事件必须保持 `event_id` 去重 + `run_id` 过滤；single-command stdout 只能输出最终 JSON；`/exit` 只能截断未开始的 queued tail，不能吞掉 active candidate。
  - `COMMENTING_GUIDE.md` 已确认遵守：public API/入口写契约型 docstring，注释只解释意图/边界/代价。

## Plan Commit
- `f04f9c6` `docs(M110): 建立执行计划`

### R1 默认启动路径切换到 Managed
- Context: SPEC 要求无参数即进入 Managed，但现状是隐式 remote；同时大量既有 CLI 测试把“提供 --base-url 但未写 --mode”的路径当作 remote 调试入口使用，不能为了修默认 UX 直接改写全部含 `--base-url` 的隐式语义。
- Decision: 仅在“未显式给 `--mode`、未给 CLI `--base-url`、也没有 `NANO_MULTIAGENT_API_BASE_URL`”时，把默认 mode 解析为 managed；其它隐式带 URL 的路径继续落到 remote，显式 `--mode remote` 仍最高优先。
- Rationale: 这样既满足 SPEC 的无参数 front-door，又不破坏现有 `--base-url` 调试/远端调用面和 single-command JSON 合约。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/e2e/test_cli_managed_live_agent_e2e.py` → `117 passed, 1 skipped`
  - Entry: 新增 unit 覆盖无参数 REPL / 无参数单命令默认 managed，以及“带 `--base-url` 但未指定 mode 时仍走 remote”。
- Rollback: `a5b4279`（R1 C1 红灯测试）
- Commits: C1=`a5b4279`, C2=`9484fce`, C3=<pending>
- Next: R2 补 live/default 验收覆盖，并记录真实 CLI smoke 证据与 §10 对应关系。

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
