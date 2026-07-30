# M95 - IM Web IM API 扩展

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

- Milestone: M95 / IM Web IM API 扩展
- Branch: `milestone/M95`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M95`
- Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M95 && PYTHONPATH=src pytest -q tests/im_service`
- Prevention Rules:
  1. 先跑真实基线测试，再开始编码。
  2. 大范围修改后复查负向断言与 import path，避免旧新结构并存。
  3. 保持单一 canonical 结构；若保留兼容层，必须最小且有理由。
  4. TASKS/PROGRESS 必须注明已先阅读顶层 SPEC 与 IM 相关 SPEC。

## R1 owner 隔离 + 会话 PATCH + 列表排序
- Status: TODO
- Acceptance:
  - `PATCH /im/v1/conversations/{id}` 支持 `is_pinned` / `is_muted` / `title`。
  - 会话读写按 `owner_id` 隔离，禁止混 owner 创建或跨 owner 读写。
  - 会话列表可稳定返回 `type/unread_count/last_message_at`，并优先展示 pinned + 最近活跃。
- Tests Plan:
  - contract: 覆盖 PATCH 契约与 owner 冲突语义。
  - integration: 覆盖 mixed-owner 创建失败、PATCH 成功、列表排序/字段稳定。
  - e2e: 复用聊天链路，确认扩展后主路径不退化。
- Expected Tests:
  - `tests/im_service/contract/test_chat_flow_contract.py`
  - `tests/im_service/integration/test_users_conversations_api.py`
  - `tests/im_service/e2e/test_human_chat_sse_e2e.py`
- DoD:
  - `PYTHONPATH=src pytest -q tests/im_service` 全绿。
  - PROGRESS 记录 owner 隔离与 PATCH 语义、证据、提交哈希。

## R2 消息扩展 + 历史分页
- Status: TODO
- Acceptance:
  - Message 支持 `sender_type(user/agent/system)` 与 `attachments[]`。
  - `GET /im/v1/conversations/{id}/messages` 支持分页历史读取。
  - 未读数与 `last_message_at` 在消息写入后稳定更新。
- Tests Plan:
  - contract: 覆盖消息字段与分页响应契约。
  - integration: 覆盖 user/agent/system 消息、附件透传、分页顺序、未读/last_message_at 更新。
  - e2e: 复用 SSE 重连链路，确认新字段不破坏事件流。
- Expected Tests:
  - `tests/im_service/contract/test_messages_contract.py`
  - `tests/im_service/integration/test_messages_api.py`
  - `tests/im_service/e2e/test_human_chat_sse_e2e.py`
- DoD:
  - `PYTHONPATH=src pytest -q tests/im_service` 全绿。
  - PROGRESS 记录 sender_type/attachments/pagination 语义、证据、提交哈希。

## R3 收口 canonical 结构 + 文档/看板完成态
- Status: TODO
- Acceptance:
  - 实现与测试统一走 `api/application/domain/infra` canonical 路径。
  - 负向复查确认没有遗留并行结构或 stale import。
  - TASKS/PROGRESS 与共享任务板同步完成态。
- Tests Plan:
  - full: `tests/im_service`。
  - selective grep: 复查 M95 相关字段和旧路径残留。
- Expected Tests:
  - `tests/im_service/**/*`
- DoD:
  - 本地测试全绿。
  - 里程碑完成记录、提交、merge、board update、worktree cleanup 完成。
