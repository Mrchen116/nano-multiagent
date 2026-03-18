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
  - Tests: `cd src/IM/frontend && npx vitest run src/features/chat/chat-workspace-page.test.ts`
  - Entry: relay.processing payload 含 `sender_display_name=Alpha, agent_id=A, node_id=my-macbook` 时，合成消息显示 Alpha/A，不再显示 my-macbook。
- Rollback:
  - 回退到 R1 的 C1 或本文件创建前的计划提交。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 跑完整 build/vitest 门禁；若主线 vitest 仍有既有失败，仅记录不顺手扩修。
