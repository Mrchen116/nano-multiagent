# M144 Settings Center 真实 API 收口

## 启动记录
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`。
- 已阅读强制材料：`docs/需求.md`、`docs/IM-SPEC.md`、`docs/operator-runbook.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/M104-acceptance.md`、`PROGRESS/M134-web-im-agent-config-real-api.md`。
- 当前处境：M144，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M144`，branch=`milestone/M144`。
- 计划测试门禁：`PYTHONPATH=src pytest -q tests/im_service/contract/test_account_binding_contract.py tests/im_service/contract/test_settings_policies_contract.py tests/im_service/integration/test_account_binding_api.py tests/im_service/integration/test_settings_policies_api.py tests/im_service/integration/test_nodes_metrics_api.py::test_nodes_list_and_config_update && npm --prefix src/IM/frontend test -- src/features/settings/nodes/nodes-page.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/policies/policies-page.test.tsx`
- 基线观察：当前 `/settings/nodes`、`/settings/account`、`/settings/policies` 仍直接 import `mock-settings-api.ts`；现有 IM 后端只覆盖 nodes/account，尚无 policies API；`/im/v1/me` 也缺少前端蓝图要求的 `default_entry_node_id`。

### R1 Nodes / Account 真实 API 接线与持久化
- Context: `/settings/nodes` 与 `/settings/account` 仍走页面级 mock API；真实后端已有 `/im/v1/nodes`、`PATCH /im/v1/nodes/{id}/config`、`/im/v1/me`，但 account 缺 `default_entry_node_id`，前端也还显示 mock 独有字段。
- Decision: 新增 `src/IM/frontend/src/features/settings/im-settings-api.ts` 统一封装 nodes/account/policies 请求；nodes/account 页面切到真实 IM API；后端为 `/im/v1/me` 增补 `user_id/default_entry_node_id`，并在 bind flow 中自动维护默认入口节点；同时更新 `src/IM/frontend/dist` 让 IM host 直接服务新设置页。
- Rationale: 保持改动收口在 settings 中心，不扩散到聊天主链路；直接对齐现有 IM-SPEC 数据模型，比继续扩展 mock 兼容层更稳。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service/contract/test_account_binding_contract.py tests/im_service/contract/test_settings_policies_contract.py tests/im_service/integration/test_account_binding_api.py tests/im_service/integration/test_settings_policies_api.py tests/im_service/integration/test_nodes_metrics_api.py::test_nodes_list_and_config_update && npm --prefix src/IM/frontend test -- src/features/settings/nodes/nodes-page.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/policies/policies-page.test.tsx`；`npm --prefix src/IM/frontend run build`
  - Entry: 真实启动 `PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 8011` 与 `PYTHONPATH=src python -m personal_assistant.main --config /Users/czj/Repos/nano-multiagent/.worktrees/M144/node-config.yaml` 后，Chrome 直接访问 `/settings/nodes`、`/settings/account`；节点 alias 从 `m135-node-baseline` 持久化为 `m135-node-m144-final`，账号 display name 从 `You Baseline` 持久化为 `You Ops M144 Final`，刷新后表单仍回显；证据见 `/Users/czj/Repos/nano-multiagent/.worktrees/M144/ACCEPTANCE/M144-settings-browser-evidence.json` 与对应 PNG。
- Rollback: `32b3034`
- Commits: C1=`32b3034`, C2=`e327540`, C3=`待本次文档提交补齐`
- Next: 收口 policies 真 API 与真实浏览器验收。

### R2 Policies 真实 IM API 落地
- Context: `/settings/policies` 完全依赖 mock state，后端不存在 `/im/v1/policies`；真实浏览器回归时又暴露出一个运行态缺口：若旧 runtime DB 缺少 singleton row，`PATCH /im/v1/policies` 会在真实入口上触发 500。
- Decision: 落地 `settings_policies` 单例表、`PolicyService`、`/im/v1/policies` GET/PATCH 路由和前端真实页面接线；新增集成红测覆盖 singleton row 被删后的回种场景，并在 `SettingsPolicyRepository.get_policies()` 缺行时自动回种默认记录。
- Rationale: 单例配置文档最符合 settings center 语义；把回种逻辑收在 repository，可兼容旧 runtime DB 和真实浏览器操作，不要求人工修库。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service/integration/test_settings_policies_api.py::test_policies_reseed_missing_singleton_row`；`PYTHONPATH=src pytest -q tests/im_service/contract/test_account_binding_contract.py tests/im_service/contract/test_settings_policies_contract.py tests/im_service/integration/test_account_binding_api.py tests/im_service/integration/test_settings_policies_api.py tests/im_service/integration/test_nodes_metrics_api.py::test_nodes_list_and_config_update && npm --prefix src/IM/frontend test -- src/features/settings/nodes/nodes-page.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/policies/policies-page.test.tsx`
  - Entry: 真实 Chrome 访问 `/settings/policies`，将 policies 从 `baseline-model/basic/55` 持久化为 `gpt-5.4-settings-final/strict/111`，刷新后表单仍回显，`GET /im/v1/policies` 读回相同值；证据见 `/Users/czj/Repos/nano-multiagent/.worktrees/M144/ACCEPTANCE/M144-settings-browser-evidence.json`。
