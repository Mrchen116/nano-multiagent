# M213 群聊文案与 NO_REPLY 收口计划

## Roadpoints

### R1 群聊线程与列表隐藏 NO_REPLY 内部态
- Acceptance:
  - 普通用户在群聊线程中看不到 `NO_REPLY` 文案。
  - 群聊线程中不会因为 `relay.processing` / `relay.report` 的 `NO_REPLY` 产生“Agent is working”或“Agent replied”提示。
  - 会话列表预览不会被 `NO_REPLY` 事件覆盖成内部态文案。
  - 真实可见消息仍保留既有渲染。
- Tests Plan:
  - unit: 选。锁定 `toRelayAgentMessage` 对 `NO_REPLY` 与 receipt 的过滤。
  - contract: 不选。该 Roadpoint 无新增协议结构。
  - integration: 选。覆盖 `ChatWorkspacePage` SSE 更新线程与预览的真实入口。
  - e2e: 不选。当前 milestone 仅要求前端测试与 build 通过，仓内已有 Vitest 入口即可覆盖可见态。
- Expected Tests:
  - `src/features/chat/chat-workspace-page.test.ts`
  - 可补 `toRelayAgentMessage` 可见态断言相关测试入口
- DoD:
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M213/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build` 全绿
  - 完成 C1/C2/C3
  - `PROGRESS/M213-group-chat-copy-and-no-reply.md` 记录决策/证据/哈希
- 状态: TODO

### R2 mention picker 与群聊可见文案产品化
- Acceptance:
  - mention picker 选项只向用户显示产品化名称，不暴露 `@agent:token`。
  - 输入框中的已选 mention 以可读名称显示，键盘选择仍可用。
  - 发送 payload 仍保留稳定 mention token，保证协议兼容。
  - 群聊目标/ownership 等可见文案不再出现 `Multiple participants` 或工程化口吻。
- Tests Plan:
  - unit: 选。锁定 mention 显示值与 payload token 分离逻辑。
  - contract: 不选。协议未改，仅前端呈现与编码转换。
  - integration: 选。覆盖 `MessagePane` 输入/选择/发送与 `ChatWorkspacePage` 页面文案。
  - e2e: 不选。Vitest 入口已覆盖用户可见态与发送编码。
- Expected Tests:
  - `src/features/chat/components/message-pane.test.tsx`
  - `src/features/chat/chat-workspace-page.test.ts`
- DoD:
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M213/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build` 全绿
  - 完成 C1/C2/C3
  - `PROGRESS/M213-group-chat-copy-and-no-reply.md` 记录决策/证据/哈希
- 状态: TODO
