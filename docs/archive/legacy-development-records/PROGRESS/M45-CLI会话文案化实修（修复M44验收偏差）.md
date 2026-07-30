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
  - `repl_commands` 新增/使用会话文案输出函数（`print_session_created/print_session_switched/print_active_session`），并在 `commands._run_repl` 的自动建会话路径复用 `print_session_created`。
  - `/use` 执行后立即补打一条 `Active session: ...`，保证切换反馈与当前 prompt 一致。
- Rationale:
  - 先锁行为再改实现，避免“看似修复但真实入口回归”。
- Evidence:
  - Tests:
    - 红测：`tests/unit/test_cli_main.py` 会话文案断言（`153f8d2`）。
    - 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `103 passed, 42 warnings`。
  - Entry:
    - managed 抽检输出：
      - `Started new session sess_93d1f5a2bc313f58.`
      - `Active session: sess_93d1f5a2bc313f58.`
      - `/new` 后：`Started new session sess_655b8bcbed174154.` + `Active session: sess_655b8bcbed174154.`
      - `/use sess_manual` 后：`Switched to session sess_manual.` + `Active session: sess_manual.`
      - `/session`：`Active session: sess_manual.`
- Rollback:
  - `153f8d2`（R1 红测起点）
- Commits: C1=`153f8d2`, C2=`07c1869`, C3=`本提交（docs R1.1）`
- Next:
  - 进入 R2 收口：统一门禁证据、主干集成与里程碑状态更新。

### R2 收口（全量门禁 + managed 验收 + main 集成 + dev_tasks DONE）
- Context:
  - 需提供真实 managed 验收片段，且固定使用 `/Users/czj/miniforge3/bin/python3`。
- Decision:
  - 在 R1 完成后执行全量门禁与 managed 实跑，并以独立 Milestone 分支整体集成到 main。
  - `dev_tasks.py` 统一回填 M45 `DONE` 与 result，保持控制塔状态一致。
- Rationale:
  - 满足里程碑出入口契约，确保结果可复核可回滚。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `103 passed, 42 warnings`
  - Entry:
    - managed 验收命令：`PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8005 --token test-token`
    - 输出确认会话相关路径不再直出 JSON。
- Rollback:
  - `07c1869`（R1 绿测稳定点）
- Commits: C1=`N/A`, C2=`N/A`, C3=`本提交（docs R2.1）`
- Next:
  - rebase/merge/push 并将 `M45` 更新为 `DONE`。
