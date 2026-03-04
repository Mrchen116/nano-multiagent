# M46 - CLI工具流去重与文案一致性收口（实跑观感修复）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - Pending (M46 execution)

## Notes
- 仅修改 CLI 层与相关测试；不触碰内核模块。
- 重点修复真实 managed 交互中的三类体验问题：重复、风格不一致、摘要复读。

### R1 预置
- Context: M45 后实跑仍观察到工具 `start/exit` 重复和 `Tool`/`Tool:` 混用。
- Decision: 先补红测锁定“无 event_id 回放去重 + 队列模式摘要去重 + 文案一致性”。
- Rationale: 防止修复只在本地实跑有效、缺少回归护栏。
- Evidence:
  - Tests: Pending
  - Entry: Pending
- Rollback: `58a422b`
- Commits: C1=<TBD>, C2=<TBD>, C3=<TBD>
- Next: 执行 R1 红测并提交 C1。
