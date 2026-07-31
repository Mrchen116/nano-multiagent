# M319 Fix stale and gradually-refreshing conversation previews

## Context
- Milestone: `M319`
- Goal: 修复会话列表最后一条消息预览与真实最新消息不一致、且打开会话后预览才逐步“追平”的问题。
- Scope: `src/IM/frontend/src/features/chat/`
- Out of scope: 未读角标、时间戳展示、mention 语义等非预览一致性问题。

## Roadpoints

### R1 Preview state source-of-truth alignment
- Status: DONE
- Acceptance:
  - 会话列表预览与当前会话真实最新消息内容保持一致，不出现旧文案残留拼接。
  - 新消息发送/到达后，左栏预览可立即更新，无需打开会话等待多步追平。
  - 打开会话后，不出现“旧预览 + 增量 delta”逐步替换的可见抖动。
  - 在现有 `chat-workspace-page.test.ts` / `chat-layout.test.tsx` 相关测试集中补充回归覆盖。
- Tests Plan:
  - 在 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 增加回归用例：复现 stale preview + text_delta 拼接抖动，并断言修复后预览直接对齐最新消息。
  - 运行 `cd src/IM/frontend && npm test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx`。
- DoD:
  - ✅ `test_command` 已执行，新增回归通过；保留 2 个既有无关失败。
  - ✅ C1/C2/C3 三提交完整。
  - ✅ `TASKS`/`PROGRESS`/`data/dev-tasks.json` 已同步更新。
