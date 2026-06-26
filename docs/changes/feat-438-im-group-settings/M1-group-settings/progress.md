# feat-438-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

### R1 — 后端：add_participants + POST /participants + ActorPayload.user_id

- Context: 群成员管理需要一个「添加 agent」端点（后端原本只有 PATCH/DELETE participant/DELETE conversation），且前端移除路径需要 participant 的 user_id（CRITICAL-1：agent participant 的 `id` 是 agent_id，不是删除端点用的 user_id）。
- Decision:
  - `ConversationRepository.add_participants(conversation_id, references)`：复用 `_resolve_participant_user_row` 做 agent→user 解析 + 幂等 INSERT membership；**不**调用 config 快照逻辑，因此不重冻 `config_profile_version`（决策 3）。
  - `WebIMService.add_participants` 透传。
  - 新路由 `POST /im/v1/conversations/{id}/participants`：先 `_load_owner_scoped_conversation`（跨租户 404），再 resolve + add；空列表 / resolve 失败由 repo raise ValueError → route 映射 400（决策 3 要求 400 而非 422，故不在 Pydantic model 上做 min_length）。
  - `ActorPayload` 加 `user_id`，`to_conversation_response` 透传域 `Actor.user_id`（决策 5）。域 `Actor` 本就有 `user_id`，纯透传。
  - 抽 `_actor_payloads_to_references` 供 create / add 共用，避免平行实现（§0.1）。
- Rationale: membership 写入与 resolve 已存在于 create 路径，抽成可复用方法符合「复用现有架构」；不碰 relay——relay 在发消息时按 participants 动态建（design 现状分析已证）。
- Evidence:
  - Tests: `tests/unit/IM/test_conversation_add_participants.py` 13 passed（repo 全分支 + route 200/幂等/400 空/400 resolve 失败/404 跨租户 + user_id 透传 + CRITICAL-1 移除用 user_id 真删）。`tests/unit/IM/ + tests/im_service/` 406 passed / 1 skip。
  - Entry: HTTP route 测试经 TestClient 真发请求（非 mock 入口）：POST 加 agent → 200 且 participants 含该 agent；DELETE /participants/{user_id} → 204 且成员消失。
  - Frontend State Matrix: N/A
  - Browser QA: N/A（后端 roadpoint，UI 走查在 R5）
  - E2E/Regression: `test_remove_participant_by_user_id_removes_agent` 锚定 CRITICAL-1（防止前端误传 agent_id 导致删不掉的回归）。
  - Visual/Interaction: N/A
- Rollback: 回退到 R1 C1 commit（删端点 + add_participants + user_id 字段即回到现状）。
- Commits: C1=test(R1 红测), C2=feat(R1 实现), C3=docs(本段)
- Next: R2 前端 chat-api 4 调用 + Actor.user_id。
