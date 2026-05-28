# M1: reconcile-on-register — Tasks

## R1: DB 迁移 — is_stale / staled_at 列
- [x] `src/IM/infra/db.py`: `_migrate_agent_profile_tables` 追加 `ALTER TABLE agent_profiles ADD COLUMN is_stale INTEGER NOT NULL DEFAULT 0`（PRAGMA 探测幂等）
- [x] `src/IM/infra/db.py`: 同上追加 `ALTER TABLE agent_profiles ADD COLUMN staled_at TEXT`

Status: DONE

## R2: 域模型字段
- [x] `src/IM/domain/models.py`: `AgentProfile` 加 `is_stale: bool = False`
- [x] `src/IM/domain/models.py`: `Actor` 加 `is_stale: bool | None = None`

Status: DONE

## R3: Repository 层
- [x] `src/IM/infra/repositories.py`: 新增 `mark_stale_for_node(*, node_id, advertised_agent_ids) -> int`（空列表全标 / 非空 NOT IN 参数化 / 只动 is_stale=0 行）
- [x] `src/IM/infra/repositories.py`: `upsert_profile` ON CONFLICT 追加 `is_stale=0, staled_at=NULL`（复活路径）
- [x] `src/IM/infra/repositories.py`: `list_runtime_selectable_profiles` WHERE 追加 `ap.is_stale = 0`
- [x] `src/IM/infra/repositories.py`: `list_runtime_selectable_profiles_for_owner` WHERE 追加 `ap.is_stale = 0`
- [x] `src/IM/infra/repositories.py`: `_row_to_profile` 读取 `is_stale`（keys() 探测兼容旧行）
- [x] `src/IM/infra/repositories.py`: 会话 participants 查询 LEFT JOIN `agent_profiles` 带 `is_stale`；`_actor_from_user_row` 填入 `Actor.is_stale`
- [x] SELECT 列表更新：`list_profiles` / `get_profile` 均加 `is_stale`

Status: DONE

## R4: WS handler 对账
- [x] `src/IM/ws/gateway_handler.py`: `_handle_register` upsert 循环后、`commit()` 前调 `profile_repository.mark_stale_for_node(node_id, agents)`（同一事务）

Status: DONE

## R5: API schema
- [x] `src/IM/api/routes/web_im.py`: `ActorPayload` 加 `is_stale: bool | None = None`
- [x] `src/IM/api/routes/web_im.py`: `to_conversation_response` 对 agent 参与者填 `is_stale`

Status: DONE

## R6: 前端
- [x] `src/IM/frontend/src/features/chat/im-chat-api.ts`: `ImActorRef` 加 `is_stale?: boolean`；`parseActorRef` 解析该字段
- [x] `src/IM/frontend/src/features/chat/im-chat-api.ts`: `toMentionCandidates` 过滤 `participant.is_stale === true`（legacy v1 picker）
- [x] `src/IM/frontend/src/features/chat/v2/chat-types.ts`: `Actor` 加 `is_stale?: boolean | null`
- [x] `src/IM/frontend/src/features/chat/v2/chat-api.ts`: `listMentionCandidates` allowed set 排除 `is_stale` 参与者
- [x] `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`: stale agent 群成员渲染加 `opacity-40` + tooltip

Status: DONE
