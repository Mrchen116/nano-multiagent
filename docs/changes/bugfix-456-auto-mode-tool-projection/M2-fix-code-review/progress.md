# bugfix-456-M2 - Progress

## R1 - Code review fixes

- Context: M1 已修复 auto mode 当前工具 projection 缺失问题，但 reviewer 指出四个剩余风险：历史 tool_use 仍依赖当前 registry、`skill_manage` 长文本只截断开头、`skill_manage view` 只读 fast path 未利用、当前 projection 在 gate 和 prompt builder 中重复计算。
- Decision: 历史 transcript 改用稳定通用 JSON projection，只消费历史 `name` + `input`；current action projection 由 gate 预先验证后传入 prompt builder；`skill_manage` 长文本输出 `length/head/omitted/tail`；`view` 与 `list` 同属低风险只读 action。
- Rationale: 历史证据必须反映发生当时的记录，而不是今天注册表里同名工具的新 projection；当前动作仍保留工具实例专用 projection。长文本只看前 200 字会隐藏 skill 中后段风险，因此用头尾摘要控制 prompt size 同时保留尾部危险信号。`view` 只执行 `registry.list_skills()`、读取 `SKILL.md` 和 support-file 列表，没有写路径，适合工具级 fast path。
- Evidence:
  - Tests: existing red commit `17cb47b8 test(bugfix-456/M2/R1): 覆盖 auto mode review 回归` was preserved.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_auto_mode_gate_hook.py tests/unit/test_skill_manage_tool.py tests/unit/test_auto_mode_gate.py` -> 85 passed.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_skill_manage_tool.py tests/unit/personal_assistant/test_cron_tool_permissions.py tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py tests/integration/test_tools_registry_loader_integration.py` -> 153 passed before the contract whitelist fix.
  - Tests: first `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e"` -> 3327 passed / 2 skipped / 22 deselected / 1 failed. Failure was `tests/contract/test_no_hardcoded_workspace_dirname.py`, caused by this M2 helper shifting a pre-existing whitelisted `.nanocode` fallback from line 776 to 778.
  - Debugging: per `systematic-debugging`, traceback + blame + `origin/unit/bugfix-456` comparison showed the `.nanocode` line is pre-existing (`469e557a9`) and only the line-number whitelist became stale; fix was to update the contract whitelist comment and key, not alter auto-mode config behavior.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_no_hardcoded_workspace_dirname.py` -> 1 passed.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_skill_manage_tool.py tests/unit/personal_assistant/test_cron_tool_permissions.py tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py tests/integration/test_tools_registry_loader_integration.py tests/contract/test_no_hardcoded_workspace_dirname.py` -> 154 passed.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e"` -> 3328 passed / 2 skipped / 22 deselected.
  - Lint: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff check src/agent/platform/hooks/builtins/auto_mode_gate.py src/agent/platform/tools/builtins/skill_manage.py tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_skill_manage_tool.py tests/contract/test_no_hardcoded_workspace_dirname.py` -> All checks passed.
  - Entry: Hook-level tests exercise the real auto-mode gate handler path: current `write` action reaches classifier, historical `retired_dynamic` evidence remains visible without registry lookup, same-name replacement projection is not used, and current projection is called once.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: N/A; backend permission-gate regression is covered by hook/unit/integration tests and full non-e2e suite.
  - Visual/Interaction: N/A.
  - Prototype Comparison: N/A.
- Rollback: revert M2 commits on `milestone/bugfix-456-M2`.
- Commits: C1=17cb47b8, C2=0ba3cdb9, C3=92bc399d, merge=98e83f7f.
- Cleanup: `unit/bugfix-456` pushed to `origin/unit/bugfix-456`; local M2 worktree removed; local `milestone/bugfix-456-M2` branch deleted after ancestor check; remote `milestone/bugfix-456-M2` was absent (`git ls-remote --heads origin milestone/bugfix-456-M2` returned no ref); unit lock removed.
- Next: M2 complete.
