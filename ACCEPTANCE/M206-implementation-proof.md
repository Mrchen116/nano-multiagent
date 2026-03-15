# M206 Implementation Proof — 让真实群聊中的 NO_REPLY 对用户完全静默

- Milestone: M206
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M206`
- Branch: `milestone/M206`
- Source acceptance blocker: `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M170-acceptance.md` Issue 1

## 唯一 blocker 与根因
- 唯一 blocker：真实群聊中的 `NO_REPLY` turn 仍向用户暴露 `suppressed_by=no_reply_token` 与 `Agent replied`。
- 实现侧根因：前端 `toRelayAgentMessage()` 只对 `relay.completed` 的 suppressed receipt 做过滤，但 gateway 在 completed receipt 后还会追加同 `message_id` 的 `message.delivered` 事件；该事件缺少显式 `sender_type`，因此会被前端继续合成为 synthetic completed agent message，最终出现可见 bubble 与成功态。

## 最小修复
- 文件：`/Users/czj/Repos/nano-multiagent/.worktrees/M206/src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
- 方案：新增 `isSuppressedNoReplyReceipt()`，把 suppressed `NO_REPLY` 过滤从仅 `relay.completed` 扩展到同链路的 `message.delivered`，其余事件、payload shape 与直聊显示语义不变。

## 自动化证据
### 红测
- 文件：`/Users/czj/Repos/nano-multiagent/.worktrees/M206/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- 新增测试：`keeps suppressed NO_REPLY delivery receipts out of visible agent messages`
- 红测结果：在修复前失败，并返回可见 synthetic agent message：
  - `content="NO_REPLY | suppressed_by=no_reply_token"`
  - `delivery_status="completed"`

### 绿测
- 前端目标测试：
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M206/src/IM/frontend && ./node_modules/.bin/vitest run src/features/chat/chat-workspace-page.test.ts`
  - 结果：`25 passed`
- 前端 chat 门禁：
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M206/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts*`
  - 结果：`63 passed`
- 后端 unit 门禁：
  - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M206/tests/im_service/unit/test_relay_service.py`
  - 结果：`7 passed in 0.12s`
- 完整 backend gate 现状：
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py` 在既有测试 `test_web_im_message_roundtrip_browserless` 处长时间卡住；verbose 运行已确认前 3 个测试通过，阻塞点不在本次 NO_REPLY 前端修复路径。
- 前端完整门禁说明：为兼容当前 Vitest 版本，本次把 `package.json` 的 `test` 脚本调整为过滤透传的 `--runInBand`，使既有 milestone `test_command` 仍可直接运行。

## 不回归边界
- 未改后端 relay schema、gateway receipt shape、mention parsing 或多 Agent 路由。
- 现有直聊 `relay.completed` 可见回归仍保留。
- 群聊 typed mention、picker mention、双 Agent 同线程回复依赖的 payload/事件语义未改，仍由既有 M103 与前端 chat suite 覆盖。

## 主 agent 重验步骤
1. 使用 fresh canonical M170 runtime 重启并进入真实 IM 前端。
2. 在群聊中把 Alpha prompt 改为 `Reply exactly with NO_REPLY.`。
3. 发送 `@agent-m170-alpha no-reply check: stay silent now.`。
4. 验证：
   - 不新增任何可见 agent bubble。
   - 不显示 `suppressed_by=no_reply_token`。
   - 不显示 `NO_REPLY`、旧 ACK、`Agent replied`。
5. 同时回归：group creation、typed mention、picker mention、双 Agent 同线程回复。
