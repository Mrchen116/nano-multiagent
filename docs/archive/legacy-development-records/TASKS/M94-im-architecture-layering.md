# M94 - IM 分层架构迁移

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

- Milestone: M94 / IM 分层架构迁移
- Branch: `milestone/M94`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M94`
- Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M94 && PYTHONPATH=src pytest -q tests/im_service`
- Prevention Rules:
  1. 先跑真实基线测试，再开始迁移。
  2. 大范围移动后回查负向断言与 import path，避免旧新结构并存。
  3. 保持唯一 canonical 结构，兼容层必须最小且有理由。
  4. TASKS/PROGRESS 必须注明已先阅读 SPEC 与模块 SPEC。

## R1 规划与分层骨架落位
- Status: TODO
- Acceptance:
  - `src/IM/api/routes/`、`src/IM/application/`、`src/IM/domain/`、`src/IM/infra/`、`src/IM/ws/` 目录存在。
  - 现有 `models/repositories/app/sse` 职责映射到新层级。
  - app 入口改为从分层模块装配，而不是继续承载全部路由与 DTO。
  - 现有 IM 路由入口保持可用。
- Tests Plan:
  - unit: 保留并补充 app factory / repository 导入路径测试，验证新结构可被装配。
  - contract: 复用现有 API contract，确保迁移不改变外部 HTTP 契约。
  - integration: 复用 users/conversations/messages API 测试，验证真实入口不回退。
  - e2e: 复用 SSE e2e，验证事件流入口仍可用。
- Expected Tests:
  - `tests/im_service/unit/test_app_factory.py`
  - `tests/im_service/integration/test_users_conversations_api.py`
  - `tests/im_service/integration/test_messages_api.py`
  - `tests/im_service/e2e/test_human_chat_sse_e2e.py`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 写明层级映射、证据和提交哈希。

## R2 domain models 扩展并对齐 IM-SPEC
- Status: TODO
- Acceptance:
  - `domain/models.py` 定义 `User`、`AgentProfile`、`Conversation`、`Message`、`NodeStatus`、`RelayTask`。
  - `User` 含 `owner_id`。
  - `AgentProfile` 含 `profile_version`。
  - `Conversation` 含 `type/owner_id/is_pinned/is_muted/unread_count/last_message_at`。
  - `Message` 含 `sender_type/attachments`。
- Tests Plan:
  - unit: 为仓储 roundtrip 与 schema 初始化补字段断言。
  - contract: 为 users/conversations/messages 返回结构补充新字段契约。
  - integration: 真实 API 验证字段可写入/读出，默认值稳定。
  - e2e: 不新增；复用现有 SSE e2e 即可覆盖消息输出未退化，字段扩展不需要额外 UI 入口。
- Expected Tests:
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/unit/test_db_init.py`
  - `tests/im_service/contract/test_messages_contract.py`
  - `tests/im_service/integration/test_users_conversations_api.py`
  - `tests/im_service/integration/test_messages_api.py`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 写明新增字段的默认语义与边界。

## R3 清理旧路径并收口 canonical imports
- Status: TODO
- Acceptance:
  - `src/IM/models.py`、`src/IM/repositories.py`、`src/IM/sse.py` 不再作为实现主路径。
  - 路由只位于 `api/routes/`。
  - 仓储只位于 `infra/`，领域模型只位于 `domain/`。
  - 测试与实现使用 canonical imports，且无无理由并行结构。
- Tests Plan:
  - unit: 补充结构/导入断言，避免旧路径继续被依赖。
  - contract: 复用现有 contract tests，确认外部 API 不受清理影响。
  - integration: 跑完整 `tests/im_service`，验证真实入口与导入装配完整。
  - e2e: 复用现有 SSE e2e，作为主入口回归。
- Expected Tests:
  - `tests/im_service/unit/test_app_factory.py`
  - `tests/im_service/unit/test_repositories.py`
  - `tests/im_service/**/*`
- DoD:
  - `test_command` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 写清清理范围、负向复查结果、稳定回滚点。
