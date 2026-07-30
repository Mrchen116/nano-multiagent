# M208 Implementation Proof — 修复群聊 NO_REPLY 仍显示运行中气泡

- Milestone: M208
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M208`
- Branch: `milestone/M208`
- Fresh browser evidence: `/Users/czj/Repos/nano-multiagent/src/IM/frontend/.playwright-cli/page-2026-03-16T03-13-50-289Z.yml`
- Structured backend evidence: `/Users/czj/Repos/nano-multiagent/output/playwright/m170-no-reply-running-leak-20260316.json`
- Runtime DB: `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/im_service.sqlite3`

## 唯一 blocker 与根因
- 唯一 blocker：fresh M170 真实浏览器群聊里，NO_REPLY turn 仍显示可见 `NO_REPLY` 正文与 `Agent is working` 气泡。
- 实现侧根因：M206 只吞掉了 completion / delivery 阶段的 suppressed receipt，但前端 `toRelayAgentMessage()` 仍会把 `relay.processing.summary="NO_REPLY"` 与 `relay.report.summary="NO_REPLY"` 提前合成为 synthetic agent message，因此用户会先看到 running / completed 气泡，再由后续 suppressed receipt 静默收口。

## 最小修复
- 文件：`/Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
- 方案：新增精确 `NO_REPLY` 协议 token 判定，并在 relay synthetic message 映射层直接静默返回 `null`；这样 processing / report / completed 任何阶段只要正文就是 `NO_REPLY`，都不会在前端生成可见 agent bubble 或刷新会话列表预览。

## 自动化证据
### 红测
- 文件：`/Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- 新增测试：
  - `keeps relay.processing NO_REPLY tokens out of visible agent messages`
  - `keeps relay.report NO_REPLY tokens out of visible agent messages`
  - `keeps NO_REPLY processing and report events out of the live group thread and conversation preview`
- 红测结果：在修复前失败，并返回可见 synthetic agent message：
  - `content="NO_REPLY"`
  - `delivery_status="running"` / `delivery_status="completed"`

### 绿测
- 前端目标测试：
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && ./node_modules/.bin/vitest run src/features/chat/chat-workspace-page.test.ts`
  - 结果：`29 passed`
- 前端 chat 门禁：
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts*`
  - 结果：`67 passed`
- 前端 build：
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && npm run build`
  - 结果：`built in 727ms`
- 后端门禁：
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/unit/test_relay_service.py`
  - 结果：`17 passed in 0.81s`

## 不回归边界
- 未改后端 relay schema、gateway receipt shape、mention parsing、群聊路由或双 Agent 回复语义。
- 现有正常 `relay.processing` / `relay.report` 文案仍保留；只对精确 `NO_REPLY` token 静默。
- typed mention、picker mention、双 Agent 同线程回复继续由前端 chat suite 与 M103 相关后端门禁覆盖。

## 主 agent 重验步骤
1. 使用 fresh canonical M170 runtime 进入真实 IM 前端群聊。
2. 把 Alpha prompt 设为 `Reply exactly with NO_REPLY.`。
3. 发送 `@agent-m170-alpha no-reply check: stay silent now.`。
4. 验证：
   - 不新增任何可见 running / completed agent bubble。
   - 不显示 `NO_REPLY`、`suppressed_by=no_reply_token`、`Agent is working`、`Agent replied`。
   - 会话列表最后预览保持上一条真实可见消息，不被 NO_REPLY 覆盖。
5. 同时回归：group creation、typed mention、picker mention、双 Agent 同线程回复。
