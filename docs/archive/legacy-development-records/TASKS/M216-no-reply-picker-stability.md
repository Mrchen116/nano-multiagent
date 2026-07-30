# M216 任务计划：NO_REPLY 完成态泄漏与 fresh picker 复验稳定性

- Milestone: M216
- Title: 修复 NO_REPLY 完成态仍泄漏与 fresh picker 复验不稳定
- Branch: `milestone/M216`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M216`
- Gate: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M216/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build && pytest /Users/czj/Repos/nano-multiagent/.worktrees/M216/tests/unit/test_m170_rerun_acceptance.py`
- Baseline: 当前环境缺少 `vitest`，基线门禁在 frontend test 入口失败，属依赖缺失，不足以说明本 milestone 代码状态。

## R1 修复 NO_REPLY 完成态泄漏
- Status: DONE
- Acceptance:
  - 群聊里 suppressed NO_REPLY turn 对普通用户不显示任何 agent 成功态文案。
  - 空正文 agent message 不再仅因 `delivery_status=completed` 渲染状态块。
  - 既有正常 agent 回复与失败态不回归。
  - fresh runtime 验收检查的违禁词在该路径上消失。
- Tests Plan:
  - unit: 需要。锁定 `message-pane` 对空正文 completed agent message 的渲染行为。
  - contract: 不需要。无新增协议字段。
  - integration: 需要。锁定 `chat-workspace-page` 将 suppressed receipt 转成无可见消息。
  - e2e: 不新增。由 milestone 总门禁与 rerun 验证覆盖。
- Expected Tests:
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- DoD:
  - 先红测试证明现状缺陷。
  - 实现后 gate 全绿。
  - PROGRESS 记录根因、证据、提交哈希。

## R2 让 fresh rerun picker 路径稳定跟随 current-main UI
- Status: DONE
- Acceptance:
  - rerun 脚本不再硬编码旧的 option accessible name。
  - 脚本可根据 current-main picker 文案稳定找到 Beta 候选。
  - 单元测试覆盖新的 locator 选择策略。
  - rerun 结果继续记录 picker 候选与 composer 插入值。
- Tests Plan:
  - unit: 需要。锁定 `_pick_mention_candidate()` 的 locator 策略。
  - contract: 不需要。无新结构。
  - integration: 需要。锁定 picker 文字与 composer 插入值读取不依赖旧 handle 文案。
  - e2e: 不新增。由 milestone rerun 验证覆盖。
- Expected Tests:
  - `tests/unit/test_m170_rerun_acceptance.py`
- DoD:
  - 先红测试证明旧 locator 与 current-main UI 脱节。
  - 实现后 gate 全绿。
  - PROGRESS 记录根因、证据、提交哈希。
