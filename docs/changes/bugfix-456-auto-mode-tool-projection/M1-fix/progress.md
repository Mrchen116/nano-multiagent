# bugfix-456-M1 — Progress

## R1 — 工具协议 projection 与权限 gate 修复

- Context: `auto_mode_gate` 的中央 projection 表只覆盖少量静态工具，`skill_manage create` 这类非 safe 当前动作没有进入 classifier prompt，导致 classifier 只看到历史 `bash rm -rf cold-joke-on-insult` 并把历史风险误归因到当前工具。
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: Red baseline captured before implementation: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/test_auto_mode_gate.py tests/unit/test_auto_mode_gate_hook.py tests/unit/test_auto_mode_gate_allowlist.py tests/unit/test_auto_mode_gate_dispatch.py tests/unit/test_skill_manage_tool.py tests/unit/personal_assistant/test_cron_tool_permissions.py tests/unit/agent/platform/tools/builtins/test_web_fetch_permissions.py tests/integration/test_tools_registry_loader_integration.py` -> 20 failed / 127 passed. Failures prove central `TOOL_PROJECTIONS` still exists, `skill_manage`/`cron`/`web_fetch` lack classifier projection, dynamic loaded tools are not wrapper-projected, and unknown/missing projection still reaches old behavior.
  - Entry: Red hook-level entry test added for `skill_manage create` after historical `bash rm -rf cold-joke-on-insult`; current implementation omits `skill_manage` from classifier prompt.
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
  - Prototype Comparison: N/A
- Rollback: revert R1 commits on `milestone/bugfix-456-M1`.
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: 实现工具协议 projection 并让红测转绿。
