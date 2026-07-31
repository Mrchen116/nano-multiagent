# M161 Progress — Agent 设置页展示 Workspace 路径并支持配置

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M161`
- 已确认 branch：`milestone/M161`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 首轮阅读文件：
  - `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts`
  - `src/IM/api/routes/agents.py`
  - `src/IM/application/config_service.py`
  - `src/IM/infra/repositories.py`
  - `src/personal_assistant/main.py`

## 初始根因判断
- Agent 列表页只暴露 profile 摘要，没有 workspace 路径字段，导致用户无法确认每个 Agent 的实际工作目录。
- Agent 详情页缺少 workspace 设置入口，当前 UI 只能改行为配置，无法改工作目录。
- IM Agent 配置接口和持久层未纳入 workspace 字段，gateway config sync 仍以默认目录兜底，导致“看不到也配不了”的问题同时存在。

## 执行策略
1. 先补 `TASKS/M161` 与 `PROGRESS/M161`，锁定 Roadpoints、验证门禁与回滚边界。
2. 再打通 IM agent config 的 workspace 数据模型、接口和 gateway sync 消费路径。
3. 最后补 Agent 列表/详情/创建页的 workspace 展示与设置 UI，并跑聚焦验证。

## 进度

### R1 打通 workspace 路径数据模型与接口
- Status: DONE
- Context:
  - 当前 Agent profile schema 不存 workspace，接口也无法返回/保存该信息。
- Decision:
  - 为 `agent_profiles` 增加 `workspace_root` 持久化字段，并在 `AgentProfile` / repository / API response 中统一返回 `workspace_root` 与 `workspace_is_default`。
  - `ConfigService` 负责规范化 workspace 配置：空值表示使用托管默认目录，非空值必须是绝对路径或 `~/...`。
  - gateway `_IMConfigSyncClient` 改为优先消费 IM 配置返回的 `workspace_root`，避免继续硬编码默认目录。
- Rationale:
  - 只有把存储、接口和 sync 三层同时打通，前端的“看到路径”和“保存设置”才是真正可用的产品闭环。
- Evidence:
  - `src/IM/domain/models.py`
  - `src/IM/infra/db.py`
  - `src/IM/infra/repositories.py`
  - `src/IM/application/config_service.py`
  - `src/IM/api/routes/agents.py`
  - `src/personal_assistant/main.py`
  - `tests/im_service/contract/test_agent_config_contract.py`
  - `tests/im_service/contract/test_agent_create_contract.py`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/integration/test_agent_create_flow.py`
  - `tests/unit/personal_assistant/test_main.py`

### R2 设置页展示当前 workspace 并提供可编辑入口
- Status: DONE
- Context:
  - 前端设置页没有 workspace 行，用户也没有进入配置的明显入口。
- Decision:
  - Agent 列表页增加 workspace 模式、当前路径与 `Workspace settings` 入口，列表和移动卡片都可直接看到每个 Agent 的工作目录。
  - Agent 详情页新增 `Current workspace` 只读区与 `Workspace Path Setting` 可编辑输入，明确区分运行时当前路径和可保存配置。
  - Agent 创建页新增 workspace 设置输入与当前路径预览，空值时明确提示会采用托管默认路径。
- Rationale:
  - 把“当前实际路径”和“可编辑配置”分开呈现，才能满足用户既要看见真实目录、又要理解如何修改的需求。
- Evidence:
  - `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts`
  - `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agents-list-mobile.test.tsx`
  - `src/IM/frontend/dist/index.html`
  - `src/IM/frontend/dist/assets/index-M82Qcduf.css`
  - `src/IM/frontend/dist/assets/index-Dw2Ti_Tx.js`

### R3 聚焦验证、记录与收口
- Status: DONE
- Tests:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/im_service/contract/test_agent_config_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/im_service/contract/test_agent_create_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/im_service/integration/test_agent_create_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/unit/personal_assistant/test_main.py`
    - 结果：`32 passed`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M161/src/IM/frontend test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agents-list-mobile.test.tsx`
    - 首次结果：失败，原因是 worktree 未安装前端依赖，`vitest: command not found`
    - 修复：执行 `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M161/src/IM/frontend ci`
    - 复跑结果：`3 passed files / 9 passed tests`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M161/src/IM/frontend run build`
    - 首次结果：失败，原因是 `agent-edit.test.tsx` 中 mock 类型与 `workspace_root: string | null` 不兼容
    - 修复：收紧 `currentConfig` 类型并在 PATCH mock 中将 `null` 回填为默认路径字符串
    - 复跑结果：`vite build` 成功，产出 `dist/assets/index-M82Qcduf.css` 与 `dist/assets/index-Dw2Ti_Tx.js`
- Commits:
  - C1=`ab231f2` docs(M161): record workspace settings roadmap
  - C2=`4776b43` feat(M161): persist and sync agent workspace settings
  - C3=`a2cb015` feat(M161): show and edit workspace paths in agent settings

## 当前结论
- Agent 列表页和详情页现在都能直接看到每个 Agent 的当前 workspace 路径。
- 用户可以在设置页通过明确的 workspace 配置输入修改目录，且 UI 已明确区分只读当前路径和可编辑设置。
- 后端接口、gateway config sync、前端展示/保存链路和关键测试已一起收口，满足 milestone 的展示与配置要求。

## M146 / M104 复验提示
- 本变更合入 `main` 后，应把 Agent 设置页 workspace 可见性与可配置性纳入 M146 / M104 产品复验，确认真实 IM 绑定后的 Agent 工作目录展示与保存行为一致。

## Commits
- `ab231f2` docs(M161): record workspace settings roadmap
- `4776b43` feat(M161): persist and sync agent workspace settings
- `a2cb015` feat(M161): show and edit workspace paths in agent settings

## 回滚点
- 若需回滚本 milestone，撤回以下文件即可：
  - `src/IM/api/routes/agents.py`
  - `src/IM/application/config_service.py`
  - `src/IM/domain/models.py`
  - `src/IM/infra/db.py`
  - `src/IM/infra/repositories.py`
  - `src/personal_assistant/main.py`
  - `tests/im_service/contract/test_agent_config_contract.py`
  - `tests/im_service/contract/test_agent_create_contract.py`
  - `tests/im_service/integration/test_agent_config_api.py`
  - `tests/im_service/integration/test_agent_create_flow.py`
  - `tests/unit/personal_assistant/test_main.py`
  - `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts`
  - `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agents-list-mobile.test.tsx`
  - `src/IM/frontend/dist/index.html`
  - `src/IM/frontend/dist/assets/index-M82Qcduf.css`
  - `src/IM/frontend/dist/assets/index-Dw2Ti_Tx.js`
  - `TASKS/M161-Agent-设置页展示-Workspace-路径并支持配置.md`
  - `PROGRESS/M161-Agent-设置页展示-Workspace-路径并支持配置.md`
