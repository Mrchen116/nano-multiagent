# M242 群聊 sender 显示修复进展

### R1 修正 relay synthetic message 的 sender 身份映射
- Context:
  - 群聊 relay/SSE synthetic agent message 当前把 `node_id` 写入 `sender_name`，导致 UI 显示 `my-macbook`。
  - `MessagePane` 已优先显示 `sender_display_name -> sender_name -> sender_user_id`，问题在上游映射。
  - 本 Milestone 不改 IM 后端与 Gateway，只修前端 sender 映射和相关回归。
- Decision:
  - 在 `chat-workspace-page.tsx` 增加统一 relay sender identity 解析：优先 `sender_display_name/display_name/agent_display_name`，再回退 `agent_id`，最后才回退 `node_id/Agent`。
  - synthetic relay agent message 同时保留 `sender_display_name` 与 `sender_name`，让群聊 UI 与刷新后的缓存/历史合并路径使用同一展示优先级。
- Rationale:
  - 根因已明确在 relay synthetic 映射层；在此层修复成本最低，也能复用现有 `MessagePane` sender label 展示链。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run build 2>&1 | tail -10 && npx vitest run 2>&1 | grep "FAIL\|×"`
  - Entry: relay.processing payload 含 `sender_display_name=Alpha, agent_id=A, node_id=my-macbook` 时，合成消息显示 Alpha/A，不再显示 my-macbook。
  - Baseline note: 完整 vitest 仍仅剩主线既有 5 个 `src/features/settings/agents/agents-list-mobile.test.tsx` 失败；M242 相关 `src/features/chat/chat-workspace-page.test.ts` 全绿。
- Rollback:
  - `379cac8` 或 `53dbdc6`
- Commits: C1=`379cac8`, C2=`8593325`, C3=<pending>
- Next:
  - 进入里程碑集成：rebase main、合并回 main、更新 dev-tasks、清理 worktree/branch。
