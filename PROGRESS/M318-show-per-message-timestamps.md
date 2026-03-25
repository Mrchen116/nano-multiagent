# M318 Show per-message timestamps in chat bubbles

## Startup
- 已阅读并遵守：`docs/IM-SPEC.md`、`docs/IM前端蓝图.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M318`。
- 已链接运行态文件：`data/dev-tasks.json`、`data/locks`（指向主仓运行态目录）。
- 基线命令：`cd src/IM/frontend && npm test -- --run src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts`
- 基线结果：存在 2 个既有失败（与本里程碑目标无关，后续回归需保持不新增失败）：
  - `chat workspace relay event mapping > uses per-agent identity to keep same-turn multi-agent relay replies distinct`
  - `chat workspace page > keeps same-turn group replies from multiple agents visible instead of collapsing them`

### R1.1 Message bubble timestamps for sent + received
- Context: 现有聊天气泡缺少逐条消息时间信息，用户无法在同一会话内直接判断每条消息发送时间。
- Decision:
  - 在 `MessageBubble` 内新增 `formatMessageTimestamp`，将 `created_at` 渲染为 `HH:MM` 的轻量时间文本。
  - 在每个消息气泡正文/附件后增加 `<time data-testid="message-timestamp" dateTime={created_at}>`，sent/received 分别使用贴近现有配色的轻量样式。
  - 在 `message-pane.test.tsx` 增加 sent+received 时间戳渲染回归；在 `chat-workspace-page.test.ts` 的真实入口渲染用例增加时间戳断言，确保 SSE + 历史合并后仍可见。
- Rationale: 让时间信息成为消息级可见元数据，同时保持 WhatsApp 风格的低干扰视觉层级，不影响 sender label 与 delivery status。
- Evidence:
  - Tests: `cd src/IM/frontend && npm test -- --run src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts`
  - Result: 新增时间戳相关断言全部通过；命令总失败数仍为 2（与基线相同的既有失败），未引入新增失败。
  - Entry: `chat-workspace-page` 真实页面用例已验证消息列表渲染出 3 个 `time[data-testid='message-timestamp']`（历史 + SSE 合并链路）。
- Rollback: 回退本次涉及文件改动即可撤销（`message-pane.tsx` 与两处测试文件 + TASKS/PROGRESS 文档）。
- Commits: C1=`N/A（当前工作区未执行 git commit）`, C2=`N/A（当前工作区未执行 git commit）`, C3=`N/A（当前工作区未执行 git commit）`
- Next: 将 `M318` 状态更新为 `DONE` 并回传里程碑摘要。
