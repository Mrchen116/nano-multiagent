# M234 Progress: 群聊删除（解散/退出）

## Plan Commit
- Branch: milestone/M234
- Worktree: /Users/czj/Repos/nano-multiagent/.worktrees/M234

---

## R1 后端：creator_id 迁移 + 解散/退出 API

- Context: conversations 表无 creator_id 字段；无 DELETE 端点；权限校验需在 service 层做。
- Decision:
  - `infra/db.py`：`_SCHEMA_SQL` + `_migrate_conversations_metadata` 增加 `creator_id TEXT NOT NULL DEFAULT ''`，旧数据 backfill 为第一个参与者
  - `ConversationRepository.create_conversation`：接受可选 `creator_id` 参数，默认取第一个参与者
  - `ConversationRepository.delete_conversation(conversation_id, requester_id)`：service 层比对 `creator_id`，不匹配 raise `PermissionError` → HTTP 403
  - `ConversationRepository.remove_participant(conversation_id, user_id)`：DELETE participant 行
  - 域模型 `Conversation` 增加 `creator_id: str` 字段
  - `web_im.py`：`DELETE /im/v1/conversations/{id}`（携带 `requester_id` body）+ `DELETE /im/v1/conversations/{id}/participants/{user_id}`
  - `ConversationResponse` 增加 `creator_id` 字段（前端用于判断是否显示解散按钮）
- Rationale: 权限校验在 service 层而非仅依赖前端隐藏，符合 prevention_rules；CASCADE 删除通过 SQLite 外键保证。
- Evidence:
  - Tests: `python -m pytest tests/unit/IM/ -x -q` → 6 passed
  - Entry: `cd src/IM/frontend && npm run build` → success
- Rollback: plan commit (89110ba)
- Commits: C1=3a061a0, C2=4e51bd3, C3=见下
- Next: R2 前端

---

## R2 前端：退出/解散操作入口 + 二次确认弹窗

- Context: MessagePane 无群聊操作入口；需乐观更新移除 conversation + 跳回首页。
- Decision:
  - `im-chat-api.ts`：新增 `deleteConversation({ conversationId, requesterId })`、`leaveConversation({ conversationId, userId })`
  - `mock-chat-api.ts`：对应 mock 实现（从本地列表移除）
  - `chat-api.ts`：导出上述两个函数
  - `types.ts`：`ConversationDetail` 增加 `creator_id?: string`
  - `message-pane.tsx`：
    - 新增 props：`onLeaveConversation`、`onDeleteConversation`、`isGroupCreator`
    - section 加 `relative`，方便 dialog 绝对定位
    - group 会话头部显示"退出群聊"按钮；仅 creator 显示"解散群聊"（rose 色警示）
    - 点击后出现二次确认 dialog（含取消/确认）
  - `chat-workspace-page.tsx`：
    - 导入 `deleteConversation`、`leaveConversation`
    - 新增 `leaveConversationMutation`、`deleteConversationMutation`
    - `removeConversationFromCache` 函数：乐观更新列表 + removeQueries + navigate
    - 计算 `isGroupCreator = detail?.creator_id === selfUserId`
    - 两处 MessagePane 均传 `onLeaveConversation`、`onDeleteConversation`、`isGroupCreator`
- Rationale: 乐观更新让 UI 即时响应，服务端仍做权限强校验；二次确认弹窗防误操作。
- Evidence:
  - Tests: `python -m pytest tests/unit/IM/ -x -q` → 6 passed; frontend `npm test` → 96 passed
  - Entry: `npm run build` → built in ~1s, no errors
- Rollback: R1 C3
- Commits: C1=28824d9, C2=2ad682d, C3=见本次提交
- Next: 合并到 main
