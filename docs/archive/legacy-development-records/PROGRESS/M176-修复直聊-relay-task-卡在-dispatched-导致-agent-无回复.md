# M176 - 修复直聊 relay task 卡在 dispatched 导致 agent 无回复

## Summary
- 复盘 M172/M174 后确认：后端 canonical relay 闭环测试当前已可把 `relay_tasks` 从 `dispatched` 推进到 `completed`，`conversation_events` 也能持久化 `relay.accepted -> relay.processing -> relay.completed -> message.delivered`。
- 当前真实用户症状更接近浏览器侧在“历史尚未 hydrate 完成时，receipt 型 agent 回复事件先到达”的场景下丢失 agent 回复展示，最终只剩用户消息 `Sent to relay`，看起来像 relay task 卡在 `dispatched`。
- 已补一条 focused 前端回归，固定 direct chat 中 `relay.completed` 在 history 之前到达时仍必须保留 agent 回复气泡，避免旧/新会话复验时再次出现“用户只见 Sent、agent 不回复”的假象。

## Evidence
- 后端闭环证据：`/Users/czj/Repos/nano-multiagent/.worktrees/M176/tests/acceptance/test_im_gateway_real_acceptance.py` 与 `tests/im_service/integration/test_m103_im_gateway_e2e.py` 现有验收均证明 relay 完成路径存在，`relay_tasks.receipt_status=completed`，并能看到 `relay.accepted/processing/completed/message.delivered`。
- 前端修复点：`/Users/czj/Repos/nano-multiagent/.worktrees/M176/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 新增 `keeps relay-completed agent replies visible after late history hydration for direct chats`，覆盖真实浏览器更接近的竞态：`relay.completed` 先于历史载入到达时，agent 回复仍需稳定显示。
- 该回归直接约束 M149 需要的旧/新会话场景：即使 direct chat 历史稍后回放，receipt 驱动的 agent 回复不能被覆盖或丢失。

## Tests
- `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M176/tests/acceptance/test_im_gateway_real_acceptance.py /Users/czj/Repos/nano-multiagent/.worktrees/M176/tests/im_service/integration/test_m103_im_gateway_e2e.py` -> `6 passed in 0.55s`
- `cd /Users/czj/Repos/nano-multiagent/.worktrees/M176/src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts` -> `22 passed`

## Commit
- `0c5529c` `test(M176): guard direct-chat reply hydration after relay completion`

## Merge readiness
- Focused regression 与 relay acceptance 已绿，可进入提交流程。
