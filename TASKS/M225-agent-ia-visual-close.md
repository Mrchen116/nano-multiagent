# M225 Agent 页面信息架构与视觉收口计划

- Milestone: M225
- Title: 重做新增 Agent 页面信息架构与视觉收口
- Branch: `milestone/M225`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M225`
- Test gate: `npx pnpm --dir src/IM/frontend test -- --run agent-create agent-detail agents-list-mobile allowlist-selector router && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py`
- Scope: `src/IM/frontend/**, src/IM/api/**, tests/**, TASKS/**, PROGRESS/**, ACCEPTANCE/**, data/dev-tasks.json`
- Out of scope: `src/agent/**, src/personal_assistant/**, 与 workspace runtime 修复无关的后端深层逻辑`

## R1 收口 create/detail/list/allowlist 的信息架构与术语
- Status: TODO
- Acceptance:
  - New Agent 首屏只保留创建决策必需信息，不再把右栏提示、workspace 预览、内部术语堆成主路径噪音。
  - create/detail/list 三页对 workspace 的表达一致，能明确区分设置值、默认托管值、真实运行目录。
  - allowlist 选择器减少 chips/标签/高级项噪音，不把内部开发术语默认暴露给普通用户。
  - 列表页与详情页用词和创建页一致，不再出现 `Workspace preview`、`Read-only runtime path` 等误导语。
- Tests Plan:
  - unit: 选。以前端页面测试覆盖文案、结构和显示条件，快速锁定 IA 回归。
  - contract: 选轻量。仅保留/补充前后端 workspace/allowlist 字段契约，不改深层 runtime。
  - integration: 选。覆盖 create/detail/list 通过真实路由/API mock 的组合行为。
  - e2e: 本 Roadpoint 不单独做；真实页面证据放到 R2，避免在结构仍波动时过早固化截图。
- Expected Tests:
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agents-list-mobile.test.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
  - `src/IM/frontend/src/app/router.test.tsx`
  - `tests/im_service/integration/test_agent_create_flow.py`
  - `tests/im_service/integration/test_agent_config_api.py`
- DoD:
  - 先写会失败的测试并确认 Red
  - C1/C2/C3 提交齐全
  - 上述 test gate 全绿
  - PROGRESS 记录设计取舍、证据、回滚点、提交哈希

## R2 补真实页面产品验收证据并完成主干集成
- Status: TODO
- Acceptance:
  - 有真实页面级证据证明 create/detail/list/allowlist 收口已落地。
  - 验收记录能说明本次修复相对 M224 的新增收口点，而不是重复上次工作。
  - 最终 gate 全绿，main 合并成功，dev-tasks 更新为 DONE。
  - worktree 被清理，分支删除。
- Tests Plan:
  - unit: 不新增，复用 R1 覆盖。
  - contract: 不新增，复用 R1 与现有接口测试。
  - integration: 选。再次跑完整 gate 作为验收前门禁。
  - e2e: 选。以真实页面访问/截图/产品验收记录作为证据。
- Expected Tests:
  - `npx pnpm --dir src/IM/frontend test -- --run agent-create agent-detail agents-list-mobile allowlist-selector router`
  - `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py`
  - 真实页面截图/验收记录写入 `ACCEPTANCE/`
- DoD:
  - 真实页面证据落档
  - C1/C2/C3 提交齐全
  - main 合并并 push 成功
  - `data/dev-tasks.json` 更新为 `DONE`
  - worktree 清理完成
