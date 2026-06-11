# bugfix-405-M1: Chat 页实时状态修复

## 目标

在 `chat-workspace-page.tsx` 中订阅 `node.status_changed` 和 `agent.status_changed`
SSE 事件，收到后分别更新 `["chat-v2", "nodes"]` 和 `["chat-v2", "agents"]` React Query
缓存。修复后 Chat 页所有节点/Agent 在线状态展示（侧栏状态点、会话头部 Node chip、群聊 mention
候选状态）在 Gateway 断线/恢复时 1 秒内自动更新，用户无需刷新页面。

## 退出标准

- `node.status_changed` 事件到达浏览器后，Chat 页内 `nodesQuery` 缓存被即时 patch，
  所有从 nodesQuery 派生的状态展示（Node chip、侧栏状态点、mention 候选 status）同步更新。
- `agent.status_changed` 事件到达浏览器后，Chat 页内 `agentsQuery` 缓存被即时 patch。
- 上述两类事件只影响归属于对应节点/Agent 的展示，其他 Agent 展示保持不变。
- 回归测试：新增集成测试 case 覆盖 online→offline→online 状态转换路径，确认不需要刷新页面。
- 全部前端单测（`npm run test`）绿。

## 测试策略

**场景**：前端 bug 修复，已有浏览器 E2E 体系（Vitest 集成测试）。

**回归保护**：在现有 `chat-workspace.integration.test.tsx` 中补两个 case：
1. `node.status_changed` 通过 SSE 到达后，Node chip 状态从 online 切换为 offline。
2. 随后发 online 事件，chip 切回 online。

以上覆盖 fix.md 描述的双向复现场景，直接通过 WS/SSE 事件注入验证消费侧正确。

**入口验证**：真实浏览器验收（起 IM + Gateway，走复现步骤，看 Chat 页状态变化）。

## Roadpoints

### R1: 补 regression 测试（Red） [DONE]

在 `chat-workspace.integration.test.tsx` 加两个测试 case：
- Case A：SSE `node.status_changed` offline 事件 → Node chip 变为 offline 样式
- Case B：随后 SSE `node.status_changed` online 事件 → Node chip 恢复 online 样式

预期：C1 阶段 Red（chat-workspace-page 未消费这两个事件，chip 不会随事件更新）。

### R2: 实现 SSE 订阅（Green） [DONE]

在 `chat-workspace-page.tsx` 中，参考 `nodes-page.tsx` 和
`agent-status-ws-consumer.ts` 的做法，添加 `useEffect` 消费
`node.status_changed` → patch `["chat-v2", "nodes"]` 缓存，以及
`agent.status_changed` → patch `["chat-v2", "agents"]` 缓存。

### R3: 文档 + fix.md 回填 [DONE]

- 更新 tasks.md（状态 → DONE）
- 完善 progress.md
- 回填 fix.md「修复」和「验证」段
