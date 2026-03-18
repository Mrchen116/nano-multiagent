# M234 群聊删除：解散群聊（群主）+ 退出群聊（成员）

## Roadpoints

### R1 后端：conversations.creator_id 迁移 + 解散/退出 API

**Acceptance**
1. conversations 表存在 creator_id 字段（新建时自动记录第一个 participant，旧数据 migration 兜底）
2. DELETE /conversations/{id} 仅 creator 可操作，返回 204，级联删除 messages/participants
3. DELETE /conversations/{id} 非 creator 调用返回 403
4. DELETE /conversations/{id}/participants/{user_id} 成功返回 204，其他人不受影响
5. 被删参与者再次调用返回 404（或已不在对话中）

**Tests Plan**
- unit：`tests/unit/IM/` 下新增 `test_conversation_delete.py`
  - ConversationRepository.delete_conversation：happy path + permission check
  - ConversationRepository.remove_participant：happy path + not found
- contract：验证 API 返回状态码结构（已在 integration 测试中覆盖）
- integration：HTTP 层端到端（使用 TestClient + tmp db）
- e2e：不额外跑；integration 已覆盖入口链路

**Expected Tests**
```
tests/unit/IM/test_conversation_delete.py
  test_delete_conversation_by_creator_cascades_data
  test_delete_conversation_by_non_creator_raises_permission_error
  test_remove_participant_success
  test_remove_participant_not_in_conversation_raises
```

**DoD**
- test_command 全绿（tests/unit/IM/ + npm run build）
- C1/C2/C3 齐全
- PROGRESS 更新

**状态**: DONE

---

### R2 前端：退出/解散操作入口 + 二次确认弹窗

**Acceptance**
1. 群聊详情面板有"退出群聊"按钮（所有成员）
2. 群主专属显示"解散群聊"按钮
3. 任一操作前出现二次确认弹窗（含 confirm/cancel）
4. 操作成功后该群聊从列表消失，若当前在该群聊页则跳转回首页
5. 前端乐观更新：操作成功后立即从本地 conversations 列表移除该 conversation

**Tests Plan**
- unit：前端已有 chat-api.test.ts，新增对 deleteConversation / leaveConversation 的单测
- contract/integration/e2e：通过 build 门禁保证；UI 行为由人工 acceptance 覆盖

**Expected Tests**
```
src/IM/frontend/src/features/chat/im-chat-api.test.ts（扩展）
  test deleteConversation calls DELETE /im/v1/conversations/{id}
  test leaveConversation calls DELETE /im/v1/conversations/{id}/participants/{userId}
```

**DoD**
- npm run build 成功
- test_command 全绿
- C1/C2/C3 齐全
- PROGRESS 更新

**状态**: DONE
