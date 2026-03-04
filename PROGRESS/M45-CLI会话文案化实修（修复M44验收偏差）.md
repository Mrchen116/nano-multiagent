# M45 - CLI会话文案化实修（修复M44验收偏差）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `101 passed, 40 warnings`（2026-03-04）

### R1 会话文案化实修（自动建会话 + /new /use /session）
- Context:
  - 验收反馈显示真实 CLI 仍存在会话 JSON 直出，需在 REPL 路径彻底收敛为人类文案。
  - 非交互 `send-message` JSON 契约不能受影响。
- Decision:
  - 先补红测覆盖“自动建会话 + /new /use /session”的非 JSON 文案断言，再改 CLI 实现并验证门禁。
- Rationale:
  - 先锁行为再改实现，避免“看似修复但真实入口回归”。
- Evidence:
  - Tests: `<pending>`
  - Entry: `<pending>`
- Rollback:
  - `<pending>`
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - 执行 Red -> Green -> Docs。

### R2 收口（全量门禁 + managed 验收 + main 集成 + dev_tasks DONE）
- Context:
  - 需提供真实 managed 验收片段，且固定使用 `/Users/czj/miniforge3/bin/python3`。
- Decision:
  - 在 R1 完成后执行门禁与 managed 实跑，随后 rebase/merge/push 并脚本更新 M45 DONE。
- Rationale:
  - 满足里程碑出入口契约，确保结果可复核可回滚。
- Evidence:
  - Tests: `<pending>`
  - Entry: `<pending>`
- Rollback:
  - `<pending>`
- Commits: C1=`N/A`, C2=`N/A`, C3=`<pending>`
- Next:
  - 等 R1 完成后执行。
