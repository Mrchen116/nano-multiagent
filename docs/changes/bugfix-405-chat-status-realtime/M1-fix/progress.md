# bugfix-405-M1 progress

## R1 — 补 regression 测试（Red）

- Context: 现有集成测试只覆盖首次加载 node status online，不覆盖页面打开期间 online→offline→online 转换。
- Decision: 在 chat-workspace.integration.test.tsx 添加两个 case，通过 FakeSSE 注入事件触发状态切换，断言 Node chip class 变化。
- Rationale: 复用现有测试文件和 FakeWebSocket 基础设施，不引入新基础设施，Red 先行证明缺口真实存在。
- Evidence:
  - Tests: Red — node.status_changed 到 offline 后，chip 仍显示 online class，因为 page 未订阅事件
  - Entry: N/A（C1 阶段只写测试）
  - Frontend State Matrix: N/A（见 R2）
  - Browser QA: N/A（C1 阶段）
  - E2E/Regression: chat-workspace.integration.test.tsx（新增两 case）
  - Visual/Interaction: N/A（chip class 断言覆盖 online/offline 视觉状态）
- Rollback: C1 commit
- Commits: C1=<hash>

## R2 — 实现 SSE 订阅（Green）

- Context: 需要在 chat-workspace-page.tsx 中消费 SSE 事件，只 patch query cache，不改消息流/导航行为。
- Decision: 添加单个 useEffect，复用 attachUserConversationStream，分发 node.status_changed 和 agent.status_changed 两类事件到对应 queryClient.setQueryData。
- Rationale: 与 nodes-page.tsx/agent-status-ws-consumer.ts 的模式完全对称，不引入新机制。
- Evidence:
  - Tests: Green — 两个新 case 全绿，原有 7 个 case 保持绿
  - Entry: 真实浏览器验收（见「验证」段）
  - Frontend State Matrix: online/offline 双向覆盖; 多 agent 隔离覆盖
  - Browser QA: 见 fix.md「验证」段
  - E2E/Regression: 通过
  - Visual/Interaction: chip class 切换验证
- Rollback: C1 commit（回退至 C2 前）
- Commits: C1=<hash>, C2=<hash>

## R3 — 文档 + fix.md 回填

- Commits: C3=<hash>
