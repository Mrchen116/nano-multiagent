# TASKS (Milestone: M33)

- Test command: `PYTHONPATH=src pytest -q tests/im_service`
- Branch: `milestone/M33`
- Milestone status: `RUNNING`
- Scope guard:
  - Allowed: `src/IM/**`、`tests/im_service/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json(仅脚本)`。
  - Forbidden: `src/nano_multiagent/**`、`tests/im_service` 外既有测试、`ROADMAP.md`。

## [TODO] R33.1 SQLite 持久化骨架与初始化机制
- Acceptance:
  - 提供 `src/IM` 独立数据层（用户/会话/消息）与 SQLite schema 初始化。
  - 数据库初始化具备幂等性，可在空库首次启动自动建表。
  - 提供最小 repository 接口：创建用户、创建会话、写入消息、按会话查询消息。
  - 不依赖 `src/nano_multiagent/**` 任何模块。
- Tests Plan:
  - `unit`: 选。验证 schema 初始化与 repository 行为、边界与排序。
  - `contract`: 不选。本 Roadpoint 不暴露 HTTP 契约。
  - `integration`: 不选。接口链路在后续 Roadpoint 覆盖。
  - `e2e`: 不选。本 Milestone 入口验证由 integration 覆盖，避免冗余。
- Expected Tests:
  - `tests/im_service/unit/test_db_init.py`
  - `tests/im_service/unit/test_repositories.py`
- DoD:
  - `PYTHONPATH=src pytest -q tests/im_service` 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO

## [TODO] R33.2 Users/Conversations 基础 REST 接口
- Acceptance:
  - 提供 `POST /im/v1/users`、`GET /im/v1/users`。
  - 提供 `POST /im/v1/conversations`、`GET /im/v1/conversations`。
  - 会话支持参与者列表并落库。
  - 错误输入返回 4xx（如空 participant）。
- Tests Plan:
  - `unit`: 选。补路由依赖装配与服务层边界。
  - `contract`: 选。通过 Pydantic/响应断言固化字段契约。
  - `integration`: 选。FastAPI TestClient 覆盖 API->DB 主链路。
  - `e2e`: 不选。本 Milestone 仅后端基础能力，integration 足够覆盖入口。
- Expected Tests:
  - `tests/im_service/unit/test_app_factory.py`
  - `tests/im_service/integration/test_users_conversations_api.py`
- DoD:
  - `PYTHONPATH=src pytest -q tests/im_service` 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO

## [TODO] R33.3 Messages 接口与独立服务入口收口
- Acceptance:
  - 提供 `POST /im/v1/conversations/{id}/messages`、`GET /im/v1/conversations/{id}/messages`。
  - 消息按创建时间/自增顺序返回，跨会话隔离。
  - 新增独立服务入口 `src/IM/app.py`，可单独启动并初始化数据库。
  - `tests/im_service` 全绿，满足 Milestone exit criteria。
- Tests Plan:
  - `unit`: 选。验证消息仓储与时间/顺序边界。
  - `contract`: 选。验证消息响应字段与错误码契约。
  - `integration`: 选。覆盖消息 API 全链路与会话隔离。
  - `e2e`: 不选。当前目标为后端 API 持久化基础，无前端联调。
- Expected Tests:
  - `tests/im_service/unit/test_message_repo.py`
  - `tests/im_service/integration/test_messages_api.py`
- DoD:
  - `PYTHONPATH=src pytest -q tests/im_service` 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录决策/证据/回滚点/提交哈希。
- Commits:
  - C1: `<pending>`
  - C2: `<pending>`
  - C3: `<pending>`
- Status: TODO
