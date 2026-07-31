# M94 - IM 分层架构迁移

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

## Baseline
- Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M94 && PYTHONPATH=src pytest -q tests/im_service`
- Result: 23 passed
- Notes:
  - 当前 IM 后端仍是扁平结构：`app.py` 同时承载 DTO、路由、装配；`models.py` 与 `repositories.py` 在顶层。
  - 现有测试全绿，迁移必须以“结构收敛、不改外部 HTTP 契约”为第一目标。

### R1 规划与分层骨架落位
- Context: M94 基线全绿，但 `src/IM/app.py` 同时承载 DTO、路由、SSE、仓储装配；`models.py/repositories.py/sse.py` 仍是扁平结构，与 IM-SPEC §9 不符。本轮不改 HTTP 入口语义，只重构内部层级并把新增 domain 字段一并落位。
- Decision: 建立 `api/routes`、`application`、`domain`、`infra`、`ws` 五层目录；`app.py` 仅负责 lifespan 与 router 装配；用户/会话/消息/SSE 路由拆到 `api/routes/*`；仓储实现迁到 `infra/repositories.py`；领域模型迁到 `domain/models.py`；`ws/gateway_handler.py` 先建立 canonical 占位。
- Rationale: 先完成 canonical 分层，再让旧路径退化为最小兼容 alias，符合“单一主结构”与后续 M95-M97 继续扩展的要求；同时复用现有 API contract，降低迁移面。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M94 && PYTHONPATH=src pytest -q tests/im_service`
  - Entry: `create_app()` 已从 `IM.api.routes.users/web_im/messages` 装配路由，消息与 SSE 入口继续通过 `/im/v1/conversations/*` 对外提供。
- Rollback: `33ab421`（R1 C1）
- Commits: C1=33ab421, C2=bf33f58, C3=
- Next: 补文档提交，并继续清理 legacy 顶层实现路径，只保留必要的最小兼容入口。

### R2 domain models 扩展并对齐 IM-SPEC
- Context: M94 exit criteria 要求 `User(owner_id)`、`AgentProfile(profile_version)`、`Conversation(type/owner_id/is_pinned/is_muted/unread_count/last_message_at)`、`Message(sender_type/attachments)`、`NodeStatus`、`RelayTask` 落入 domain。当前实现只有 `User/Conversation/Message/ConversationEvent` 的简化版本。
- Decision: 在 `domain/models.py` 引入完整 dataclass 集合；同步扩展 SQLite schema 与迁移逻辑，给 users/conversations/messages 增加 owner_id、type、pin/mute、unread、last_message_at、sender_type、attachments_json 等字段；现有 API 响应输出新字段，默认语义保持稳定（user sender / 空 attachments / 未读为 0）。
- Rationale: M94 主要目标是为后续 IM 能力扩展打基础，字段先在 domain 与 infra 层建好，外部契约保持向后兼容，后续 M95/M96/M97 再逐步消化真实业务语义。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M94 && PYTHONPATH=src pytest -q tests/im_service`
  - Entry: 创建用户/会话/消息后，HTTP 响应已包含 `owner_id/type/is_pinned/is_muted/unread_count/last_message_at/sender_type/attachments`，SSE 事件 payload 继续稳定返回。
- Rollback: `33ab421`（R1 C1）
- Commits: C1=33ab421, C2=bf33f58, C3=
- Next: 清理 `src/IM/models.py`、`src/IM/sse.py` 等 legacy 实现残留，并把测试导入收口到 canonical path。

### R3 清理旧路径并收口 canonical imports
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