- Rollback: `ee7a874`
- Commits: C1=`32b3034` + `ee7a874`, C2=`e327540` + `fe0f038`, C3=`待本次文档提交补齐`
- Next: 产出验收报告并检查 main 合流条件。

### R3 验收报告与合流
- Context: 用户要求留下真实浏览器/真实 API 证据，并在里程碑完成后尝试合回 main；但 canonical main 工作区已有与 M144 无关的删除与未跟踪文件，不能直接在主仓上安全执行 merge。
- Decision: 产出 `ACCEPTANCE/M144-acceptance.md` 与 `ACCEPTANCE/M144-settings-browser-evidence.json`/PNG，明确记录真实 IM host、真实 Gateway、真实浏览器操作结果；合流侧先做主仓状态检查并记录 blocker，而不在脏工作区上强行执行 merge。
- Rationale: 用户更关心 settings center 是否真的跑在真实入口上；在 main 非干净时贸然 merge 会污染用户本地状态，风险高于当前记录 blocker。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service/contract/test_account_binding_contract.py tests/im_service/contract/test_settings_policies_contract.py tests/im_service/integration/test_account_binding_api.py tests/im_service/integration/test_settings_policies_api.py tests/im_service/integration/test_nodes_metrics_api.py::test_nodes_list_and_config_update && npm --prefix src/IM/frontend test -- src/features/settings/nodes/nodes-page.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/policies/policies-page.test.tsx`；`npm --prefix src/IM/frontend run build`
  - Entry: `/private/tmp/claude-501/-Users-czj-Repos-nano-multiagent/dff8d7ee-6275-4f09-a0eb-0508247a0d03/tasks/bqnz9ypem.output` 记录 IM host 真实服务 `/settings/*`、`PATCH /im/v1/nodes/...`、`PATCH /im/v1/me`、`PATCH /im/v1/policies`；`/private/tmp/claude-501/-Users-czj-Repos-nano-multiagent/dff8d7ee-6275-4f09-a0eb-0508247a0d03/tasks/bwirf4rc4.output` 记录 Gateway `STARTED`; `git -C /Users/czj/Repos/nano-multiagent status --short` 显示 main 工作区已有 unrelated 脏文件，故本次仅记录“未安全合流”的阻塞结论。
- Rollback: `fe0f038`
- Commits: C1=`ee7a874`, C2=`fe0f038`, C3=`待本次文档提交补齐`
- Next: 若需要真正合回 main，先清理 `/Users/czj/Repos/nano-multiagent` 主工作区现有脏状态，再在主仓执行 merge。
