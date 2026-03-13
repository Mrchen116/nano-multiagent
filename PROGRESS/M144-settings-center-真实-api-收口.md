# M144 Settings Center 真实 API 收口

## 启动记录
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`。
- 已阅读强制材料：`docs/需求.md`、`docs/IM-SPEC.md`、`docs/operator-runbook.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/M104-acceptance.md`、`PROGRESS/M134-web-im-agent-config-real-api.md`。
- 当前处境：M144，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M144`，branch=`milestone/M144`。
- 计划测试门禁：`PYTHONPATH=src pytest -q tests/im_service/contract/test_account_binding_contract.py tests/im_service/contract/test_settings_policies_contract.py tests/im_service/integration/test_account_binding_api.py tests/im_service/integration/test_settings_policies_api.py tests/im_service/integration/test_nodes_metrics_api.py::test_nodes_list_and_config_update && npm --prefix src/IM/frontend test -- src/features/settings/nodes/nodes-page.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/policies/policies-page.test.tsx`
- 基线观察：当前 `/settings/nodes`、`/settings/account`、`/settings/policies` 仍直接 import `mock-settings-api.ts`；现有 IM 后端只覆盖 nodes/account，尚无 policies API；`/im/v1/me` 也缺少前端蓝图要求的 `default_entry_node_id`。

### R1 Nodes / Account 真实 API 接线与持久化
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 Policies 真实 IM API 落地
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R3 验收报告与合流
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
