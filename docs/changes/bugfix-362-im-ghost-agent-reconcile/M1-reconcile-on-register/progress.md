# M1: reconcile-on-register — Progress

## RP1: DB 迁移 (db.py)
- `_migrate_agent_profile_tables` 内追加 `is_stale INTEGER NOT NULL DEFAULT 0` 和 `staled_at TEXT`（幂等 ALTER TABLE + PRAGMA 探测）。

## RP2: 域模型字段 (domain/models.py)
- `AgentProfile.is_stale: bool = False`
- `Actor.is_stale: bool | None = None`（仅 agent 类型填充）

## RP3: Repository 层 (repositories.py)
- `AgentProfileRepository.mark_stale_for_node(*, node_id, advertised_agent_ids) -> int`：空列表全标、非空列表 `NOT IN` 参数化 SQL、只动 `is_stale=0` 的行、返回新标 stale 行数。
- `upsert_profile` ON CONFLICT 路径追加 `is_stale=0, staled_at=NULL`（复活契约）。
- `list_runtime_selectable_profiles` / `list_runtime_selectable_profiles_for_owner`：WHERE 追加 `ap.is_stale = 0`。
- `_row_to_profile`：读取 `is_stale` 字段（兼容旧行无该列时用 keys() 检测 + 默认 False）。
- 会话 participants 查询 LEFT JOIN `agent_profiles` 带 `is_stale`；`_actor_from_user_row` 填入 `Actor.is_stale`。

## RP4: WS handler (gateway_handler.py)
- `_handle_register` 的 upsert 循环后、`commit()` 前追加 `profile_repository.mark_stale_for_node(node_id, agents)`。同一事务边界，保证对账原子性。

## RP5: API schema (web_im.py)
- `ActorPayload.is_stale: bool | None = None`（可选字段，向后兼容）。
- `to_conversation_response`：agent 参与者的 `is_stale=True` 时透出给前端，其余填 None。

## RP6: 前端 (TypeScript)
- `ImActorRef.is_stale?: boolean`（im-chat-api.ts）；`parseActorRef` 解析该字段。
- `toMentionCandidates`：过滤 `participant.is_stale === true`（legacy v1 picker）。
- `Actor.is_stale?: boolean | null`（v2/chat-types.ts）。
- `listMentionCandidates`：allowed set 排除 stale participants（v2/chat-api.ts）。
- 群成员头部渲染：stale agent 加 `opacity-40` + tooltip（v2/components/message-pane.tsx）。

## Test Results
```
tests/im_service/unit/test_agent_profile_stale.py  9 passed
tests/im_service/integration/test_ghost_agent_reconcile.py  3 passed
tests/im_service/unit/test_owner_scoped_repositories.py  5 passed
```

## Evidence

前端视觉自测：在 "Stale Agent Demo Group" 群组中，Gateway 重新注册时只上报 `Arch` 而不上报 `ArchA`，触发 `mark_stale_for_node`。前端 header 参与者区域显示 `架构 · Q`，其中 `Q`（ArchA）以 `opacity-40` 渲染（明显偏淡），hover 显示 tooltip "Offline — agent no longer advertised by its Gateway"。

截图：`ACCEPTANCE/bugfix-362/r0-stale-grayout-1440.png`（1440px 视口，header 区域裁切）

## Commits
- C1 `test`: 红测（mark_stale_for_node / stale 过滤 / 对账事务 / ActorPayload.is_stale）
- C2 `fix`: 完整实现（db 迁移 + repository + handler + API + 前端）
- C3 `docs`: 本文档 + tasks.md + 视觉自测截图
