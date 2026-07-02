# feat-446-M1 — Progress

## Startup

- Context: 按 `change-impl-worker` full 模式执行，worktree 为 `/Users/czj/Repos/nano-multiagent/.worktrees/feat-446-M1`，分支为 `milestone/feat-446-M1`。
- Evidence:
  - Read: `AGENTS.md`、`docs/TESTING_GUIDE.md`、`LOGBOOK.md`、`docs/changes/feat-446-skill-view-tool/spec.md`、`design.md`、`specs/kernel/spec.md`、`specs/gateway/spec.md`、`specs/im/spec.md`、`change-impl-worker/SKILL.md`。
  - Baseline: `PYTHONPATH=src pytest tests/unit/test_skill_manage_tool.py tests/unit/test_agent_prompting.py tests/unit/test_agent_runtime_compaction_guardrails.py tests/contract/ -x` -> 171 passed。

## R1 — tool contract and usage sidecar

- Context: `skill_manage` 原本同时承担 view + write，导致无法单独审计 skill 读取；M1 要先把读侧拆为 `skill_view`，并用 `.usage.json` 记录成功读取。
- Decision: 新增 `SkillViewTool`、`core/skills/usage.py` 和 `core/skills/root_resolver.py`；`skill_manage` 删除 view action，`create` 增加 `scope=agent|pa`；SDK 注册 `skill_view`，PA product 传入 PA root。
- Rationale: root 解析下沉到 core，`skill_manage` 和 `skill_view` 共享同一套 agent root + deployment roots 优先级；usage sidecar 以 `{session_id}:{tool_call_id}` 幂等，失败 view 不落统计；PA root 只在产品显式注入时可写，缺失时失败不回退。
- Evidence:
  - Tests: C1 红测 `PYTHONPATH=src pytest tests/unit/test_skill_view.py tests/unit/test_usage.py tests/unit/test_skill_manage_tool.py -x` -> 失败，`ModuleNotFoundError: agent.platform.tools.builtins.skill_view`；C2 后同命令 -> 32 passed；SDK 接线 `PYTHONPATH=src pytest tests/contract/test_sdk_kernel_wiring.py tests/contract/test_kernel_sdk_behavior_contract.py tests/unit/agent/test_kernel_list_capability_queries.py -x` -> 27 passed。
  - Entry: `SkillViewTool.run({"name": ...})` 行为测试覆盖真实 tool run：返回 SKILL.md content/location，写 `.usage.json`，注册 invoked skill；`SkillManageTool.run(create, scope=pa)` 行为测试覆盖 PA root 写入与无 PA root 失败不回退。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `tests/unit/test_skill_view.py`、`tests/unit/test_usage.py`、`tests/unit/test_skill_manage_tool.py`；本 roadpoint 是内核工具行为，不起真服务。
  - Visual/Interaction: N/A
- Rollback: revert `3746d84` and `10b8b36` together to remove R1 implementation/tests.
- Commits: C1=10b8b36, C2=3746d84, C3=TODO
- Next: R2

## R2 — prompt gates, defaults, and self-improvement

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: R3

## R3 — compaction survival and final contract gate

- Context: TODO
- Decision: TODO
- Rationale: TODO
- Evidence:
  - Tests: TODO
  - Entry: TODO
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: TODO
  - Visual/Interaction: N/A
- Rollback: TODO
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next: DONE
