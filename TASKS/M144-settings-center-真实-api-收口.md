# M144 Settings Center 真实 API 收口

## 前置确认
- 已阅读 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`。
- 已阅读强制材料：`/Users/czj/Repos/nano-multiagent/.worktrees/M144/docs/需求.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M144/docs/IM-SPEC.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M144/docs/operator-runbook.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/M104-acceptance.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M144/PROGRESS/M134-web-im-agent-config-real-api.md`。
- 注释/文档承诺：新增 public API 使用 Google 风格 docstring；注释只解释意图、约束、边界。
- 不修改 `data/dev-tasks.json`，不创建额外 worktree，仅在 `/Users/czj/Repos/nano-multiagent/.worktrees/M144` 工作。

## 当前处境
- Milestone: `M144 / Settings Center 真实 API 收口`
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M144`
- branch: `milestone/M144`
- test_command: `PYTHONPATH=src pytest -q tests/im_service/contract/test_account_binding_contract.py tests/im_service/contract/test_settings_policies_contract.py tests/im_service/integration/test_account_binding_api.py tests/im_service/integration/test_settings_policies_api.py tests/im_service/integration/test_nodes_metrics_api.py::test_nodes_list_and_config_update && npm --prefix src/IM/frontend test -- src/features/settings/nodes/nodes-page.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/policies/policies-page.test.tsx`
- allowed_scope: `src/IM/**`、`tests/im_service/**`、`src/IM/frontend/src/features/settings/**`、`TASKS/**`、`PROGRESS/**`、`ACCEPTANCE/**`
- forbidden_scope: `data/dev-tasks.json`、额外 worktree、与 settings 收口无关的 agent/kernel/gateway 路径
- prevention_rules:
  - 先红后绿，最小改动，不把 unrelated metrics 问题卷入本 milestone。
  - `/settings/nodes`、`/settings/account`、`/settings/policies` 必须走真实 IM API，不保留页面级 mock import。
  - 浏览器证据必须指向真实 IM host 与真实 HTTP API，不接受静态 mock 页面截图。
  - 节点/账号 UI 展示字段必须与 live IM 数据模型对齐，不能继续显示 mock 独有字段。

## Roadpoints

### R1 Nodes / Account 真实 API 接线与持久化
- Status: DONE
- Acceptance:
  - `/settings/nodes` 不再 import `mock-settings-api.ts`，改走真实 `/im/v1/nodes` 与 `PATCH /im/v1/nodes/{id}/config`
  - `/settings/account` 不再 import mock，改走真实 account API，并能持久化显示名/默认入口节点
  - 页面 reload 后仍能读回刚保存的数据
  - UI 展示的节点状态、节点别名、owned nodes 与 live IM API 返回一致
- Tests Plan:
  - unit: 不单拆，前端页面测试已覆盖 UI 状态/交互
  - contract: 需要，补齐 `/im/v1/me` 的稳定字段契约
  - integration: 需要，覆盖 account/default entry node roundtrip 与 node config roundtrip
  - e2e: 需要，用真实浏览器在 IM host 上编辑 nodes/account 并复读 API 结果
- Expected Tests:
  - `tests/im_service/contract/test_account_binding_contract.py`
  - `tests/im_service/integration/test_account_binding_api.py`
  - `tests/im_service/integration/test_nodes_metrics_api.py::test_nodes_list_and_config_update`
  - `src/IM/frontend/src/features/settings/nodes/nodes-page.test.tsx`
  - `src/IM/frontend/src/features/settings/account/account-page.test.tsx`
- DoD:
  - 定向测试先红后绿
  - `test_command` 全绿
  - 真实浏览器完成 nodes/account 编辑并经真实 API 复核
  - 完成 C1/C2/C3

### R2 Policies 真实 IM API 落地
- Status: DONE
- Acceptance:
  - IM 服务新增稳定的 policies HTTP API，并带持久化存储
  - `/settings/policies` 改走真实 GET/PATCH，而不是本地 mock state
  - 浏览器编辑 policies 后刷新仍能读回
  - 默认值与空库初始化可预测，不依赖前端硬编码 mock state
- Tests Plan:
  - unit: 不单拆，repository/service 路径由 contract/integration 覆盖
  - contract: 需要，冻结 `/im/v1/policies` response/request 结构
  - integration: 需要，覆盖空库默认值与 PATCH 持久化 roundtrip
  - e2e: 需要，用真实浏览器完成 policies 编辑并经真实 API 复核
- Expected Tests:
  - `tests/im_service/contract/test_settings_policies_contract.py`
  - `tests/im_service/integration/test_settings_policies_api.py`
  - `src/IM/frontend/src/features/settings/policies/policies-page.test.tsx`
- DoD:
  - 定向测试先红后绿
  - `test_command` 全绿
  - 真实浏览器完成 policies 编辑并经真实 API 复核
  - 完成 C1/C2/C3

### R3 验收报告与合流
- Status: DONE（已完成验收，main 合流因主仓工作区非干净状态而未执行）
- Acceptance:
  - 形成 `ACCEPTANCE/M144-acceptance.md`，记录真实 API / 真实浏览器证据与复验结论
  - 明确列出 test_command 与实际执行结果
  - 若 main 可快进/正常 merge，则完成 milestone 分支合回 main；若不能，明确卡点
- Tests Plan:
  - unit/contract/integration: 复用前两项成果，不新增测试面
  - e2e: 需要，最终浏览器复验作为报告证据
- Expected Tests:
  - `test_command`
  - 真实浏览器手动/自动化验收脚本
- DoD:
  - 验收报告落盘
  - 分支合流状态明确
  - `PROGRESS` 写清证据、回滚点、提交哈希
