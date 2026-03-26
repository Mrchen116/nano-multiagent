# M325 Frontend node-first agent settings UX

## Startup
- 已阅读并遵守：`/Users/czj/Repos/nano-multiagent/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/COMMENTING_GUIDE.md`、`/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md`、`/Users/czj/Repos/nano-multiagent/docs/IM前端蓝图.md`、`/Users/czj/Repos/nano-multiagent/docs/需求.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M325`。
- 已将 `data/dev-tasks.json`、`data/locks` 链接到主仓运行态目录。
- Baseline: `cd /Users/czj/Repos/nano-multiagent/src/IM/frontend && npm test -- --runInBand agent-create agent-edit nodes-page settings-scroll-layout router` 通过（18 tests passed）。

### R1.1 Node-first create flow and capability-backed settings
- Context: 代理创建入口仍保留在 `/settings/agents`，创建页依赖全局 allowlist/nodes 拼装运行时选项，编辑页也没有展示 owning node 或能力快照，导致前端和节点真实运行时约束不一致。
- Decision: 将创建入口收敛到 Nodes 列表里的在线节点卡片；新增 `/settings/nodes/:nodeId/agents/new` 路由；创建页改为直接读取 `getNodeCreateState(nodeId)` 并提交 `createNodeAgent(nodeId, payload)`；编辑页改为读取 `getAgentDetailState(agentId)`，用 agent capabilities 渲染技能/工具/模型选项，同时把 `workspace_root` 固定为只读展示。
- Rationale: 节点是代理运行时归属的真实边界，只有从节点上下文出发才能保证创建时的模型、技能、工具和工作区信息与线上能力快照一致；编辑页展示 owning node 与 capabilities timestamp，能让操作者直接确认当前配置是否仍匹配运行时。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M325/src/IM/frontend && npm test -- --runInBand agent-create agent-edit nodes-page settings-scroll-layout router`（19 tests passed）
  - Entry: 路由测试与 settings shell 测试已覆盖 `/settings/nodes/node-1/agents/new`；nodes page 测试证明仅 online 节点显示创建入口；agent-create/agent-edit 测试证明节点能力快照与代理能力快照会驱动真实页面表单与 CTA 行为。
- Rollback: 可回退到 `2310439`（plan 提交）后重新执行 R1.1；如仅回退实现则撤销 `94ad20f`。
- Commits: C1=`ef53938`, C2=`94ad20f`, C3=TODO
- Next: 推送 milestone/M325，并继续按流程做集成前检查。
