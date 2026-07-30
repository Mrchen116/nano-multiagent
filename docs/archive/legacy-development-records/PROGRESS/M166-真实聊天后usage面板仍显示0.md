# M166 Progress - 修复真实聊天后 usage 面板仍显示 0

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M166`
- 已确认 branch：`milestone/M166`
- 已确认约束：不修改 `data/dev-tasks.json`；不创建额外 worktree；只在 M166 manual worktree 内工作。
- 已先阅读：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/api/routes/metrics.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/ws/gateway_handler.py`
- 当前结论：后端 usage 真值链路已存在，M166 缺口集中在前端 query cache/refetch 语义，尤其是相同 owner 下 workspace usage query key 未随会话变化，且页面重进时仍可能复用 stale 0。

## 执行策略
1. 先用前端回归测试锁定真实路径：事件刷新、切换会话、页面重进。
2. 最小修复只改 chat workspace usage query 的 refetch/key 语义，不碰后端 usage 聚合逻辑。
3. 跑 focused frontend tests + build，记录证据后收口。

### R1 锁定真实页面 usage 刷新/重进回归
- Context:
  - 现有测试已覆盖 usage view 基础展示，但未锁定“先看到 0，随后真实 usage 到达后仍不更新”的缓存复用路径。
  - App QueryClient 默认 `staleTime: 5_000`，会让同 owner 的 workspace usage 在会话切换与页面重进时继续复用旧数据。
- Decision:
  - 在 `chat-workspace-page.test.ts` 新增 3 个 focused 回归用例，覆盖 relay.report 刷新、切换会话、离开并重新进入页面。
  - 为导航测试补一个 persistent QueryClient 渲染 helper，模拟真实路由与缓存生命周期。
- Rationale:
  - 问题不是 usage 计算公式，而是查询何时重新拉取真实 usage。
  - 必须让测试表达“初始 0 -> 后续非 0”的真实产品缺陷，否则很容易被现有 happy-path case 漏掉。
- Evidence:
  - 新增用例：
    - `refreshes visible usage after relay reports deliver real metrics`
    - `refetches workspace totals when switching chats under the same owner`
    - `refetches usage when re-entering the chat so cached zeros do not stick`
- Rollback:
  - 若新增导航级测试造成不稳定，可保留 relay.report 刷新用例并收缩 helper；但会降低对真实重进路径的保护。
- Commits: `6cffdc4` `fix(M166): refresh usage panels on chat remount and navigation`；docs 收口提交待创建。
- Next: 进入 query key / refetch 语义修复。

### R2 修复 usage 查询在切换/重进下的 stale 0 复用
- Context:
  - conversation usage query key 绑定 conversationId，但默认 mount 时可能直接消费 5 秒 stale window 内缓存。
  - workspace usage query key 只绑定 ownerId；同 owner 内切会话时不会形成新 key，也可能不触发重新拉取，导致 UI 继续显示旧的 0。
- Decision:
  - `conversationUsageQuery` 增加 `refetchOnMount: "always"`。
  - `workspaceUsageQuery` query key 扩展为 `[..., ownerId, conversationId ?? "workspace-home"]`，同时增加 `refetchOnMount: "always"`。
- Rationale:
  - 真实页面重进必须优先拿最新 usage，而不是继续信任几秒内缓存的 0。
  - workspace total 虽按 owner 聚合取数，但 UI 生命周期是“进入某个会话工作区”触发；将 conversationId 纳入 key 可以让同 owner 下不同 chat workspace 实例独立重新拉取。
- Evidence:
  - focused test：`npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts` -> green
- Rollback:
  - 若后续认为 workspace query key 不应带 conversationId，可保留 `refetchOnMount: "always"` 并改为显式 invalidate；但当前最小修复已足够且更直接。
- Commits: `6cffdc4` `fix(M166): refresh usage panels on chat remount and navigation`；docs 收口提交待创建。
- Next: 跑 focused verification 与 build 收口。

## 验证记录
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts` -> `18 passed`
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx` -> `31 passed`
- `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M166/src/IM/frontend run build` -> `vite build` 通过，产出 `dist/assets/index-Dsb-jMHm.js` 与 `dist/assets/index-CASU4UjZ.css`

## 当前结论
- 已定位并修复 M166 根因：前端 query cache/refetch 语义导致真实 usage 在切换/重进后继续显示旧的 0，而不是后端 usage 指标缺失。
- 当前 focused tests 与 frontend build 已通过，可进入提交与 milestone 收口。
