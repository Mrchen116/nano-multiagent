# M225 Agent 页面信息架构与视觉收口进度

## Milestone 摘要
- Goal: 基于当前 create/detail/list/allowlist 页面，收口明显产品缺陷：信息过载、术语误导、右栏噪音、allowlist 视觉穿模与 workspace 相关误导文案。
- Constraints:
  - 只改 `src/IM/frontend/**`, `src/IM/api/**`, `tests/**`, `TASKS/**`, `PROGRESS/**`, `ACCEPTANCE/**`, `data/dev-tasks.json`
  - 不碰 `src/agent/**`, `src/personal_assistant/**`, 与 workspace runtime 修复无关的后端深层逻辑
  - 需要真实页面/产品验收证据

### Plan
- R1: 收口 create/detail/list/allowlist 的信息架构与术语
- R2: 补真实页面产品验收证据并完成主干集成

### R1 收口 create/detail/list/allowlist 的信息架构与术语
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `npx pnpm --dir src/IM/frontend test -- --run agent-create agent-detail agents-list-mobile allowlist-selector router && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py`
  - Entry: 待补
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 写失败测试，明确 M225 相对 M224 的新增收口点

### R2 补真实页面产品验收证据并完成主干集成
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `npx pnpm --dir src/IM/frontend test -- --run agent-create agent-detail agents-list-mobile allowlist-selector router && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py`
  - Entry: 待补
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 真实页面验收与 main 集成
