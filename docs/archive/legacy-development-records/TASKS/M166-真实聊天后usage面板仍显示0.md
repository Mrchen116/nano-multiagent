# M166 Tasks - 修复真实聊天后 usage 面板仍显示 0

- Milestone: M166
- Title: 修复真实聊天后 usage 面板仍显示 0
- Goal: 修复聊天工作区中 This chat / Workspace total usage 面板在真实多轮聊天后仍显示 0 turns / 0 tokens 的缺陷，确保真实 usage 数据在加载、刷新、切换会话与页面重进后都能正确展示。
- execution_mode: manual
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M166`
- branch: `milestone/M166`
- test_command: `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx && npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend run build`
- allowed_scope:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/TASKS/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/PROGRESS/**`
- forbidden_scope:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/data/dev-tasks.json`
  - 新建额外 worktree
  - 与 M166 无关的后端/CLI/文档大范围改动
- prevention_rules:
  - 先读清现有 usage 加载/刷新语义，再做最小修复。
  - 不改 usage 聚合语义，只修复真实页面刷新/重进仍读到 0 的接线缺口。
  - conversation/workspace totals 继续只消费各自 scope，不能把 agent rows 混入主卡片。
  - 必须覆盖真实路径相近场景：事件刷新、切换会话、页面重进。
  - 只在 M166 worktree 中工作，不创建嵌套 worktree。

## Roadpoints

### R1 锁定真实页面 usage 刷新/重进回归
- Status: DONE
- Acceptance:
  - 新增前端回归测试锁定三类真实缺口：relay.report 后刷新、切换会话后 workspace total 刷新、页面离开再进入后不继续卡 0。
  - 证明 usage 面板不是聚合错，而是查询复用/挂载刷新路径未覆盖。
- Tests Plan:
  - component: `src/features/chat/chat-workspace-page.test.ts`
- Evidence:
  - 新增用例：
    - `refreshes visible usage after relay reports deliver real metrics`
    - `refetches workspace totals when switching chats under the same owner`
    - `refetches usage when re-entering the chat so cached zeros do not stick`
- DoD:
  - 三条真实路径都被测试锁定。
  - 红测能表达“初始 0 -> 后续真实值”的回归现象。

### R2 修复 usage 查询在切换/重进下的 stale 0 复用
- Status: DONE
- Acceptance:
  - conversation usage 在重新进入会话时总会重新拉取。
  - workspace usage 在会话切换与页面重进时总会重新拉取，不再沿用同 owner 下的 stale 0 结果。
  - 事件刷新后真实 usage 非 0 能落到页面。
- Tests Plan:
  - component: `src/features/chat/chat-workspace-page.test.ts`
  - build: `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend run build`
- Evidence:
  - `chat-workspace-page.tsx`：
    - conversation usage query 增加 `refetchOnMount: "always"`
    - workspace usage query key 绑定 `conversationId`，并增加 `refetchOnMount: "always"`
- DoD:
  - This chat / Workspace total 不再因为缓存复用而停在 0。
  - 现有 usage 语义与 per-agent 面板保持不变。

## Commit Result
- C1 `6cffdc4` `fix(M166): refresh usage panels on chat remount and navigation`
- C2 docs / verification / build artifact 同步在 milestone 收口提交中补齐。
- 最终准确 commit hashes 以 `git log` 与本 milestone 汇报为准。
