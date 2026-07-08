# bugfix-456-M1 — Progress

## R1 — 工具协议 projection 与权限 gate 修复

- Context: `auto_mode_gate` 的中央 projection 表只覆盖少量静态工具，`skill_manage create` 这类非 safe 当前动作没有进入 classifier prompt，导致 classifier 只看到历史 `bash rm -rf cold-joke-on-insult` 并把历史风险误归因到当前工具。
- Decision: 删除 `auto_mode_gate` 中央 projection 表，改为工具实例 `to_auto_classifier_input()` + `ToolRegistry.register()` 通用结构化 wrapper；非 safe 当前动作缺 projection 时 fail-closed。
- Rationale: 当前误判来自“当前 action 空投影 + 历史危险动作仍在 transcript”。把 projection 绑定到工具实例和注册边界后，内置工具、PA native tool、dynamic/user tool 都有同一入口；unknown tool 仍然不可执行到 classifier，避免空 current action 串台。
- Evidence:
  - Tests: Red baseline captured before implementation: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_skill_manage_tool.py tests/unit/personal_assistant/test_cron_tool_permissions.py tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py tests/integration/test_tools_registry_loader_integration.py` -> 20 failed / 127 passed. Failures prove central `TOOL_PROJECTIONS` still exists, `skill_manage`/`cron`/`web_fetch` lack classifier projection, dynamic loaded tools are not wrapper-projected, and unknown/missing projection still reaches old behavior.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_skill_manage_tool.py tests/unit/personal_assistant/test_cron_tool_permissions.py tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py tests/integration/test_tools_registry_loader_integration.py` -> 147 passed.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_tool_gate_coverage.py tests/integration/test_hooks_runtime_tools_integration.py` -> 4 passed.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_no_hardcoded_workspace_dirname.py tests/unit/test_path_sandbox_via_hook.py` -> 7 passed.
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e"` -> 3322 passed / 2 skipped / 22 deselected.
  - Lint: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff check <modified files>` -> All checks passed.
  - Entry: Hook-level regression covers `skill_manage create` after historical `bash rm -rf cold-joke-on-insult`; classifier prompt now includes `skill_manage` action/name/scope projection, so current action is visible.
  - Entry: This lite backend bugfix validates the user-visible permission-card reason source through the tool-call hook/gate path before the card is emitted. IM live was not run because this change does not touch IM frontend or transport; the observed reason串台 is determined by gate current-action projection.
  - Cleanup: local milestone worktree/branch removed; remote `origin/milestone/bugfix-456-M1` deleted and `git branch -r --list 'origin/milestone/bugfix-456-M1'` confirmed empty.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: full non-e2e regression passed; no live IM browser journey was required for this lite backend bugfix.
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: revert R1 commits on `milestone/bugfix-456-M1`.
- Commits: C1=a7cc7a2b, C2=074bc9eb, C3=00704ad5, C4=signoff cleanup commit
- Next: 无，R1 已合并并 push 到 `unit/bugfix-456`，milestone local/remote branch cleanup completed.
