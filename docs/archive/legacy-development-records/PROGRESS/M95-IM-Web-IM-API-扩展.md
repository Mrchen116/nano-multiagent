# M95 - IM Web IM API 扩展

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

## Baseline
- Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M95 && PYTHONPATH=src pytest -q tests/im_service`
- Result: 24 passed
- Notes:
  - 当前已具备 M94 的分层基础与基础字段，但尚未实现会话 PATCH、owner 隔离校验、消息 sender_type/attachments 写入、历史分页，以及未读数更新语义。
  - M95 将在不突破 IM 模块边界的前提下，仅扩展 Web IM 会话/消息 API 与测试。

## R1 owner 隔离 + 会话 PATCH + 列表排序
- Context: M94 已有 conversation metadata 字段，但还没有 `GET/PATCH /im/v1/conversations/{id}`，列表接口仍是裸数组，也没有对会话列表排序与 owner 语义做明确测试。
- Decision: 在 `src/IM/api/routes/web_im.py` 增加详情与 PATCH 路由；在 `src/IM/application/web_im_service.py` / `src/IM/infra/repositories.py` 增加 `get_conversation`、`update_conversation`；会话列表改为 envelope `{items:[...]}`，按 `is_pinned DESC, COALESCE(last_message_at, created_at) DESC` 排序，并把 mixed-owner 对话显式标记为独立会话 owner scope。
- Rationale: Web IM 端点要对齐 IM-SPEC §5，且会话列表后续还要承载更多元数据；先把 canonical API 结构和列表稳定性收口，避免后续在 M99/M103 再返工。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M95 && PYTHONPATH=src pytest -q tests/im_service`
  - Entry:
    - `GET /im/v1/conversations/{id}` 返回单会话详情。
    - `PATCH /im/v1/conversations/{id}` 支持 `title/is_pinned/is_muted`。
    - `GET /im/v1/conversations` 返回 `{items:[...]}`，且 pinned 与最近活跃排序可测。
- Rollback: uncommitted
- Commits: C1=, C2=, C3=
- Next: 扩展消息 rich fields、分页与 unread/last_message_at 写入语义。

## R2 消息扩展 + 历史分页
- Context: M94 仅支持基础文本消息，`sender_type` 固定为 user、`attachments` 固定空数组，历史读取没有分页 envelope，也没有围绕 unread_count / last_message_at 的 contract。
- Decision: 在 `src/IM/domain/models.py` 引入 `Attachment` dataclass；消息创建 API 接受 `sender_type(user/agent/system)` 与 `attachments[]`；SQLite 仓储统一以 JSON 持久化附件；`GET /im/v1/conversations/{id}/messages` 返回 `{items, next_before_message_id}`，支持 `limit` 与 `before_message_id` 游标分页；每次写消息时递增会话 `unread_count` 并刷新 `last_message_at`。
- Rationale: 这些字段和分页语义是 M95 exit criteria 的核心，必须在 domain/application/api/infra 同时收口，避免只做 DTO 表面兼容；同时保持 SSE payload 与历史 API 语义一致，减少前端分叉处理。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M95 && PYTHONPATH=src pytest -q tests/im_service`
  - Entry:
    - `POST /im/v1/conversations/{id}/messages` 支持 `sender_type` 与附件透传。
    - `GET /im/v1/conversations/{id}/messages?limit=...&before_message_id=...` 返回分页历史。
    - SSE `message.sent/message.delivered` 事件 payload 含 `sender_type` 与 `attachments`。
- Rollback: uncommitted
- Commits: C1=, C2=, C3=
- Next: 做负向复查、记录 canonical 结构结论，并准备提交/merge/board update。

## R3 收口 canonical 结构 + 文档/看板完成态
- Context: M95 实现涉及 API 响应 envelope 与 repository 语义扩展，必须确认未把测试或实现重新引回 legacy 顶层模块，也要把任务记录补齐到 worker 流程要求。
- Decision: 复查 `tests/im_service` 中无 `src/IM/models.py|src/IM/repositories.py|src/IM/sse.py` 旧路径命中；新增 `TASKS/M95-IM-Web-IM-API-扩展.md` 与本进度文档，并记录已先读 SPEC；M95 范围仅限 IM 模块与对应测试。
- Rationale: 满足 prevention rule 2/3，避免分层迁移后出现“canonical 实现已改、测试仍依赖 legacy alias”的假完成；同时给后续 merge/board update 提供可追溯证据。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M95 && PYTHONPATH=src pytest -q tests/im_service` → `28 passed`
  - Entry:
    - `tests/im_service` 中对 `sender_type/attachments/is_pinned/is_muted/unread_count/last_message_at/next_before_message_id` 共 42 处断言覆盖。
    - `tests/im_service` 中无 `src/IM/models.py|src/IM/repositories.py|src/IM/sse.py` 旧路径命中。
- Rollback: uncommitted
- Commits: C1=, C2=, C3=
- Next: 提交改动，更新 `data/dev-tasks.json`，合并 `milestone/M95` 到本地 `main`，并按要求清理 worktree。
