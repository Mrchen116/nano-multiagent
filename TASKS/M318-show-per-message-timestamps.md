# M318 Show per-message timestamps in chat bubbles

## Context
- Milestone: `M318`
- Goal: 在聊天气泡中为 sent/received 消息展示轻量时间戳，帮助用户判断每条消息发送时间。
- Scope: `src/IM/frontend/src/features/chat/`

## Roadpoints

### R1 Message bubble timestamps (sent + received)
- Status: DONE
- Acceptance:
  - 每条消息（sent/received）在气泡内可见时间戳，位置紧贴消息正文与附件区域。
  - 时间戳展示保持轻量（小字号、弱化色），不干扰现有消息状态与群聊 sender label。
  - `MessagePane` 组件回归测试覆盖时间戳渲染。
  - `ChatWorkspacePage` 入口测试覆盖真实页面渲染出的时间戳。
  - 不改 unread/preview/mention 语义，不回退 M316/M317 既有行为。
- Tests Plan:
  - 在既有 `src/IM/frontend/src/features/chat/components/message-pane.test.tsx` 增加 sent/received 时间戳渲染断言（先红）。
  - 在既有 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 增加真实入口页面时间戳断言（先红）。
  - 运行派发门禁：`cd src/IM/frontend && npm test -- --run src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts`。
- DoD:
  - `test_command` 仅保留 2 个基线既有失败，未新增失败。
  - 已完成 C1/C2/C3 闭环记录，`TASKS`/`PROGRESS`/`dev-tasks.json` 同步。
